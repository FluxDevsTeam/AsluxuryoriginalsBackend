from django_filters import DateFilter
from django_filters.rest_framework import FilterSet, CharFilter, NumberFilter
from ecommerce.models import Product, Order


class ProductFilter(FilterSet):
    category_id = NumberFilter(field_name='category__id', lookup_expr='exact')
    category_name = CharFilter(field_name='category__title', lookup_expr='exact')
    subcategory_id = NumberFilter(field_name='subcategory__id', lookup_expr='exact')
    subcategory_name = CharFilter(field_name='subcategory__title', lookup_expr='exact')

    class Meta:
        model = Product
        fields = {
            'price': ['gt', 'lt'],  # Only include fields that are directly on the Product model
        }


class OrderFilter(FilterSet):
    month = NumberFilter(field_name='placed_at', lookup_expr='month')
    year = NumberFilter(field_name='placed_at', lookup_expr='year')
    start_date = DateFilter(field_name='placed_at', lookup_expr='gte')
    end_date = DateFilter(field_name='placed_at', lookup_expr='lte')

    class Meta:
        model = Order
        fields = ['month', 'year', 'start_date', 'end_date']


