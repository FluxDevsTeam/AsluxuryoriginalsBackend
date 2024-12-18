from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

router = routers.DefaultRouter()
router.register('products', views.ApiProducts, basename='product')
router.register('category', views.APICategory, basename='category')
router.register('cart', views.ApiCart, basename='cart')
router.register('profile', views.ApiProfile, basename='profile')
router.register('orders', views.ApiOrder, basename='orders')

product_router = routers.NestedDefaultRouter(router, 'products', lookup='product')
product_router.register('reviews', views.ApiProductsReviews, basename='product-reviews')
cart_router = routers.NestedDefaultRouter(router, 'cart', lookup='cart')
cart_router.register('items', views.ApiCartItem, basename='cart-items')
urlpatterns = [
    # path("products/", views.api_products),
    # path("products/<str:pk>/", views.api_product),
    # path("category/", views.api_categories),
    # path("category/<str:pk>/", views.api_category),

    path("", include(router.urls)),
    path("", include(product_router.urls)),
    path("", include(cart_router.urls)),
    # path("", include(cart_router.urls))
    # path("products/", views.ApiProducts.as_view()),
    # path("products/<str:pk>", views.ApiProduct.as_view()),
    # path("categories", views.APICategories.as_view()),
    # path("categories/<str:pk>", views.APICategory.as_view())
]