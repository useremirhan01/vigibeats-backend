from django.contrib import admin
from .models import Beat


@admin.register(Beat)
class BeatAdmin(admin.ModelAdmin):
    list_display = ("title", "producer", "license_type", "price", "created_at")
    list_filter = ("license_type", "created_at")
    search_fields = ("title", "producer__username")
