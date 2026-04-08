import base64
import hashlib
import hmac
import json
import uuid
from urllib import error, request

from django.conf import settings


class IyzicoError(Exception):
    def __init__(self, message, payload=None, status_code=None):
        super().__init__(message)
        self.payload = payload or {}
        self.status_code = status_code


class IyzicoClient:
    CHECKOUT_INITIALIZE_PATH = "/payment/iyzipos/checkoutform/initialize/auth/ecom"
    CHECKOUT_RETRIEVE_PATH = "/payment/iyzipos/checkoutform/auth/ecom/detail"

    @property
    def api_key(self):
        return settings.IYZICO_API_KEY

    @property
    def secret_key(self):
        return settings.IYZICO_SECRET_KEY

    @property
    def base_url(self):
        return settings.IYZICO_BASE_URL.rstrip("/")

    @property
    def locale(self):
        return settings.IYZICO_LOCALE

    @property
    def timeout(self):
        return settings.IYZICO_TIMEOUT

    def _build_headers(self, path, payload_json):
        random_key = uuid.uuid4().hex
        signature_payload = f"{random_key}{path}{payload_json}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            signature_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization_raw = f"apiKey:{self.api_key}&randomKey:{random_key}&signature:{signature}"
        authorization = base64.b64encode(authorization_raw.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"IYZWSv2 {authorization}",
            "x-iyzi-rnd": random_key,
            "Content-Type": "application/json",
        }

    def _post(self, path, payload):
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        http_request = request.Request(
            url=f"{self.base_url}{path}",
            data=payload_json.encode("utf-8"),
            headers=self._build_headers(path, payload_json),
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body or "{}")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8")
            try:
                parsed_error = json.loads(error_body or "{}")
            except json.JSONDecodeError:
                parsed_error = {"raw": error_body}
            raise IyzicoError(
                parsed_error.get("errorMessage") or parsed_error.get("message") or "iyzico request failed.",
                payload=parsed_error,
                status_code=exc.code,
            ) from exc
        except error.URLError as exc:
            raise IyzicoError("Unable to reach iyzico.", payload={"error": str(exc)}) from exc

    def initialize_checkout_form(self, payload):
        return self._post(self.CHECKOUT_INITIALIZE_PATH, payload)

    def retrieve_checkout_form(self, token, conversation_id):
        return self._post(
            self.CHECKOUT_RETRIEVE_PATH,
            {
                "locale": self.locale,
                "conversationId": conversation_id,
                "token": token,
            },
        )

    def validate_hpp_webhook_signature(self, payload, signature):
        message = (
            f"{self.secret_key}"
            f"{payload.get('iyziEventType', '')}"
            f"{payload.get('iyziPaymentId', '')}"
            f"{payload.get('token', '')}"
            f"{payload.get('paymentConversationId', '')}"
            f"{payload.get('status', '')}"
        )
        expected = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")


iyzico_client = IyzicoClient()
