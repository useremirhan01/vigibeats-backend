from rest_framework import serializers
from .models import Order, OrderItem
from article.models import Beat


class OrderItemCreateSerializer(serializers.Serializer):
    beat_id = serializers.IntegerField()
    selected_license = serializers.ChoiceField(choices=["basic", "premium", "exclusive"])
    quantity = serializers.IntegerField(min_value=1, default=1)


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "beat",
            "beat_title",
            "selected_license",
            "unit_price",
            "quantity",
            "line_total",
        ]

    def get_line_total(self, obj):
        return obj.line_total


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = "__all__"


class OrderCreateSerializer(serializers.Serializer):
    beat_id = serializers.IntegerField()
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    license_type = serializers.ChoiceField(choices=["basic", "premium", "exclusive"])

    def create(self, validated_data):
        request = self.context["request"]
        beat = Beat.objects.get(id=validated_data["beat_id"])

        user = request.user if request.user.is_authenticated else None

        order = Order.objects.create(
            user=user,
            beat=beat,
            full_name=validated_data["full_name"],
            email=validated_data["email"],
            license_type=validated_data["license_type"],
            amount=beat.price,
            status="pending",
            payment_provider="mock_iyzico"
        )
        return order