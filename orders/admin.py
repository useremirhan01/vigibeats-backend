from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "status", "amount", "created_at")
    list_filter = ("status", "license_type", "created_at")
    search_fields = ("email", "full_name")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "beat_title", "selected_license", "unit_price", "quantity")
    search_fields = ("beat_title", "order__email")