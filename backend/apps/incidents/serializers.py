from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import AccountProfile
from apps.monitoring.models import PatientLocation
from apps.patients.models import Patient

from .models import Incident, IncidentEvent, IncidentLocationSnapshot


class SOSCreateSerializer(serializers.Serializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all())
    event_id = serializers.UUIDField()
    trigger_source = serializers.ChoiceField(
        choices=(Incident.Source.MANUAL, Incident.Source.SIMULATOR),
    )

    def validate(self, attrs):
        user = self.context["request"].user
        if user.is_superuser:
            return attrs

        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            raise serializers.ValidationError("An account role is required.")

        staff_roles = {
            AccountProfile.Role.EMERGENCY_COORDINATOR,
            AccountProfile.Role.CLINICIAN,
        }
        patient_user = profile.role == AccountProfile.Role.PATIENT
        if patient_user and attrs["patient"].pk != profile.patient_id:
            raise serializers.ValidationError("Patients can only raise their own SOS.")
        if patient_user and attrs["trigger_source"] != Incident.Source.MANUAL:
            raise serializers.ValidationError("Patient SOS must use the manual source.")
        if not patient_user and profile.role not in staff_roles:
            raise serializers.ValidationError("This account cannot raise incidents.")
        return attrs


class IncidentSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()
    assigned_vehicle_identifier = serializers.CharField(
        source="assigned_vehicle.vehicle_identifier",
        read_only=True,
        allow_null=True,
    )
    assigned_provider_name = serializers.CharField(
        source="assigned_vehicle.provider.name",
        read_only=True,
        allow_null=True,
    )
    assigned_vehicle_source = serializers.CharField(
        source="assigned_vehicle.data_source",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Incident
        fields = (
            "id",
            "patient",
            "source_event_id",
            "incident_type",
            "priority",
            "trigger_source",
            "status",
            "location",
            "assigned_vehicle",
            "assigned_vehicle_identifier",
            "assigned_provider_name",
            "assigned_vehicle_source",
            "assigned_operator",
            "is_simulated_dispatch",
            "dispatch_requested_at",
            "dispatch_confirmed_at",
            "dispatch_confirmation_reference",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_location(self, obj):
        try:
            snapshot = obj.location_snapshot
        except IncidentLocationSnapshot.DoesNotExist:
            return None
        return IncidentLocationSnapshotSerializer(snapshot).data


class IncidentLocationSnapshotSerializer(serializers.ModelSerializer):
    age_seconds = serializers.SerializerMethodField()
    is_stale = serializers.SerializerMethodField()

    class Meta:
        model = IncidentLocationSnapshot
        fields = (
            "latitude",
            "longitude",
            "accuracy_meters",
            "source",
            "quality",
            "recorded_at",
            "received_at",
            "age_seconds",
            "is_stale",
        )
        read_only_fields = fields

    def get_age_seconds(self, obj):
        return max(0, int((timezone.now() - obj.recorded_at).total_seconds()))

    def get_is_stale(self, obj):
        return (
            obj.quality == PatientLocation.Quality.STALE
            or obj.recorded_at < timezone.now() - timedelta(minutes=5)
        )


class IncidentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentEvent
        fields = ("id", "event_type", "actor", "details", "created_at")
        read_only_fields = fields


class AssignResponderSerializer(serializers.Serializer):
    vehicle = serializers.UUIDField()
    include_simulated = serializers.BooleanField(default=False)


class DispatchConfirmationSerializer(serializers.Serializer):
    confirmation_reference = serializers.CharField(max_length=200, allow_blank=False)


class IncidentStatusTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(
            Incident.Status.RESPONDER_EN_ROUTE,
            Incident.Status.ARRIVED,
            Incident.Status.RESOLVED,
            Incident.Status.CLOSED,
            Incident.Status.DECLINED,
            Incident.Status.CANCELLED,
        )
    )