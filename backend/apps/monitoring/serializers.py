from rest_framework import serializers

from apps.accounts.models import AccountProfile
from apps.devices.models import Device
from apps.patients.models import Patient

from .models import Measurement, MonitoringRule, MonitoringRuleEvaluation, PatientLocation


class PatientDataIngestSerializer(serializers.Serializer):
    patient = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        required=False,
    )

    def validate_patient(self, patient):
        device = self.context["request"].auth
        if isinstance(device, Device):
            if device.patient_id != patient.pk:
                raise serializers.ValidationError("Device is not assigned to this patient.")
            return patient

        user = self.context["request"].user
        if user.is_superuser:
            return patient
        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            raise serializers.ValidationError("An account role is required.")

        staff_roles = {
            AccountProfile.Role.EMERGENCY_COORDINATOR,
            AccountProfile.Role.CLINICIAN,
        }
        if profile.role in staff_roles:
            return patient
        if profile.role == AccountProfile.Role.PATIENT and profile.patient_id == patient.pk:
            return patient
        raise serializers.ValidationError("This account cannot submit data for this patient.")

    def validate_device(self, device):
        if device and device.status == Device.Status.REVOKED:
            raise serializers.ValidationError("Revoked devices cannot submit data.")
        return device

    def validate_ingest_identity(self, attrs):
        authenticated_device = self.context["request"].auth
        if isinstance(authenticated_device, Device):
            if authenticated_device.status != Device.Status.ACTIVE:
                raise serializers.ValidationError("Inactive devices cannot submit data.")
            if attrs.get("patient") and attrs["patient"].pk != authenticated_device.patient_id:
                raise serializers.ValidationError({"patient": "Device is not assigned to this patient."})
            if attrs.get("device") and attrs["device"].pk != authenticated_device.pk:
                raise serializers.ValidationError({"device": "Credential does not match this device."})

            expected_source = {
                Device.Type.WEARABLE: "wearable",
                Device.Type.SIMULATOR: "simulator",
            }[authenticated_device.device_type]
            if attrs.get("source") not in (None, expected_source):
                raise serializers.ValidationError({"source": "Source is determined by device credentials."})
            attrs["patient"] = authenticated_device.patient
            attrs["device"] = authenticated_device
            attrs["source"] = expected_source
            return attrs

        if not attrs.get("patient"):
            raise serializers.ValidationError({"patient": "This field is required for user submissions."})
        if not attrs.get("source"):
            raise serializers.ValidationError({"source": "This field is required for user submissions."})
        if attrs["source"] == "wearable":
            raise serializers.ValidationError(
                {"source": "Wearable data requires device-specific credentials."}
            )
        device = attrs.get("device")
        if device and device.patient_id != attrs["patient"].pk:
            raise serializers.ValidationError({"device": "Device is not assigned to this patient."})
        return attrs


class MeasurementIngestSerializer(PatientDataIngestSerializer):
    device = serializers.PrimaryKeyRelatedField(
        queryset=Device.objects.all(),
        required=False,
        allow_null=True,
    )
    event_id = serializers.UUIDField()
    measurement_type = serializers.ChoiceField(choices=Measurement.Type.choices)
    value = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)
    unit = serializers.CharField(max_length=24)
    source = serializers.ChoiceField(choices=Measurement.Source.choices, required=False)
    measured_at = serializers.DateTimeField()

    expected_units = {
        Measurement.Type.HEART_RATE: "bpm",
        Measurement.Type.SPO2: "percent",
        Measurement.Type.SKIN_TEMPERATURE: "celsius",
        Measurement.Type.BODY_TEMPERATURE: "celsius",
        Measurement.Type.SYSTOLIC_BLOOD_PRESSURE: "mmHg",
        Measurement.Type.DIASTOLIC_BLOOD_PRESSURE: "mmHg",
    }

    def validate(self, attrs):
        attrs = self.validate_ingest_identity(attrs)
        if attrs["unit"] != self.expected_units[attrs["measurement_type"]]:
            raise serializers.ValidationError({"unit": "Unit does not match measurement type."})
        if attrs["measurement_type"] == Measurement.Type.SPO2 and attrs["value"] > 100:
            raise serializers.ValidationError({"value": "SpO2 must be between 0 and 100."})
        return attrs


class PatientLocationIngestSerializer(PatientDataIngestSerializer):
    device = serializers.PrimaryKeyRelatedField(
        queryset=Device.objects.all(),
        required=False,
        allow_null=True,
    )
    event_id = serializers.UUIDField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
    )
    source = serializers.ChoiceField(choices=PatientLocation.Source.choices, required=False)
    recorded_at = serializers.DateTimeField()

    def validate(self, attrs):
        attrs = self.validate_ingest_identity(attrs)
        if not -90 <= attrs["latitude"] <= 90:
            raise serializers.ValidationError({"latitude": "Latitude must be between -90 and 90."})
        if not -180 <= attrs["longitude"] <= 180:
            raise serializers.ValidationError({"longitude": "Longitude must be between -180 and 180."})
        return attrs


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        fields = (
            "id",
            "patient",
            "device",
            "event_id",
            "measurement_type",
            "value",
            "unit",
            "source",
            "quality",
            "measured_at",
            "received_at",
        )
        read_only_fields = fields


class PatientLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientLocation
        fields = (
            "id",
            "patient",
            "device",
            "event_id",
            "latitude",
            "longitude",
            "accuracy_meters",
            "source",
            "quality",
            "recorded_at",
            "received_at",
        )
        read_only_fields = fields


class MonitoringRuleSerializer(serializers.ModelSerializer):
    reviewed_by_username = serializers.SerializerMethodField()
    evaluation_count = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringRule
        fields = (
            "id",
            "name",
            "description",
            "measurement_type",
            "operator",
            "threshold",
            "priority",
            "minimum_consecutive_readings",
            "lookback_window_seconds",
            "include_simulated",
            "version",
            "is_enabled",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "evaluation_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "is_enabled",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "evaluation_count",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        if self.instance and self.instance.evaluations.exists() and attrs:
            raise serializers.ValidationError(
                "Evaluated rule versions are immutable. Create a new version to change this rule."
            )
        return attrs

    def get_reviewed_by_username(self, obj):
        return obj.reviewed_by.get_username() if obj.reviewed_by else None

    def get_evaluation_count(self, obj):
        return obj.evaluations.count()


class MonitoringRuleReviewSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()


class MonitoringRuleEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringRuleEvaluation
        fields = (
            "id",
            "rule",
            "measurement",
            "incident",
            "status",
            "details",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MeasurementQualityReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = Measurement
        fields = (
            "id",
            "patient",
            "patient_name",
            "device",
            "event_id",
            "measurement_type",
            "value",
            "unit",
            "source",
            "quality",
            "quality_reviewed_by",
            "quality_reviewed_at",
            "measured_at",
            "received_at",
        )
        read_only_fields = fields


class MeasurementQualityDecisionSerializer(serializers.Serializer):
    quality = serializers.ChoiceField(
        choices=(Measurement.Quality.ACCEPTABLE, Measurement.Quality.QUESTIONABLE)
    )