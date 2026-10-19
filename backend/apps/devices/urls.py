from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceHeartbeatView, DeviceRegistryViewSet

router = DefaultRouter()
router.register("device-registry", DeviceRegistryViewSet, basename="device-registry")


urlpatterns = [
    path("devices/heartbeat/", DeviceHeartbeatView.as_view(), name="device-heartbeat"),
    path("", include(router.urls)),
]