from rest_framework import serializers
from ecommerce.models import *
from django.db import transaction


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'title', 'slug']
        read_only_fields = ['id']


class ColourSerializer(serializers.ModelSerializer):
    class Meta:
        model = Colour
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id']


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ['id', 'size', 'slug']
        read_only_fields = ['id']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImages
        fields = ['id', 'product', 'image', 'slug']
        read_only_fields = ['id']


class ProductSerializer(serializers.ModelSerializer):
    extra_images = ProductImageSerializer(many=True, read_only=True)
    category_view = CategorySerializer(read_only=True)
    size_view = SizeSerializer(many=True, read_only=True)
    colour_view = ColourSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(max_length=1000000, allow_empty_file=True, use_url=False),
        write_only=True,
        required=False  # Make the field optional
    )

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'discount', 'image', 'colour', 'size', 'price', 'slug', 'inventory','size_view','colour_view', 'top_deal', 'extra_images', 'category', 'category_view', 'uploaded_images']
        read_only_fields = ['id']
        write_only_fields = ['category', 'color', 'size']

    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])

        # Pop many-to-many fields from validated_data
        colours = validated_data.pop('colour', [])
        sizes = validated_data.pop('size', [])

        # Create the Product instance
        product = Product.objects.create(**validated_data)

        # Add many-to-many relationships
        if colours:
            product.colour.set(colours)
        if sizes:
            product.size.set(sizes)

        # Handle uploaded images
        for image in uploaded_images:
            ProductImages.objects.create(product=product, image=image)

        return product


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
        fields = ['id', 'items','owner', 'grand_total']
        read_only_fields = ['id', 'owner']

    def create(self, validated_data):
        # Access the current user from the request object
        user = self.context['request'].user
        # Set the owner to the current user
        validated_data['owner'] = user
        # Create and return the new Cart instance
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

        # Fetch the product to check inventory
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise serializers.ValidationError("The product does not exist.")

        # Check if the desired quantity exceeds the product inventory
        if quantity > product.inventory:
            raise serializers.ValidationError("The requested quantity exceeds the available inventory.")

        # Ensure 'owner' is set in the validated data
        self.validated_data['owner'] = user

        try:
            # Check if the cart item already exists
            cartitem = CartItems.objects.get(product_id=product_id, cart_id=cart_id)

            # Check if the combined quantity exceeds inventory
            if cartitem.quantity + quantity > product.inventory:
                raise serializers.ValidationError("The total quantity in your cart exceeds the available inventory.")

            cartitem.quantity += quantity  # Update quantity
            cartitem.save()
            self.instance = cartitem  # Set the instance for the serializer
        except CartItems.DoesNotExist:
            # Create a new cart item if it doesn't exist
            self.instance = CartItems.objects.create(cart_id=cart_id, **self.validated_data)

        return self.instance

    class Meta:
        model = CartItems
        fields = ['id', 'product_id', 'quantity', 'slug']
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
    product = SimpleProductSerializer

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'slug']
        read_only_fields = ['id']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'placed_at' , 'owner', 'items', 'slug']
        read_only_fields = ['id']

