from django.conf import settings
from django.db import models
import os

def get_upload_path(instance, filename):
    return f'music/user_{instance.article.author.id}/{instance.article.id}/{filename}'

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
    license_type = models.CharField(max_length=20, choices=LICENSE_CHOICES, default="basic")

    file = models.FileField(upload_to="beats/originals/")
    watermark_file = models.FileField(upload_to="beats/watermarks/", blank=True, null=True)

    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="beats"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.license_type})"




class Comment(models.Model):
    beat = models.ForeignKey(Beat, on_delete=models.CASCADE, verbose_name="Makale", related_name="comments")
    comment_author = models.CharField(max_length=50, verbose_name="İsim")
    comment_content = models.CharField(max_length=200, verbose_name="Yorum")
    comment_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.comment_content

    class Meta:
        ordering = ['-comment_date']
