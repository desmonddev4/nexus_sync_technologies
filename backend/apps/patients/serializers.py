from rest_framework import serializers

from apps.accounts.models import AccountProfile
from .access import has_patient_access
from .models import ConsentRecord, EmergencyContact, Patient, PatientAccessGrant, PatientDataRequest


class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = (
            "id",
            "name",
            "relationship",
            "phone_number",
            "notification_preferences",
            "priority_order",
            "verification_status",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ConsentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRecord
        fields = (
            "id",
            "scope",
            "status",
            "policy_version",
            "recorded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PatientSerializer(serializers.ModelSerializer):
    emergency_contacts = EmergencyContactSerializer(many=True, read_only=True)
    consent_records = ConsentRecordSerializer(many=True, read_only=True)
    access_scopes = serializers.SerializerMethodField()

    def get_access_scopes(self, instance):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return []
        if user.is_superuser:
            return list(PatientAccessGrant.Scope.values)
        profile = getattr(user, "profile", None)
        if profile and profile.role == AccountProfile.Role.PATIENT and profile.patient_id == instance.pk:
            return list(PatientAccessGrant.Scope.values)
        if not has_patient_access(user, instance, "patient"):
            return []
        grant = PatientAccessGrant.objects.filter(patient=instance, user=user, revoked_at__isnull=True).first()
        return grant.scopes if grant else []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        profile = getattr(getattr(request, "user", None), "profile", None) if request else None
        if profile and profile.role == AccountProfile.Role.EMERGENCY_CONTACT:
            for field in ("date_of_birth", "phone_number", "relevant_medical_notes", "emergency_contacts", "consent_records"):
                data.pop(field, None)
        return data

    class Meta:
        model = Patient
        fields = (
            "id", "full_name", "date_of_birth", "phone_number", "relevant_medical_notes",
            "status", "emergency_contacts", "consent_records", "access_scopes", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "access_scopes")

class PatientDataRequestSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all(), required=False)
    requested_by_username = serializers.SerializerMethodField(read_only=True)
    reviewed_by_username = serializers.SerializerMethodField(read_only=True)
    fulfilled_by_username = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PatientDataRequest
        fields = (
            "id",
            "patient",
            "request_type",
            "status",
            "requested_by",
            "requested_by_username",
            "requested_at",
            "reason",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "fulfilled_by",
            "fulfilled_by_username",
            "fulfilled_at",
            "fulfillment_summary",
            "review_notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "requested_by",
            "requested_by_username",
            "requested_at",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "fulfilled_by",
            "fulfilled_by_username",
            "fulfilled_at",
            "fulfillment_summary",
            "review_notes",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        patient = attrs.get("patient")
        request = self.context.get("request")
        if patient is None and request is not None:
            profile = getattr(request.user, "profile", None)
            if profile and profile.patient_id:
                attrs["patient"] = profile.patient
        if attrs.get("patient") is None:
            raise serializers.ValidationError({"patient": "Patient is required."})
        return attrs

    def get_requested_by_username(self, obj):
        return obj.requested_by.get_username() if obj.requested_by else None

    def get_reviewed_by_username(self, obj):
        return obj.reviewed_by.get_username() if obj.reviewed_by else None

    def get_fulfilled_by_username(self, obj):
        return obj.fulfilled_by.get_username() if obj.fulfilled_by else None
