from django.shortcuts import get_object_or_404
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .permissions import IsAdminOrReadOnly, IsOwner, IsOwnerOrAdmin
from ecommerce.models import Product, Category, Cart, Order, CartItems, OrderItem, SubCategory
from .filters import ProductFilter
from .serializers import ProductSerializer, CategorySerializer, CartSerializer, CartItemSerializer, \
    AddCartItemSerializer, UpdateCartItemSerializer, OrderSerializer, SimpleProductSerializer, \
    SubCategorySerializer, GetProductSerializer


import uuid
import requests
from rest_framework.response import Response
from django.conf import settings


def initiate_payment(amount, email, cart_id, user):
    url = "https://api.flutterwave.com/v3/payments"
    headers = {
        "Authorization": f"Bearer {settings.FLW_SEC_KEY}"
    }
    first_name = user.first_name
    last_name = user.last_name
    user_id = user.id
    phone_no = user.phone_number

    data = {
        "tx_ref": str(uuid.uuid4()),
        "amount": str(amount),
        "currency": "NGN",
        "redirect_url": "https:/asluxeryoriginals.pythonanywhere.com/api/carts/confirm_payment/?c_id=" + cart_id,
        "meta": {
            "consumer_id": user_id,
            "consumer_mac": "92a3-912ba-1192a"
        },
        "customer": {
            "email": email,
            "phonenumber": phone_no,
            "name": f"{last_name} {first_name}"
        },
        "customizations": {
            "title": "AXLuxeryOriginals",
            "logo": "https://th.bing.com/th/id/OIP.YUyvxZV46V46TKoPLtcyjwHaIj?w=183&h=211&c=7&r=0&o=5&pid=1.7"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        return Response(response_data)

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
        )


class ApiCart(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsOwnerOrAdmin, IsAuthenticated]

    @action(detail=True, methods=['POST'])
    def pay(self, request, pk=None):
        cart = self.get_object()
        cart_items = CartItems.objects.filter(cart=cart)
        amount = cart.get_total_price()
        email = request.user.email
        user = request.user
        cart_id = str(cart.id)

        for cart_item in cart_items:
            product = cart_item.product
            if product.inventory < cart_item.quantity:
                return Response(
                    {
                        "error": f"Not enough inventory for product '{product.name}'. "
                                 f"Available: {product.inventory}, Requested: {cart_item.quantity}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        return initiate_payment(amount, email, cart_id, user)

    @action(detail=False, methods=["POST"])
    def confirm_payment(self, request):

        cart_id = request.GET.get("c_id")
        transaction_id = request.GET.get("transaction_id")
        status_from_gateway = request.GET.get("status", "").lower()
        if status_from_gateway != "successful":
            return Response({"detail": "Payment failed."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            cart = get_object_or_404(Cart, id=cart_id, owner=request.user)
            cart_items = CartItems.objects.filter(cart=cart)

            order = Order.objects.create(owner=request.user)
            order_items = []
            for cart_item in cart_items:
                product = cart_item.product
                product.inventory -= cart_item.quantity
                product.save()

                order_items.append(
                    OrderItem(
                        owner=request.user,
                        order=order,
                        product=product,
                        quantity=cart_item.quantity,
                        price=cart_item.product.price
                    )
                )
            OrderItem.objects.bulk_create(order_items)

            cart_items.delete()
            cart.delete()

            serializer = OrderSerializer(order)
            return Response({
                "message": "Payment successful, order created.",
                "order": serializer.data,
                "transaction_id": transaction_id
            }, status=status.HTTP_201_CREATED)

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
        return CartItems.objects.filter(cart_slug=self.kwargs['cart_slug'], owner=self.request.user)

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

    def get_permissions(self):
        if self.request.method in ["PATCH", "DELETE"]:
            return [IsAdminUser()]
        return [IsOwner()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(owner=user)
