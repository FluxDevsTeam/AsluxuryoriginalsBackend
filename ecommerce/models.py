from django.db import models
from django.utils.text import slugify
import uuid
from django.conf import settings


# Create your models here.


class Category(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    title = models.CharField(max_length=200)
    category_id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, unique=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    featured_product = models.OneToOneField('Product', on_delete=models.CASCADE, blank=True, null=True,
                                            related_name='featured_product')
    icon = models.CharField(max_length=100, default=None, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Generate a unique slug if it doesn't exist
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Product(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    discount = models.BooleanField(default=False)
    image = models.ImageField(upload_to='img', blank=True, null=True, default='')
    price = models.FloatField(default=100.00)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, blank=True, null=True, related_name='products')
    slug = models.SlugField(unique=True, blank=True, null=True)
    inventory = models.IntegerField(default=5)
    top_deal = models.BooleanField(default=False)
    flash_sales = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Generate a unique slug if it doesn't exist
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductImages(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='img', default='', null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Generate a unique slug if it doesn't exist
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Cart(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    created = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Generate a unique slug if it doesn't exist
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.id)


class Cartitems(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=True, null=True, related_name='cartitems')
    quantity = models.PositiveSmallIntegerField(default=0)
    slug = models.SlugField(unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Generate a unique slug if it doesn't exist
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Order(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    slug = models.SlugField(unique=True, blank=True, null=True)
    def __str__(self):
        return f"Order #{self.id} - Total: ${self.total_price}"

    def save(self, *args, **kwargs):
        # Generate a unique slug if it doesn't exist
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def update_total_price(self):
        # Recalculate based on OrderItems
        items = self.items.all()
        self.total_price = sum(item.quantity * item.price for item in items)
        self.save()


class OrderItem(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Store the price at the time of order creation
    slug = models.SlugField(unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Generate a unique slug if it doesn't exist
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Automatically set the product price on first save
        if not self.pk:  # This ensures it's the first save (i.e., when creating the object)
            self.price = self.product.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} @ NGN{self.price} (Order)"


