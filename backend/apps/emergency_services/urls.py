from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AmbulanceVehicleViewSet, EmergencyProviderViewSet, HealthcareFacilityViewSet


router = DefaultRouter()
router.register("providers", EmergencyProviderViewSet, basename="emergency-provider")
router.register("facilities", HealthcareFacilityViewSet, basename="healthcare-facility")
router.register("vehicles", AmbulanceVehicleViewSet, basename="ambulance-vehicle")

urlpatterns = [path("", include(router.urls))]