from django.db import transaction
from rest_framework import serializers

from article.models import Beat, BeatLicense

from .models import Order, OrderItem


class OrderItemCreateSerializer(serializers.Serializer):
    beat_id = serializers.IntegerField()
    selected_license = serializers.ChoiceField(choices=BeatLicense.LICENSE_CHOICES)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        try:
            beat = Beat.objects.get(id=attrs["beat_id"])
        except Beat.DoesNotExist as exc:
            raise serializers.ValidationError({"beat_id": "Beat not found."}) from exc

        license_obj = beat.get_license(attrs["selected_license"])
        if not beat.is_license_available(attrs["selected_license"]):
            raise serializers.ValidationError(
                {"selected_license": "This license is no longer available for the selected beat."}
            )

        if attrs["selected_license"] == BeatLicense.LICENSE_EXCLUSIVE and attrs["quantity"] != 1:
            raise serializers.ValidationError(
                {"quantity": "Exclusive licenses can only be purchased one time."}
            )

        attrs["beat"] = beat
        attrs["beat_license"] = license_obj
        attrs["unit_price"] = beat.get_price_for_license(attrs["selected_license"])
        return attrs


class DeliveryItemSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "beat_title", "selected_license", "download_url"]

    def get_download_url(self, obj):
        request = self.context.get("request")
        token = self.context.get("delivery_token")
        if request is None or not token:
            return None
        return request.build_absolute_uri(
            f"/api/orders/delivery/{token}/items/{obj.id}/download/"
        )


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "beat",
            "beat_license",
            "beat_title",
            "selected_license",
            "unit_price",
            "quantity",
            "line_total",
        ]

    def get_line_total(self, obj):
        return obj.line_total


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_ready = serializers.BooleanField(source="is_payment_successful", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "tracking_code",
            "full_name",
            "email",
            "amount",
            "currency",
            "status",
            "payment_provider",
            "notes",
            "created_at",
            "paid_at",
            "fulfilled_at",
            "updated_at",
            "delivery_ready",
            "items",
        ]
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    currency = serializers.CharField(max_length=10, default="TRY")
    items = OrderItemCreateSerializer(many=True, required=False)
    beat_id = serializers.IntegerField(required=False)
    license_type = serializers.ChoiceField(
        choices=BeatLicense.LICENSE_CHOICES,
        required=False,
    )
    quantity = serializers.IntegerField(min_value=1, default=1, required=False)

    def validate(self, attrs):
        items = attrs.get("items")
        beat_id = attrs.get("beat_id")
        license_type = attrs.get("license_type")
        quantity = attrs.get("quantity", 1)

        if not items:
            if beat_id is None or license_type is None:
                raise serializers.ValidationError(
                    "Provide either an items list or beat_id with license_type."
                )
            item_serializer = OrderItemCreateSerializer(
                data={
                    "beat_id": beat_id,
                    "selected_license": license_type,
                    "quantity": quantity,
                }
            )
            item_serializer.is_valid(raise_exception=True)
            attrs["items"] = [item_serializer.validated_data]

        if not attrs["items"]:
            raise serializers.ValidationError({"items": "At least one item is required."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        item_payloads = validated_data.pop("items")
        validated_data.pop("beat_id", None)
        validated_data.pop("license_type", None)
        validated_data.pop("quantity", None)

        user = request.user if request.user.is_authenticated else None

        order = Order.objects.create(
            user=user,
            full_name=validated_data["full_name"],
            email=validated_data["email"],
            currency=validated_data.get("currency", "TRY"),
            status="pending",
            payment_provider="iyzico",
        )

        for item_payload in item_payloads:
            beat = item_payload["beat"]
            beat_license = item_payload["beat_license"]
            selected_license = item_payload["selected_license"]
            quantity = item_payload["quantity"]
            unit_price = item_payload["unit_price"]

            OrderItem.objects.create(
                order=order,
                beat=beat,
                beat_license=beat_license,
                beat_title=beat.title,
                selected_license=selected_license,
                unit_price=unit_price,
                quantity=quantity,
            )

        order.recalculate_amount()
        order.save(update_fields=["amount"])
        order.sync_exclusive_inventory()
        return order


class OrderTrackingSerializer(serializers.Serializer):
    tracking_code = serializers.CharField(max_length=32)
    email = serializers.EmailField()

    def validate(self, attrs):
        try:
            attrs["order"] = Order.objects.prefetch_related("items").get(
                tracking_code=attrs["tracking_code"].upper(),
                email=attrs["email"],
            )
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError("Order not found.") from exc
        return attrs


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["paid", "fulfilled", "failed", "cancelled", "refunded"]
    )

    def validate_status(self, value):
        order = self.context["order"]
        allowed_transitions = {
            "pending": {"paid", "failed", "cancelled"},
            "paid": {"fulfilled", "refunded"},
            "fulfilled": {"refunded"},
            "failed": set(),
            "cancelled": set(),
            "refunded": set(),
        }
        if value not in allowed_transitions[order.status]:
            raise serializers.ValidationError(
                f"Cannot change status from {order.status} to {value}."
            )
        return value

    def save(self, **kwargs):
        order = self.context["order"]
        order.set_status(self.validated_data["status"])
        return order


class CheckoutInitializeSerializer(serializers.Serializer):
    tracking_code = serializers.CharField(max_length=32)
    email = serializers.EmailField()
    identity_number = serializers.RegexField(r"^\d{11}$")
    gsm_number = serializers.CharField(max_length=32)
    registration_address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=64)
    country = serializers.CharField(max_length=64, default="Turkey")
    zip_code = serializers.CharField(max_length=16, allow_blank=True, required=False)
    billing_contact_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    billing_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    billing_city = serializers.CharField(max_length=64, required=False, allow_blank=True)
    billing_country = serializers.CharField(max_length=64, required=False, allow_blank=True)
    billing_zip_code = serializers.CharField(max_length=16, required=False, allow_blank=True)
    shipping_contact_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    shipping_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    shipping_city = serializers.CharField(max_length=64, required=False, allow_blank=True)
    shipping_country = serializers.CharField(max_length=64, required=False, allow_blank=True)
    shipping_zip_code = serializers.CharField(max_length=16, required=False, allow_blank=True)

    def validate(self, attrs):
        tracking_code = attrs["tracking_code"].upper()
        try:
            order = Order.objects.prefetch_related("items__beat").get(
                tracking_code=tracking_code,
                email=attrs["email"],
            )
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError("Order not found.") from exc

        if order.status not in {"pending", "failed"}:
            raise serializers.ValidationError("Checkout can only be started for pending/failed orders.")

        attrs["order"] = order
        attrs["tracking_code"] = tracking_code
        return attrs


class PaymentConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)


class DeliveryAccessSerializer(serializers.Serializer):
    tracking_code = serializers.CharField(max_length=32)
    email = serializers.EmailField()

    def validate(self, attrs):
        tracking_code = attrs["tracking_code"].upper()
        try:
            order = Order.objects.prefetch_related("items__beat").get(
                tracking_code=tracking_code,
                email=attrs["email"],
            )
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError("Order not found.") from exc

        if not order.is_payment_successful:
            raise serializers.ValidationError("Payment is not completed for this order.")

        attrs["order"] = order
        return attrs
