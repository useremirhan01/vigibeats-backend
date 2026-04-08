from django.contrib import admin
from .models import Beat, BeatLicense


class BeatLicenseInline(admin.TabularInline):
    model = BeatLicense
    extra = 0


@admin.register(Beat)
class BeatAdmin(admin.ModelAdmin):
    inlines = [BeatLicenseInline]
    list_display = ("title", "producer", "license_type", "price", "exclusive_available", "created_at")
    list_filter = ("license_type", "exclusive_available", "created_at")
    search_fields = ("title", "producer__username")


@admin.register(BeatLicense)
class BeatLicenseAdmin(admin.ModelAdmin):
    list_display = ("beat", "license_type", "price", "is_active", "sold")
    list_filter = ("license_type", "is_active", "sold")
    search_fields = ("beat__title", "title")
