from rest_framework import serializers
from .models import Beat, BeatLicense


class BeatLicenseSerializer(serializers.ModelSerializer):
    is_available_for_purchase = serializers.BooleanField(read_only=True)

    class Meta:
        model = BeatLicense
        fields = [
            "id",
            "license_type",
            "title",
            "price",
            "is_active",
            "allow_wav",
            "allow_stems",
            "commercial_use",
            "distribution_limit",
            "streaming_limit",
            "max_purchasers",
            "requires_credit",
            "sold",
            "is_available_for_purchase",
        ]


class BeatSerializer(serializers.ModelSerializer):
    """
    Beat modelini JSON formatına çeviren serializer.
    """
    producer_name = serializers.CharField(source="producer.username", read_only=True)
    license_prices = serializers.SerializerMethodField()
    licenses = BeatLicenseSerializer(many=True, read_only=True)

    class Meta:
        model = Beat
        fields = [
            "id",
            "title",
            "description",
            "bpm",
            "key",
            "tags",
            "price",
            "premium_price",
            "exclusive_price",
            "license_type",
            "exclusive_available",
            "audio_file",
            "cover_image",
            "producer_name",
            "license_prices",
            "licenses",
            "created_at",
            "updated_at",
        ]

    def get_license_prices(self, obj):
        return {
            "basic": obj.get_price_for_license("basic"),
            "premium": obj.get_price_for_license("premium"),
            "exclusive": obj.get_price_for_license("exclusive"),
        }
