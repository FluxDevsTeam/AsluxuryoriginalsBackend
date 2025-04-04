import uuid
from django.http import JsonResponse
import requests
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce, Cast
from rest_framework.viewsets import ViewSet
from .utils import EmailThread
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from .permissions import IsAdminOrReadOnly, IsOwner, IsOwnerOrAdmin
from ecommerce.models import Product, Category, Cart, Order, CartItems, OrderItem, SubCategory
from .filters import ProductFilter, OrderFilter
from .serializers import ProductSerializer, CategorySerializer, CartSerializer, CartItemSerializer, \
    AddCartItemSerializer, UpdateCartItemSerializer, OrderSerializer, SimpleProductSerializer, \
    SubCategorySerializer, GetProductSerializer, DashboardOrderSerializer
from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.timezone import now
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


def generate_confirm_token(user, cart_id):
    """
    Generates a token for payment confirmation.
    """
    refresh = RefreshToken.for_user(user)
    refresh['cart_id'] = cart_id
    refresh['exp'] = now() + timedelta(hours=20)
    return str(refresh.access_token)


def initiate_payment(amount, email, user, redirect_url):
    url = "https://api.flutterwave.com/v3/payments"
    headers = {
        "Authorization": f"Bearer {settings.FLW_SEC_KEY}"
    }
    first_name = user.first_name
    last_name = user.last_name
    phone_no = user.phone_number

    data = {
        "tx_ref": str(uuid.uuid4()),
        "amount": str(amount),
        "currency": "NGN",
        "redirect_url": redirect_url,
        "meta": {
            "consumer_id": user.id,
        },
        "customer": {
            "email": email,
            "phonenumber": phone_no,
            "name": f"{last_name} {first_name}"
        },
        "customizations": {
            "title": "ASLUXURY ORIGINALS",
            "logo": "https://th.bing.com/th/id/OIP.YUyvxZV46V46TKoPLtcyjwHaIj?w=183&h=211&c=7&r=0&o=5&pid=1.7"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()

        if response.status_code in [200, 201]:
            payment_link = response_data.get("data", {}).get("link")
            if not payment_link:
                return Response(
                    {"error": "Payment link not found in the response."},
                    status=500
                )
            return Response({
                "message": "Payment initiated successfully.",
                "payment_link": payment_link,
            }, status=200)
        else:
            return Response({
                "error": response_data.get("message", "An error occurred while initiating payment.")
            }, status=response.status_code)

    except requests.exceptions.RequestException as err:
        return Response({"error": str(err)}, status=500)


class ApiProducts(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'colour', 'material']
    ordering_fields = ['price']
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return GetProductSerializer
        elif self.action == 'retrieve':
            return GetProductSerializer
        return ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(
            inventory__gte=1
        ).order_by('-top_deal', 'id')


class ApiCart(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsOwnerOrAdmin, IsAuthenticated]

    @action(detail=True, methods=['POST'])
    def pay(self, request, pk=None):
        cart = self.get_object()
        print(cart)
        cart_items = CartItems.objects.filter(cart=cart)
        amount = cart.get_total_price()
        email = request.user.email
        user = request.user
        cart_id = str(cart.id)

        for cart_item in cart_items:
            print("item")
            product = cart_item.product
            if product.inventory < cart_item.quantity:
                return Response(
                    {
                        "error": f"Not enough inventory for product '{product.name}'. "
                                 f"Available: {product.inventory}, Requested: {cart_item.quantity}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        confirm_token = generate_confirm_token(user, cart_id)

        redirect_url = (
            f"https://api.asluxuryoriginals.com/api/carts/confirm_payment/"
            f"?c_id={cart_id}&token={confirm_token}"
        )
        
        return initiate_payment(amount, email, user, redirect_url)

    @action(detail=False, methods=["GET"], permission_classes=[AllowAny])
    def confirm_payment(self, request):
        cart_id = request.GET.get("c_id")
        token = request.GET.get("token")
        transaction_id = request.GET.get("transaction_id")
        status_from_gateway = request.GET.get("status", "").lower()

        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
        except AuthenticationFailed:
            return JsonResponse({"detail": "Invalid or expired confirmation token."}, status=401)

        if status_from_gateway != "successful":
            return redirect(f"https://asluxuryoriginals.com/checkout/")

        with transaction.atomic():
            cart = get_object_or_404(Cart, id=cart_id, owner=user)
            cart_items = CartItems.objects.filter(cart=cart)

            if not cart_items.exists():
                return JsonResponse({"detail": "Cart is empty or invalid."}, status=400)

            order = Order.objects.create(
                owner=user,
                address=cart.address,
                state=cart.state,
                city=cart.city,
                postal_code=cart.postal_code,
                transaction_id=transaction_id
            )

            order_items = []
            for cart_item in cart_items:
                product = cart_item.product
                if product.inventory < cart_item.quantity:
                    return JsonResponse(
                        {
                            "error": f"Not enough inventory for product '{product.name}'. "
                                     f"Available: {product.inventory}, Requested: {cart_item.quantity}"
                        },
                        status=400
                    )

                product.inventory -= cart_item.quantity
                product.save()

                order_items.append(
                    OrderItem(
                        owner=user,
                        order=order,
                        product=product,
                        quantity=cart_item.quantity,
                        price=cart_item.product.price,
                        size=cart_item.size
                    )
                )

            OrderItem.objects.bulk_create(order_items)
            amount = order.calculate_total_price()
            order.save()

            # Notify admin
            email_thread = EmailThread(
                subject='New Order',
                message=f'User {user.email} made an order of total amount of ₦{amount}, '
                        f'order ID is {order.id}. Link to order: '
                        f'https://asluxuryoriginals.com/orders/',
                recipient_list=[settings.EMAIL_HOST_USER],
            )
            email_thread.start()

            cart_items.delete()
            cart.delete()

            return redirect(f"https://asluxuryoriginals.com/orders/")

    def get_queryset(self):
        return Cart.objects.filter(owner=self.request.user).select_related('owner').prefetch_related('items')


class ApiCartItem(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']
    permission_classes = [IsOwnerOrAdmin, IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AddCartItemSerializer
        elif self.request.method == 'PATCH':
            return UpdateCartItemSerializer
        return CartItemSerializer

    def get_queryset(self):
        return CartItems.objects.filter(cart_id=self.kwargs['cart_pk'], owner=self.request.user)

    def get_serializer_context(self):
        return {
            'request': self.request,
            'cart_id': self.kwargs.get('cart_pk')
        }


class ApiCategory(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly, ]
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['title']


class ApiSubCategory(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly, ]
    serializer_class = SubCategorySerializer
    queryset = SubCategory.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['title']


class ApiOrder(viewsets.ModelViewSet):
    http_method_names = ["get", "patch", "delete", "options", "head"]
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['id']
    search_fields = ['id']

    def get_permissions(self):
        if self.request.method in ["PATCH", "DELETE"]:
            return [IsAdminUser()]
        return [IsOwner()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all().order_by('-placed_at')
        return Order.objects.filter(owner=user).order_by('-placed_at')


class DashboardOrderViewSet(ViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id']

    def list(self, request):
        """
        Retrieve all orders, optionally filtered by month, year, or date range.
        """
        orders = Order.objects.all().order_by('-placed_at')
        filters = OrderFilter(request.GET, queryset=orders)
        filtered_orders = filters.qs

        total_cost = filtered_orders.aggregate(total=Sum('total_price'))['total'] or 0

        serializer = DashboardOrderSerializer(filtered_orders, many=True)
        return Response({
            "orders": serializer.data,
            "total_cost": total_cost
        })

    @action(detail=False, methods=["GET"], url_path='summary')
    def summary(self, request):
        """
        Retrieve a summary of total orders and revenue.
        """
        total_orders = Order.objects.count()
        total_revenue = Order.objects.aggregate(total=Sum('total_price'))['total'] or 0

        return Response({
            "total_orders": total_orders,
            "total_revenue": total_revenue
        })

    @action(detail=False, methods=["GET"], url_path='most-sold-products')
    def most_sold_products(self, request):
        """
        Retrieve the list of most sold products with quantities and total sales price.
        Supports filtering by revenue generated.
        """

        products_data = (
            OrderItem.objects
            .values(product_name=F('product__name'), product_identifier=F('product__id'))
            .annotate(
                total_quantity=Sum('quantity'),
                total_revenue=Coalesce(
                    Sum(
                        Cast(F('quantity'), DecimalField()) * Cast(F('price'), DecimalField())
                    ),
                    Value(0),
                    output_field=DecimalField()
                ),
            )
            .filter(total_quantity__gt=0)
            .order_by('-total_quantity')
        )

        if request.GET.get('order_by') == 'revenue':
            products_data = products_data.order_by('-total_revenue')

        total_revenue = sum([item['total_revenue'] for item in products_data])

        return Response({
            "most_sold_products": list(products_data),
            "total_revenue": total_revenue,
        })