from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .iyzico import IyzicoError, iyzico_client
from .models import Order
from .serializers import (
    CheckoutInitializeSerializer,
    DeliveryAccessSerializer,
    DeliveryItemSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    OrderStatusUpdateSerializer,
    OrderTrackingSerializer,
    PaymentConfirmSerializer,
)


class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or (request.user.is_authenticated and obj.user == request.user)


def split_full_name(full_name):
    pieces = [piece for piece in full_name.strip().split() if piece]
    if not pieces:
        return "Guest", "Buyer"
    if len(pieces) == 1:
        return pieces[0], pieces[0]
    return pieces[0], " ".join(pieces[1:])


def build_checkout_payload(order, callback_url):
    first_name, last_name = split_full_name(order.full_name)
    buyer = order.buyer_data
    billing_address = order.billing_address
    shipping_address = order.shipping_address

    return {
        "locale": iyzico_client.locale,
        "conversationId": order.tracking_code,
        "price": str(order.amount),
        "paidPrice": str(order.amount),
        "currency": order.currency,
        "basketId": order.tracking_code,
        "paymentGroup": "PRODUCT",
        "callbackUrl": callback_url,
        "enabledInstallments": [1],
        "buyer": {
            "id": str(order.user_id or order.tracking_code),
            "name": buyer.get("name", first_name),
            "surname": buyer.get("surname", last_name),
            "gsmNumber": buyer["gsm_number"],
            "email": order.email,
            "identityNumber": buyer["identity_number"],
            "lastLoginDate": buyer["last_login_date"],
            "registrationDate": buyer["registration_date"],
            "registrationAddress": buyer["registration_address"],
            "ip": buyer["ip"],
            "city": buyer["city"],
            "country": buyer["country"],
            "zipCode": buyer.get("zip_code", ""),
        },
        "shippingAddress": {
            "contactName": shipping_address["contact_name"],
            "city": shipping_address["city"],
            "country": shipping_address["country"],
            "address": shipping_address["address"],
            "zipCode": shipping_address.get("zip_code", ""),
        },
        "billingAddress": {
            "contactName": billing_address["contact_name"],
            "city": billing_address["city"],
            "country": billing_address["country"],
            "address": billing_address["address"],
            "zipCode": billing_address.get("zip_code", ""),
        },
        "basketItems": [
            {
                "id": str(item.id),
                "name": item.beat_title,
                "category1": "Beat",
                "category2": item.selected_license,
                "itemType": "VIRTUAL",
                "price": str(item.unit_price),
            }
            for item in order.items.all()
        ],
    }


