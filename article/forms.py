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
            "license_type",
            "file",
        ]
