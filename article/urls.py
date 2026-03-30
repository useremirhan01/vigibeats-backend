from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import BeatViewSet, dashboard

app_name = "article"

router = DefaultRouter()
router.register("beats", BeatViewSet, basename="beat")
#router.register("licenses", LicenseViewSet, basename="license")
#router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
] + router.urls