from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer, OrderCreateSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def get_permissions(self):
        return [AllowAny()]

    @action(detail=True, methods=["post"])
    def mock_pay(self, request, pk=None):
        order = self.get_object()
        order.status = "paid"
        order.save(update_fields=["status"])

        return Response({
            "message": "Mock payment successful",
            "order_id": order.id,
            "status": order.status
        }, status=status.HTTP_200_OK)