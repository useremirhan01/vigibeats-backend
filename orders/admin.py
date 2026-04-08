from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ("id", "tracking_code", "email", "status", "amount", "currency", "created_at")
    list_filter = ("status", "currency", "created_at", "paid_at", "fulfilled_at")
    search_fields = ("email", "full_name", "tracking_code")
    readonly_fields = ("tracking_code", "created_at", "updated_at", "paid_at", "fulfilled_at")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "beat_title", "selected_license", "unit_price", "quantity")
    search_fields = ("beat_title", "order__email")
