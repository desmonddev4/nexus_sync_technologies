from django.urls import path

from .views import DeviceHeartbeatView


urlpatterns = [
    path("devices/heartbeat/", DeviceHeartbeatView.as_view(), name="device-heartbeat"),
]