from rest_framework import serializers
from .models import Beat


class BeatSerializer(serializers.ModelSerializer):
    """
    Beat modelini JSON formatına çeviren serializer.
    """
    producer_name = serializers.CharField(source="producer.username", read_only=True)

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
            "license_type",
            "file",
            "watermark_file",
            "producer_name",
            "created_at",
            "updated_at",
        ]
