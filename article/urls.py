
from django.contrib import admin
from django.urls import path
from article import views
from .import views
from django.conf import settings
from rest_framework.routers import DefaultRouter
from .views import BeatViewSet

from django.conf.urls.static import static
app_name = "article"

router = DefaultRouter()
router.register("beats", BeatViewSet, basename="beat")

urlpatterns = router.urls

