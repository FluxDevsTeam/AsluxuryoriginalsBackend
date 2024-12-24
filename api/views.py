
from django.shortcuts import get_object_or_404
from django.db import transaction
import uuid
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, DestroyModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .permissions import IsAdminOrReadOnly, IsOwner, IsOwnerOrAdmin
from ecommerce.models import Product, Category, Cart, Order, Size, Colour, CartItems, OrderItem
from .filters import ProductFilter
from .serializers import ProductSerializer, CategorySerializer, CartSerializer, CartItemSerializer, \
    AddCartItemSerializer, UpdateCartItemSerializer, OrderSerializer, SimpleProductSerializer, \
    SizeSerializer, ColourSerializer
from rest_framework.parsers import MultiPartParser, FormParser
import requests

import uuid
import requests
from rest_framework.response import Response
from django.conf import settings


def initiate_payment(request, amount, email, cart_id, user):
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
        "redirect_url": f"http://127.0.0.1:8000/api",  # Change this in production
        "meta": {
            "consumer_id": user_id,
            "consumer_mac": "92a3-912ba-1192a"  # Optional, for fraud prevention
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

        if response.status_code == 200:
            response_data = response.json()  # The JSON response from Flutterwave
            return Response(response_data)  # Returning the response data as JSON

        # In case of error from Flutterwave
        error_data = {"error": "Payment initiation failed", "details": response.json()}
        return Response(error_data, status=response.status_code)

    except requests.RequestException as e:
        # Handle any request errors
        error_data = {"error": str(e)}
        return Response(error_data, status=500)


class ApiProducts(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'color']
    ordering_fields = ['price']
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return SimpleProductSerializer
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

        # Validate inventory
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

        amount = cart.get_total_price()
        email = request.user.email
        user = request.user
        cart_id = str(cart.id)

        # Call initiate_payment and handle the response
        payment_response = initiate_payment(request, amount, email, cart_id, user)

        if "error" in payment_response:
            return Response(payment_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(payment_response, status=status.HTTP_200_OK)

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

            # Create the order
            order = Order.objects.create(owner=request.user)
            order_items = []
            for cart_item in cart_items:
                product = cart_item.product
                product.inventory -= cart_item.quantity
                product.save()

                order_items.append(
                    OrderItem(
                        order=order,
                        product=product,
                        quantity=cart_item.quantity
                    )
                )
            OrderItem.objects.bulk_create(order_items)

            # Clear the cart
            cart_items.delete()
            cart.delete()

            # Return success response
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
        return CartItems.objects.filter(cart_id=self.kwargs['cart_pk'], owner=self.request.user)

    def get_serializer_context(self):
        return {
            'request': self.request,
            'cart_id': self.kwargs.get('cart_pk')
        }


class ApiColour(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly, ]
    serializer_class = ColourSerializer
    queryset = Colour.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['name']
    pagination_class = PageNumberPagination


class ApiCategory(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly, ]
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['name']


class ApiSize(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly, ]
    serializer_class = SizeSerializer
    queryset = Size.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['size']


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
