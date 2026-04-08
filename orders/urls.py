from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CheckoutInitializeView,
    DeliveryAccessView,
    DeliveryDownloadView,
    OrderViewSet,
    PaymentConfirmView,
    PaymentWebhookView,
)

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")

urlpatterns = [
    path("orders/checkout/", CheckoutInitializeView.as_view(), name="orders-checkout"),
    path("orders/payment/confirm/", PaymentConfirmView.as_view(), name="orders-payment-confirm"),
    path("orders/payment/webhook/", PaymentWebhookView.as_view(), name="orders-payment-webhook"),
    path("orders/delivery/", DeliveryAccessView.as_view(), name="orders-delivery-access"),
    path(
        "orders/delivery/<str:token>/items/<int:item_id>/download/",
        DeliveryDownloadView.as_view(),
        name="orders-delivery-download",
    ),
] + router.urls
