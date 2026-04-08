from django import forms
from .models import Beat


class BeatForm(forms.ModelForm):
    class Meta:
        model = Beat
        fields = [
            "title",
            "description",
            "bpm",
            "key",
            "tags",
            "price",
            "premium_price",
            "exclusive_price",
            "license_type",
            "audio_file",
            "cover_image",
        ]
