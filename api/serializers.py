from rest_framework import serializers
from ecommerce.models import *


class SubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ['category', 'title']
        extra_kwargs = {
            'category': {'write_only': True},
        }


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['title']


class GetProductSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField(required=False)
    subcategory = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'discount', 'colour', 'size', 'price', 'inventory',
                  'top_deal', 'image1', 'image2', 'image3', 'category', 'subcategory']
        read_only_fields = ['id']

    def get_category(self, obj):
        if obj.category:
            return {
                "name": obj.category.title,
                "id": obj.category.id
            }
        return None

    def get_subcategory(self, obj):
        # Return subcategory details like name and slug
        if obj.subcategory:
            return {
                "name": obj.subcategory.title,
                "id": obj.subcategory.id
            }
        return None


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False)
    subcategory = serializers.PrimaryKeyRelatedField(queryset=SubCategory.objects.all(), required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'discount', 'colour', 'size', 'price', 'inventory',
                  'top_deal', 'image1', 'image2', 'image3', 'category', 'subcategory']
        read_only_fields = ['id']


class SimpleProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer()

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'category', 'slug']
        read_only_fields = ['id']


class CartItemSerializer(serializers.ModelSerializer):
    sub_total = serializers.SerializerMethodField(method_name='total')
    product = SimpleProductSerializer()

    class Meta:
        model = CartItems
        fields = ['id', 'cart', 'product', 'quantity', 'sub_total']
        read_only_fields = ['id']

    def total(self, cartitem: CartItems):
        return cartitem.quantity * cartitem.product.price


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    grand_total = serializers.SerializerMethodField(method_name='main_total')

    class Meta:
        model = Cart
        fields = ['id', 'items', 'owner', 'grand_total']
        read_only_fields = ['id', 'owner']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['owner'] = user
        return Cart.objects.create(**validated_data)

    def main_total(self, cart: Cart):
        items = cart.items.all()
        total = sum([item.quantity * item.product.price for item in items])
        return total


class AddCartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField()

    def validate_product_id(self, value):
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError('there is no product associated with the given id')
        return value

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError('Quantity cannot be less than 0')
        return value

    def save(self, **kwargs):
        cart_id = self.context['cart_id']
        product_id = self.validated_data['product_id']
        quantity = self.validated_data['quantity']
        user = self.context['request'].user

        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise serializers.ValidationError("The product does not exist.")

        if quantity > product.inventory:
            raise serializers.ValidationError("The requested quantity exceeds the available inventory.")

        self.validated_data['owner'] = user

        try:
            cartitem = CartItems.objects.get(product_id=product_id, cart_id=cart_id)

            if cartitem.quantity + quantity > product.inventory:
                raise serializers.ValidationError("The total quantity in your cart exceeds the available inventory.")

            cartitem.quantity += quantity
            cartitem.save()
            self.instance = cartitem
        except CartItems.DoesNotExist:
            self.instance = CartItems.objects.create(cart_id=cart_id, **self.validated_data)

        return self.instance

    class Meta:
        model = CartItems
        fields = ['id', 'product_id', 'quantity']
        read_only_fields = ['id']


class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItems
        fields = ['quantity']
        read_only_fields = ['id']

    def save(self, **kwargs):
        cartitem = self.instance
        quantity = self.validated_data['quantity']
        product = cartitem.product

        if quantity > product.inventory:
            raise serializers.ValidationError("The requested quantity exceeds the available inventory.")
        cartitem.quantity = quantity
        cartitem.save()
        return cartitem


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'owner']
        read_only_fields = ['id']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'address',  'placed_at', 'owner', 'delivered', 'total_price', 'items',]
        read_only_fields = ['id']


class DashboardOrderSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Order
        fields = ['id', 'placed_at', 'owner', 'total_price']
        read_only_fields = ['id', 'total_price']