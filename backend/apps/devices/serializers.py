from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.patients.models import Patient

from .models import Device


class DeviceHeartbeatSerializer(serializers.Serializer):
    battery_percent = serializers.IntegerField(min_value=0, max_value=100, required=False)
    firmware_version = serializers.CharField(max_length=40, required=False, allow_blank=True)


class DeviceHealthSerializer(serializers.ModelSerializer):
    is_stale = serializers.SerializerMethodField()
    last_seen_age_seconds = serializers.SerializerMethodField()
    credential_revoked = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = (
            "id",
            "device_identifier",
            "device_type",
            "status",
            "firmware_version",
            "battery_percent",
            "last_seen_at",
            "last_seen_age_seconds",
            "is_stale",
            "credential_revoked",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_last_seen_age_seconds(self, obj):
        if not obj.last_seen_at:
            return None
        return max(0, int((timezone.now() - obj.last_seen_at).total_seconds()))

    def get_is_stale(self, obj):
        if not obj.last_seen_at:
            return True
        return obj.last_seen_at < timezone.now() - timedelta(minutes=5)

    def get_credential_revoked(self, obj):
        credential = getattr(obj, "credential", None)
        if credential is None:
            return None
        return credential.revoked_at is not None


class DeviceManagementSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(), allow_null=True, required=False
    )
    credential_revoked = serializers.SerializerMethodField()
    credential_last_used_at = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = (
            "id",
            "device_identifier",
            "patient",
            "device_type",
            "status",
            "firmware_version",
            "battery_percent",
            "last_seen_at",
            "credential_revoked",
            "credential_last_used_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "firmware_version",
            "battery_percent",
            "last_seen_at",
            "created_at",
            "updated_at",
        )

    def get_credential_revoked(self, obj):
        credential = getattr(obj, "credential", None)
        return credential is None or credential.revoked_at is not None

    def get_credential_last_used_at(self, obj):
        credential = getattr(obj, "credential", None)
        return credential.last_used_at if credential else None