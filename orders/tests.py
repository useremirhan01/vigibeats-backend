import hashlib
import hmac
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from article.models import Beat, BeatLicense
from .models import Order


@override_settings(
    IYZICO_API_KEY="sandbox-api-key",
    IYZICO_SECRET_KEY="sandbox-secret",
    IYZICO_BASE_URL="https://sandbox-api.iyzipay.com",
)
class OrderApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.producer = user_model.objects.create_user(
            username="producer",
            password="testpass123",
            role="producer",
        )
        self.customer = user_model.objects.create_user(
            username="customer",
            password="testpass123",
            role="artist",
        )
        self.other_customer = user_model.objects.create_user(
            username="othercustomer",
            password="testpass123",
            role="artist",
        )
        self.admin = user_model.objects.create_superuser(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
        )

        self.audio = SimpleUploadedFile("night-drive.mp3", b"fake-mp3-data", content_type="audio/mpeg")
        self.beat = Beat.objects.create(
            title="Night Drive",
            description="Synth beat",
            bpm=140,
            key="Am",
            price=Decimal("100.00"),
            premium_price=Decimal("180.00"),
            exclusive_price=Decimal("450.00"),
            audio_file=self.audio,
            producer=self.producer,
        )
        BeatLicense.objects.create(
            beat=self.beat,
            license_type="basic",
            title="Basic",
            price=Decimal("100.00"),
            distribution_limit=5000,
            streaming_limit=100000,
        )
        BeatLicense.objects.create(
            beat=self.beat,
            license_type="premium",
            title="Premium",
            price=Decimal("180.00"),
            allow_wav=True,
            distribution_limit=50000,
            streaming_limit=500000,
        )
        self.exclusive_license = BeatLicense.objects.create(
            beat=self.beat,
            license_type="exclusive",
            title="Exclusive",
            price=Decimal("450.00"),
            allow_wav=True,
            allow_stems=True,
            requires_credit=False,
        )

    def create_order(self, **overrides):
        payload = {
            "full_name": "Guest Buyer",
            "email": "guest@example.com",
            "items": [
                {
                    "beat_id": self.beat.id,
                    "selected_license": "premium",
                    "quantity": 2,
                }
            ],
        }
        payload.update(overrides)
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Order.objects.get(id=response.data["id"])

    def test_guest_can_create_order_with_license_pricing(self):
        order = self.create_order()
        self.assertEqual(order.amount, Decimal("360.00"))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().selected_license, "premium")
        self.assertTrue(order.tracking_code)

    def test_exclusive_order_marks_beat_unavailable(self):
        response = self.client.post(
            "/api/orders/",
            {
                "full_name": "Exclusive Buyer",
                "email": "exclusive@example.com",
                "beat_id": self.beat.id,
                "license_type": "exclusive",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.beat.refresh_from_db()
        self.exclusive_license.refresh_from_db()
        self.assertFalse(self.beat.exclusive_available)
        self.assertTrue(self.exclusive_license.sold)
        self.assertFalse(self.exclusive_license.is_active)

    def test_guest_can_track_order_by_tracking_code_and_email(self):
        order = self.create_order()
        response = self.client.post(
            "/api/orders/track/",
            {
                "tracking_code": order.tracking_code.lower(),
                "email": order.email,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tracking_code"], order.tracking_code)
        self.assertEqual(len(response.data["items"]), 1)

    def test_order_creation_falls_back_to_beat_prices_without_license_rows(self):
        legacy_beat = Beat.objects.create(
            title="Legacy Beat",
            description="Fallback pricing",
            price=Decimal("90.00"),
            premium_price=Decimal("150.00"),
            exclusive_price=Decimal("350.00"),
            producer=self.producer,
        )

        response = self.client.post(
            "/api/orders/",
            {
                "full_name": "Legacy Buyer",
                "email": "legacy@example.com",
                "beat_id": legacy_beat.id,
                "license_type": "premium",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.amount, Decimal("150.00"))
        self.assertIsNone(order.items.first().beat_license)

    @patch("orders.views.iyzico_client.initialize_checkout_form")
    def test_checkout_endpoint_initializes_iyzico_session(self, mock_initialize):
        order = self.create_order()
        mock_initialize.return_value = {
            "status": "success",
            "token": "cf-token-123",
            "paymentPageUrl": "https://sandbox-cpp.iyzipay.com/mock",
            "checkoutFormContent": "<form></form>",
        }

        response = self.client.post(
            "/api/orders/checkout/",
            {
                "tracking_code": order.tracking_code,
                "email": order.email,
                "identity_number": "11111111111",
                "gsm_number": "+905555555555",
                "registration_address": "Istanbul",
                "city": "Istanbul",
                "country": "Turkey",
                "zip_code": "34000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.payment_metadata["token"], "cf-token-123")
        self.assertEqual(response.data["payment_page_url"], "https://sandbox-cpp.iyzipay.com/mock")

    @patch("orders.views.iyzico_client.retrieve_checkout_form")
    def test_payment_confirmation_fulfills_order_and_returns_delivery_links(self, mock_retrieve):
        order = self.create_order()
        order.payment_metadata = {"token": "cf-token-123"}
        order.save(update_fields=["payment_metadata"])
        mock_retrieve.return_value = {
            "status": "success",
            "paymentStatus": "SUCCESS",
            "paymentId": "payment-1",
            "conversationId": order.tracking_code,
            "token": "cf-token-123",
        }

        response = self.client.post(
            "/api/orders/payment/confirm/",
            {"token": "cf-token-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "fulfilled")
        self.assertTrue(order.delivery_token)
        self.assertEqual(response.data["provider_status"], "SUCCESS")
        self.assertEqual(len(response.data["delivery"]["items"]), 1)

    def test_delivery_access_and_download_require_successful_payment(self):
        order = self.create_order()
        order.set_status("fulfilled")

        access_response = self.client.post(
            "/api/orders/delivery/",
            {"tracking_code": order.tracking_code, "email": order.email},
            format="json",
        )
        self.assertEqual(access_response.status_code, status.HTTP_200_OK)
        download_url = access_response.data["items"][0]["download_url"]

        download_response = self.client.get(download_url)
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment;", download_response["Content-Disposition"])

    def test_webhook_rejects_invalid_signature(self):
        order = self.create_order()
        response = self.client.post(
            "/api/orders/payment/webhook/",
            {
                "paymentConversationId": order.tracking_code,
                "status": "SUCCESS",
                "iyziEventType": "CHECKOUT_FORM_AUTH",
                "iyziPaymentId": "1",
                "token": "cf-token-123",
            },
            format="json",
            HTTP_X_IYZ_SIGNATURE_V3="invalid",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_webhook_marks_order_fulfilled_with_valid_signature(self):
        order = self.create_order()
        payload = {
            "paymentConversationId": order.tracking_code,
            "status": "SUCCESS",
            "iyziEventType": "CHECKOUT_FORM_AUTH",
            "iyziPaymentId": "1",
            "token": "cf-token-123",
        }
        signature_base = (
            "sandbox-secret"
            f"{payload['iyziEventType']}"
            f"{payload['iyziPaymentId']}"
            f"{payload['token']}"
            f"{payload['paymentConversationId']}"
            f"{payload['status']}"
        )
        signature = hmac.new(
            b"sandbox-secret",
            signature_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        response = self.client.post(
            "/api/orders/payment/webhook/",
            payload,
            format="json",
            HTTP_X_IYZ_SIGNATURE_V3=signature,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "fulfilled")

    def test_authenticated_user_only_sees_own_orders(self):
        own_order = Order.objects.create(
            user=self.customer,
            full_name="Customer",
            email="customer@example.com",
        )
        other_order = Order.objects.create(
            user=self.other_customer,
            full_name="Other",
            email="other@example.com",
        )

        self.client.force_authenticate(self.customer)
        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data}
        self.assertIn(own_order.id, returned_ids)
        self.assertNotIn(other_order.id, returned_ids)

    def test_admin_can_mark_order_paid(self):
        order = self.create_order()
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"/api/orders/{order.id}/mock_pay/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "fulfilled")
        self.assertIsNotNone(order.paid_at)
        self.assertIsNotNone(order.fulfilled_at)
