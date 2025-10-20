from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ("producer", "Producer"),
        ("artist", "Artist"),
        ("admin", "Admin"),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="artist")
    email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"
