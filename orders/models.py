from django.conf import settings
from django.db import models
from article.models import Beat


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    LICENSE_CHOICES = [
        ("basic", "Basic"),
        ("premium", "Premium"),
        ("exclusive", "Exclusive"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    beat = models.ForeignKey(Beat, on_delete=models.CASCADE, related_name="orders")
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    license_type = models.CharField(max_length=20, choices=LICENSE_CHOICES, default="basic")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_provider = models.CharField(max_length=50, default="mock_iyzico")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.email}"

class OrderItem(models.Model):
    LICENSE_CHOICES = [
        ("basic", "Basic License"),
        ("premium", "Premium License"),
        ("exclusive", "Exclusive License"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    beat = models.ForeignKey(Beat, on_delete=models.PROTECT, related_name="order_items")

    beat_title = models.CharField(max_length=255)
    selected_license = models.CharField(max_length=20, choices=LICENSE_CHOICES)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.beat_title} - {self.selected_license}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity