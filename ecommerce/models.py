from django.db import models
from autoslug import AutoSlugField
import uuid
from django.conf import settings


# note i had to create nultple functions because lambda doesnt pass makemigrations and migrate

# Named function to generate slug for ProductImages
def generate_product_image_slug(instance):
    return f"{instance.product.name}-other-image"


# Named function to generate slug for Cart
def generate_cart_slug(instance):
    return f"{instance.owner.email}-cart"


# Named function to generate slug for CartItems
def generate_cart_item_slug(instance):
    return f"{instance.cart.slug}-{instance.product.name}"


# Named function to generate slug for Order
def generate_order_slug(instance):
    return f"{instance.owner.email}-order"


# Named function to generate slug for OrderItem
def generate_order_item_slug(instance):
    return f"{instance.order.id}-{instance.product.name}"


class Category(models.Model):
    title = models.CharField(max_length=200)
    slug = AutoSlugField(populate_from='title', unique=True, db_index=True)

    def __str__(self):
        return self.title


class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=200)
    slug = AutoSlugField(populate_from='title', unique=True, db_index=True)

    def __str__(self):
        return self.title


class Size(models.Model):
    size = models.CharField(max_length=30)
    slug = AutoSlugField(populate_from='size', unique=True)

    def __str__(self):
        return self.size


class Product(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    material = models.CharField(max_length=1000, blank=True, null=True)
    discount = models.BooleanField(default=False)
    colour = models.CharField(max_length=1000, blank=True, null=True)
    size = models.ManyToManyField(Size)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, blank=True, null=True, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, blank=True, null=True,
                                    related_name='products_subcategory')
    slug = AutoSlugField(populate_from='name', unique=True, db_index=True)
    inventory = models.IntegerField(default=5)
    top_deal = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class ProductImages(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='img', default='placeholder.jpg', null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} extra image"


class Cart(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts"
    )
    created = models.DateTimeField(auto_now_add=True)
    slug = AutoSlugField(
        populate_from=generate_cart_slug, unique=True, db_index=True
    )

    def __str__(self):
        return f"Cart {self.id} ({self.slug})"

    def get_total_price(self):
        cart_items = self.items.all()  # Using related_name='items'
        return sum(item.product.price * item.quantity for item in cart_items)


class CartItems(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveSmallIntegerField(default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cart_items")
    slug = AutoSlugField(
        populate_from=generate_cart_item_slug, unique=True, db_index=True
    )

    def __str__(self):
        return f"CartItem #{self.product.name} ({self.slug})"


class Order(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="order_history")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    slug = AutoSlugField(populate_from=generate_order_slug, unique=True, db_index=True)

    def calculate_total_price(self):
        self.total_price = sum(item.quantity * item.price for item in self.items.all())
        return self.total_price

    def save(self, *args, **kwargs):
        self.calculate_total_price()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} ({self.slug}) - Total: ₦{self.total_price:.2f}"


class OrderItem(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    slug = AutoSlugField(
        populate_from=generate_order_item_slug, unique=True, db_index=True
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            self.price = self.product.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} @ ₦ {self.price} (Order)"
