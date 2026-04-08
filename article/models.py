from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal


def get_upload_path(instance, filename):
    article = getattr(instance, "article", None)
    author_id = getattr(getattr(article, "author", None), "id", "unknown")
    article_id = getattr(article, "id", "unknown")
    return f"music/user_{author_id}/{article_id}/{filename}"


class Beat(models.Model):
    LICENSE_CHOICES = [
        ("basic", "Basic License"),
        ("premium", "Premium License"),
        ("exclusive", "Exclusive License"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    bpm = models.PositiveIntegerField(default=120)
    key = models.CharField(max_length=10, blank=True)
    tags = models.JSONField(default=list, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    premium_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    exclusive_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    license_type = models.CharField(max_length=20, choices=LICENSE_CHOICES, default="basic")
    exclusive_available = models.BooleanField(default=True)

    audio_file = models.FileField(upload_to="beats/", null=True, blank=True)
    cover_image = models.ImageField(upload_to="covers/", null=True, blank=True)

    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="beats"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.license_type})"

    def get_license(self, license_type, active_only=True):
        queryset = self.licenses.all()
        if active_only:
            queryset = queryset.filter(is_active=True)

        try:
            return queryset.get(license_type=license_type)
        except BeatLicense.DoesNotExist:
            return None

    def get_price_for_license(self, license_type):
        license_obj = self.get_license(license_type)
        if license_obj is not None:
            return license_obj.price

        price_map = {
            "basic": self.price,
            "premium": self.premium_price if self.premium_price is not None else self.price,
            "exclusive": self.exclusive_price if self.exclusive_price is not None else self.price,
        }
        return price_map[license_type]

    def is_license_available(self, license_type):
        license_obj = self.get_license(license_type)
        if license_obj is not None:
            return license_obj.is_available_for_purchase
        if license_type == "exclusive":
            return self.exclusive_available
        return True

    def clean(self):
        if self.premium_price is not None and self.premium_price < self.price:
            raise ValidationError({"premium_price": "Premium price cannot be lower than basic price."})
        if self.exclusive_price is not None:
            floor = self.premium_price if self.premium_price is not None else self.price
            if self.exclusive_price < floor:
                raise ValidationError(
                    {"exclusive_price": "Exclusive price cannot be lower than premium/basic price."}
                )


class BeatLicense(models.Model):
    LICENSE_BASIC = "basic"
    LICENSE_PREMIUM = "premium"
    LICENSE_EXCLUSIVE = "exclusive"
    LICENSE_CHOICES = [
        (LICENSE_BASIC, "Basic License"),
        (LICENSE_PREMIUM, "Premium License"),
        (LICENSE_EXCLUSIVE, "Exclusive License"),
    ]

    beat = models.ForeignKey(Beat, on_delete=models.CASCADE, related_name="licenses")
    license_type = models.CharField(max_length=20, choices=LICENSE_CHOICES)
    title = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    allow_wav = models.BooleanField(default=False)
    allow_stems = models.BooleanField(default=False)
    commercial_use = models.BooleanField(default=True)
    distribution_limit = models.PositiveIntegerField(null=True, blank=True)
    streaming_limit = models.PositiveIntegerField(null=True, blank=True)
    max_purchasers = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for unlimited purchases.",
    )
    requires_credit = models.BooleanField(default=True)
    sold = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["beat", "license_type"],
                name="unique_license_type_per_beat",
            )
        ]
        ordering = ["price", "id"]

    def __str__(self):
        return f"{self.beat.title} - {self.get_license_type_display()}"

    @property
    def is_exclusive(self):
        return self.license_type == self.LICENSE_EXCLUSIVE

    @property
    def is_available_for_purchase(self):
        if not self.is_active:
            return False
        if self.is_exclusive:
            return not self.sold and self.beat.exclusive_available
        if self.max_purchasers is None:
            return True
        return self.purchase_count < self.max_purchasers

    @property
    def purchase_count(self):
        return self.order_items.exclude(order__status__in=["failed", "cancelled", "refunded"]).count()

    def clean(self):
        errors = {}

        if self.price <= Decimal("0.00"):
            errors["price"] = "License price must be greater than zero."

        if self.is_exclusive:
            if self.max_purchasers not in (None, 1):
                errors["max_purchasers"] = "Exclusive license can only have one purchaser."
            if self.distribution_limit is not None:
                errors["distribution_limit"] = "Exclusive license cannot have a distribution limit."
            if self.streaming_limit is not None:
                errors["streaming_limit"] = "Exclusive license cannot have a streaming limit."
        else:
            if self.sold:
                errors["sold"] = "Only the exclusive license can be marked as sold."

        siblings = BeatLicense.objects.filter(beat=self.beat).exclude(pk=self.pk)
        basic_license = next(
            (license_obj for license_obj in siblings if license_obj.license_type == self.LICENSE_BASIC),
            None,
        )
        premium_license = next(
            (license_obj for license_obj in siblings if license_obj.license_type == self.LICENSE_PREMIUM),
            None,
        )

        if self.license_type == self.LICENSE_PREMIUM and basic_license and self.price < basic_license.price:
            errors["price"] = "Premium license price cannot be lower than basic license price."

        if self.license_type == self.LICENSE_EXCLUSIVE:
            comparison_price = premium_license.price if premium_license else (
                basic_license.price if basic_license else None
            )
            if comparison_price is not None and self.price < comparison_price:
                errors["price"] = "Exclusive license price cannot be lower than premium/basic license price."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        if self.is_exclusive:
            beat = self.beat
            beat.exclusive_available = not self.sold and self.is_active
            Beat.objects.filter(pk=beat.pk).update(exclusive_available=beat.exclusive_available)




class Comment(models.Model):
    beat = models.ForeignKey(Beat, on_delete=models.CASCADE, verbose_name="Makale", related_name="comments")
    comment_author = models.CharField(max_length=50, verbose_name="İsim")
    comment_content = models.CharField(max_length=200, verbose_name="Yorum")
    comment_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.comment_content

    class Meta:
        ordering = ['-comment_date']
