from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import BeatViewSet, add_beat, dashboard

app_name = "article"

router = DefaultRouter()
router.register("beats", BeatViewSet, basename="beat")
#router.register("licenses", LicenseViewSet, basename="license")
#router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("beats/add/", add_beat, name="add_beat"),
] + router.urls
