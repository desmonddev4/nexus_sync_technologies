from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
	AmbulanceVehicleViewSet,
	EmergencyProviderViewSet,
	FacilityDirectoryManagementViewSet,
	HealthcareFacilityViewSet,
	ProviderDirectoryManagementViewSet,
	VehicleDirectoryManagementViewSet,
)


router = DefaultRouter()
router.register("providers", EmergencyProviderViewSet, basename="emergency-provider")
router.register("facilities", HealthcareFacilityViewSet, basename="healthcare-facility")
router.register("vehicles", AmbulanceVehicleViewSet, basename="ambulance-vehicle")
router.register("directory/providers", ProviderDirectoryManagementViewSet, basename="directory-provider")
router.register("directory/facilities", FacilityDirectoryManagementViewSet, basename="directory-facility")
router.register("directory/vehicles", VehicleDirectoryManagementViewSet, basename="directory-vehicle")

urlpatterns = [path("", include(router.urls))]