def serialize_delivery(order, request):
    order.issue_delivery_token()
    serializer = DeliveryItemSerializer(
        order.items.select_related("beat").all(),
        many=True,
        context={"request": request, "delivery_token": order.delivery_token},
    )
    return {
        "delivery_token": order.delivery_token,
        "delivery_token_expires_at": order.delivery_token_expires_at,
        "items": serializer.data,
    }


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.prefetch_related("items").order_by("-created_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_staff:
            return queryset
        if self.request.user.is_authenticated:
            return queryset.filter(user=self.request.user)
        return queryset.none()

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        if self.action == "track":
            return OrderTrackingSerializer
        if self.action in {"mock_pay", "advance_status"}:
            return OrderStatusUpdateSerializer
        return OrderSerializer

    def get_permissions(self):
        if self.action in {"create", "track"}:
            return [AllowAny()]
        if self.action in {"mock_pay", "advance_status"}:
            return [IsAdminUser()]
        return [IsOwnerOrAdmin()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        response_serializer = OrderSerializer(order, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def track(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data["order"]
        response_serializer = OrderSerializer(order, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def mock_pay(self, request, pk=None):
        order = self.get_object()
        serializer = self.get_serializer(
            data={"status": "fulfilled"},
            context={"order": order},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Mock payment successful",
                "order_id": order.id,
                "tracking_code": order.tracking_code,
                "status": order.status,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def advance_status(self, request, pk=None):
        order = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={"order": order},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = OrderSerializer(order, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class CheckoutInitializeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CheckoutInitializeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data["order"]

        first_name, last_name = split_full_name(order.full_name)
        ip_address = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "127.0.0.1"))
        if "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()

        order.buyer_data = {
            "name": first_name,
            "surname": last_name,
            "identity_number": serializer.validated_data["identity_number"],
            "gsm_number": serializer.validated_data["gsm_number"],
            "registration_address": serializer.validated_data["registration_address"],
            "city": serializer.validated_data["city"],
            "country": serializer.validated_data["country"],
            "zip_code": serializer.validated_data.get("zip_code", ""),
            "last_login_date": order.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "registration_date": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ip": ip_address,
        }
        order.billing_address = {
            "contact_name": serializer.validated_data.get("billing_contact_name") or order.full_name,
            "address": serializer.validated_data.get("billing_address")
            or serializer.validated_data["registration_address"],
            "city": serializer.validated_data.get("billing_city") or serializer.validated_data["city"],
            "country": serializer.validated_data.get("billing_country") or serializer.validated_data["country"],
            "zip_code": serializer.validated_data.get("billing_zip_code")
            or serializer.validated_data.get("zip_code", ""),
        }
        order.shipping_address = {
            "contact_name": serializer.validated_data.get("shipping_contact_name") or order.full_name,
            "address": serializer.validated_data.get("shipping_address")
            or serializer.validated_data["registration_address"],
            "city": serializer.validated_data.get("shipping_city") or serializer.validated_data["city"],
            "country": serializer.validated_data.get("shipping_country") or serializer.validated_data["country"],
            "zip_code": serializer.validated_data.get("shipping_zip_code")
            or serializer.validated_data.get("zip_code", ""),
        }

        callback_url = settings.IYZICO_CALLBACK_URL or request.build_absolute_uri(
            reverse("orders-payment-confirm")
        )

        try:
            response_payload = iyzico_client.initialize_checkout_form(
                build_checkout_payload(order, callback_url)
            )
        except IyzicoError as exc:
            return Response(
                {"detail": str(exc), "provider_payload": exc.payload},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        order.payment_metadata = {
            **order.payment_metadata,
            "token": response_payload.get("token", ""),
            "checkout_form_content": response_payload.get("checkoutFormContent", ""),
            "payment_page_url": response_payload.get("paymentPageUrl", ""),
            "raw_initialize_response": response_payload,
        }
        order.save(
            update_fields=[
                "buyer_data",
                "billing_address",
                "shipping_address",
                "payment_metadata",
                "updated_at",
            ]
        )

        return Response(
            {
                "tracking_code": order.tracking_code,
                "token": response_payload.get("token"),
                "payment_page_url": response_payload.get("paymentPageUrl"),
                "checkout_form_content": response_payload.get("checkoutFormContent"),
                "status": response_payload.get("status"),
            },
            status=status.HTTP_200_OK,
        )


class PaymentConfirmView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_token(self, request):
        return request.data.get("token") or request.query_params.get("token")

    def post(self, request):
        token = self.get_token(request)
        serializer = PaymentConfirmSerializer(data={"token": token})
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        order = get_object_or_404(
            Order.objects.prefetch_related("items__beat"),
            payment_metadata__token=token,
        )

        try:
            response_payload = iyzico_client.retrieve_checkout_form(token, order.tracking_code)
        except IyzicoError as exc:
            return Response(
                {"detail": str(exc), "provider_payload": exc.payload},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        success = response_payload.get("paymentStatus") == "SUCCESS" and response_payload.get("status") == "success"
        order.mark_payment_result(response_payload, success=success)

        response_data = {
            "order": OrderSerializer(order, context={"request": request}).data,
            "provider_status": response_payload.get("paymentStatus"),
            "payment_id": response_payload.get("paymentId"),
        }
        if success:
            response_data["delivery"] = serialize_delivery(order, request)
        return Response(response_data, status=status.HTTP_200_OK)

    def get(self, request):
        return self.post(request)


class PaymentWebhookView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        signature = request.headers.get("X-IYZ-SIGNATURE-V3", "")
        payload = request.data

        if not iyzico_client.validate_hpp_webhook_signature(payload, signature):
            return Response({"detail": "Invalid webhook signature."}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, tracking_code=payload.get("paymentConversationId", "").upper())
        order.mark_payment_result(payload, success=payload.get("status") == "SUCCESS")
        return Response({"received": True, "tracking_code": order.tracking_code}, status=status.HTTP_200_OK)


class DeliveryAccessView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DeliveryAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data["order"]
        return Response(serialize_delivery(order, request), status=status.HTTP_200_OK)


class DeliveryDownloadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token, item_id):
        order = get_object_or_404(Order.objects.prefetch_related("items__beat"), delivery_token=token)
        if not order.has_valid_delivery_token(token):
            raise Http404("Delivery token is invalid or expired.")

        item = get_object_or_404(order.items.select_related("beat"), id=item_id)
        if not item.beat.audio_file:
            raise Http404("Digital file is not available for this item.")

        filename = Path(item.beat.audio_file.name).name or f"{item.beat_title}.mp3"
        return FileResponse(item.beat.audio_file.open("rb"), as_attachment=True, filename=filename)
