from django.contrib import admin

from .models import AmbulanceVehicle, EmergencyProvider, HealthcareFacility


@admin.register(EmergencyProvider)
class EmergencyProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_type", "verification_status", "verified_at")
    list_filter = ("provider_type", "verification_status")
    search_fields = ("name", "dispatch_phone_number", "general_phone_number")


@admin.register(HealthcareFacility)
class HealthcareFacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "facility_type", "verification_status", "is_active")
    list_filter = ("facility_type", "verification_status", "is_active")
    search_fields = ("name", "address", "phone_number")


@admin.register(AmbulanceVehicle)
class AmbulanceVehicleAdmin(admin.ModelAdmin):
    list_display = ("vehicle_identifier", "provider", "availability", "data_source", "location_updated_at")
    list_filter = ("availability", "data_source", "provider")
    search_fields = ("vehicle_identifier", "provider__name")