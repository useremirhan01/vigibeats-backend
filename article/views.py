from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from rest_framework import viewsets, permissions
from .models import Beat
from .serializers import BeatSerializer


# -----------------------
# 1. HTML Sayfaları
# -----------------------

def index(request):
    """Ana sayfa"""
    return render(request, "index.html", {})


def about(request):
    """Hakkında sayfası"""
    return render(request, "about.html", {})


@login_required
def dashboard(request):
    """Kullanıcının yüklediği beatleri listeler"""
    beats = Beat.objects.filter(producer=request.user)
    return render(request, "dashboard.html", {"beats": beats})


# -----------------------
# 2. Beat CRUD API (DRF)
# -----------------------

class IsProducerOrReadOnly(permissions.BasePermission):
    """
    Producer rolündeki kullanıcılar kendi beatlerini oluşturabilir, düzenleyebilir.
    Diğer herkes sadece görebilir.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and getattr(request.user, "role", None) == "producer"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.producer == request.user


class BeatViewSet(viewsets.ModelViewSet):
    queryset = Beat.objects.all().order_by("-created_at")
    serializer_class = BeatSerializer
    permission_classes = [IsProducerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(producer=self.request.user)


# -----------------------
# 3. Beat Ekleme (HTML form sürümü)
# -----------------------

@login_required
def add_beat(request):
    """
    Basit HTML formu üzerinden beat yükleme (şimdilik yerel dosya sistemi).
    """
    if request.method == "POST":
        title = request.POST.get("title")
        bpm = request.POST.get("bpm")
        key = request.POST.get("key")
        license_type = request.POST.get("license_type")
        price = request.POST.get("price")
        file = request.FILES.get("file")

        Beat.objects.create(
            title=title,
            bpm=bpm or 120,
            key=key or "",
            license_type=license_type or "basic",
            price=price or 0.0,
            file=file,
            producer=request.user,
        )
        messages.success(request, "Beat başarıyla yüklendi.")
        return redirect("dashboard")

    return render(request, "addbeat.html")
