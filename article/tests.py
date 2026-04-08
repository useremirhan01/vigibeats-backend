from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Beat, BeatLicense


class BeatLicenseModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.producer = user_model.objects.create_user(
            username="producer",
            password="testpass123",
            role="producer",
        )
        self.beat = Beat.objects.create(
            title="License Test Beat",
            description="Test",
            price=Decimal("100.00"),
            premium_price=Decimal("180.00"),
            exclusive_price=Decimal("400.00"),
            producer=self.producer,
        )

    def test_premium_license_cannot_be_cheaper_than_basic(self):
        BeatLicense.objects.create(
            beat=self.beat,
            license_type="basic",
            title="Basic",
            price=Decimal("100.00"),
            distribution_limit=5000,
            streaming_limit=100000,
            max_purchasers=None,
        )

        with self.assertRaises(ValidationError):
            BeatLicense.objects.create(
                beat=self.beat,
                license_type="premium",
                title="Premium",
                price=Decimal("90.00"),
                allow_wav=True,
                distribution_limit=50000,
                streaming_limit=500000,
            )

    def test_exclusive_license_requires_single_buyer_rules(self):
        with self.assertRaises(ValidationError):
            BeatLicense.objects.create(
                beat=self.beat,
                license_type="exclusive",
                title="Exclusive",
                price=Decimal("500.00"),
                max_purchasers=2,
            )

    def test_beat_reads_price_from_license_model(self):
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

        self.assertEqual(self.beat.get_price_for_license("premium"), Decimal("180.00"))
