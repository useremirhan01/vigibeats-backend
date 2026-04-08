from datetime import timedelta
from decimal import Decimal
from secrets import token_urlsafe
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from article.models import Beat, BeatLicense


def generate_tracking_code():
    return uuid4().hex[:12].upper()


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("fulfilled", "Fulfilled"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="TRY")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_provider = models.CharField(max_length=50, default="iyzico")
    tracking_code = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        default=generate_tracking_code,
    )
    notes = models.TextField(blank=True)
    buyer_data = models.JSONField(default=dict, blank=True)
    billing_address = models.JSONField(default=dict, blank=True)
    shipping_address = models.JSONField(default=dict, blank=True)
    payment_metadata = models.JSONField(default=dict, blank=True)
    delivery_token = models.CharField(max_length=128, blank=True, default="")
    delivery_token_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = generate_tracking_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - {self.tracking_code}"

    def recalculate_amount(self):
        total = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        self.amount = total
        return total

    @property
    def reserves_exclusive_inventory(self):
        return self.status in {"pending", "paid", "fulfilled"}

    @property
    def is_payment_successful(self):
        return self.status in {"paid", "fulfilled"}

    def sync_exclusive_inventory(self):
        exclusive_items = self.items.select_related("beat", "beat_license").filter(
            selected_license=BeatLicense.LICENSE_EXCLUSIVE
        )

        for item in exclusive_items:
            if item.beat_license is not None:
                item.beat_license.sold = self.reserves_exclusive_inventory
                item.beat_license.is_active = not item.beat_license.sold
                item.beat_license.save(update_fields=["sold", "is_active", "updated_at"])
            else:
                Beat.objects.filter(pk=item.beat_id).update(
                    exclusive_available=not self.reserves_exclusive_inventory
                )

    def issue_delivery_token(self, hours_valid=24, commit=True):
        self.delivery_token = token_urlsafe(32)
        self.delivery_token_expires_at = timezone.now() + timedelta(hours=hours_valid)
        if commit:
            self.save(update_fields=["delivery_token", "delivery_token_expires_at", "updated_at"])
        return self.delivery_token

    def has_valid_delivery_token(self, token):
        if not token or token != self.delivery_token:
            return False
        if self.delivery_token_expires_at is None:
            return False
        return self.delivery_token_expires_at >= timezone.now() and self.is_payment_successful

    def set_status(self, new_status):
        update_fields = ["status", "updated_at"]
        self.status = new_status

        if new_status == "paid" and self.paid_at is None:
            self.paid_at = timezone.now()
            update_fields.append("paid_at")

        if new_status == "fulfilled":
            if self.paid_at is None:
                self.paid_at = timezone.now()
                update_fields.append("paid_at")
            if self.fulfilled_at is None:
                self.fulfilled_at = timezone.now()
                update_fields.append("fulfilled_at")
            if not self.delivery_token or (
                self.delivery_token_expires_at is not None and self.delivery_token_expires_at < timezone.now()
            ):
                self.issue_delivery_token(commit=False)
                update_fields.extend(["delivery_token", "delivery_token_expires_at"])

        self.save(update_fields=update_fields)
        self.sync_exclusive_inventory()

    def mark_payment_result(self, payment_data, success):
        self.payment_provider = "iyzico"
        self.payment_metadata = {
            **self.payment_metadata,
            "conversation_id": payment_data.get("conversationId") or payment_data.get("paymentConversationId"),
            "token": payment_data.get("token", self.payment_metadata.get("token", "")),
            "payment_id": payment_data.get("paymentId") or payment_data.get("iyziPaymentId"),
            "payment_status": payment_data.get("paymentStatus") or payment_data.get("status"),
            "raw": payment_data,
        }
        self.save(update_fields=["payment_provider", "payment_metadata", "updated_at"])
        self.set_status("fulfilled" if success else "failed")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    beat = models.ForeignKey(Beat, on_delete=models.PROTECT, related_name="order_items")
    beat_license = models.ForeignKey(
        BeatLicense,
        on_delete=models.PROTECT,
        related_name="order_items",
        null=True,
        blank=True,
    )

    beat_title = models.CharField(max_length=255)
    selected_license = models.CharField(max_length=20, choices=BeatLicense.LICENSE_CHOICES)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.beat_title} - {self.selected_license}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
