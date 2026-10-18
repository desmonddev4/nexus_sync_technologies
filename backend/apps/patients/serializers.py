from rest_framework import serializers

from .models import ConsentRecord, EmergencyContact, Patient, PatientDataRequest


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

    class Meta:
        model = Patient
        fields = (
            "id",
            "full_name",
            "date_of_birth",
            "phone_number",
            "relevant_medical_notes",
            "status",
            "emergency_contacts",
            "consent_records",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


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