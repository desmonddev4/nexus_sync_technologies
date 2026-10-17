from django.contrib import admin

from .models import Device, DeviceCredential


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("device_identifier", "device_type", "patient", "status", "last_seen_at")
    list_filter = ("device_type", "status")
    search_fields = ("device_identifier", "patient__full_name")


@admin.register(DeviceCredential)
class DeviceCredentialAdmin(admin.ModelAdmin):
    list_display = ("device", "last_used_at", "revoked_at")
    readonly_fields = ("device", "secret_digest", "last_used_at", "revoked_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False