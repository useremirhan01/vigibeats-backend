from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from rest_framework import permissions, viewsets

from .forms import BeatForm
from .models import Beat
from .serializers import BeatSerializer


def index(request):
    return render(request, "index.html", {})


def about(request):
    return render(request, "about.html", {})


@login_required
def dashboard(request):
    beats = Beat.objects.filter(producer=request.user)
    return render(request, "dashboard.html", {"beats": beats})


class IsProducerOrReadOnly(permissions.BasePermission):
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


@login_required
def add_beat(request):
    form = BeatForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            beat = form.save(commit=False)
            beat.producer = request.user
            beat.save()
            messages.success(request, "Beat basariyla yuklendi.")
            return redirect("article:dashboard")
        messages.error(request, "Beat yuklenemedi. Form alanlarini kontrol edin.")

    return render(request, "addarticle.html", {"form": form})
