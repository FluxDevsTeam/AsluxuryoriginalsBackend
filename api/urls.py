from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter
from .views import ApiProducts, ApiCart, ApiCartItem, ApiCategory, ApiOrder, ApiSubCategory, DashboardOrderViewSet

router = DefaultRouter()

router.register('products', ApiProducts, basename='product')
router.register('categories', ApiCategory, basename='category')
router.register('orders', ApiOrder, basename='order')
router.register('carts', ApiCart, basename='cart')
router.register('subcategory', ApiSubCategory, basename='subcategory')

# Nested router for Cart and CartItems (now 'carts' is registered above)
cart_router = NestedDefaultRouter(router, 'carts', lookup='cart')
cart_router.register('items', ApiCartItem, basename='cart-items')

urlpatterns = [
    path('', include(router.urls)),  # Main API urls
    path('', include(cart_router.urls)),  # Nested urls for Cart and CartItems
    path('dashboard/', DashboardOrderViewSet.as_view({'get': 'list'}), name='dashboard'),
    path('dashboard/summary/', DashboardOrderViewSet.as_view({'get': 'summary'}),
         name='summary'),
    path('dashboard/most-sold-products/', DashboardOrderViewSet.as_view({'get': 'most_sold_products'}),
         name='most_sold_products'),
]
