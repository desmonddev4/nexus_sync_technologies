from rest_framework import serializers

from .models import AmbulanceVehicle, EmergencyProvider, HealthcareFacility


class EmergencyProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyProvider
        fields = (
            "id",
            "name",
            "provider_type",
            "dispatch_phone_number",
            "general_phone_number",
            "email",
            "address",
            "latitude",
            "longitude",
            "operating_hours",
            "coverage_description",
            "verification_status",
            "api_integration_authorized",
            "fleet_feed_authorized",
            "integration_authorization_reference",
            "integration_authorized_at",
            "verification_source",
            "verified_by",
            "verified_at",
        )
        read_only_fields = fields


class HealthcareFacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthcareFacility
        fields = (
            "id",
            "name",
            "facility_type",
            "address",
            "phone_number",
            "latitude",
            "longitude",
            "verification_source",
            "verified_by",
            "verified_at",
            "verification_status",
        )
        read_only_fields = fields


class AmbulanceVehicleSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    provider_verification_status = serializers.CharField(
        source="provider.verification_status",
        read_only=True,
    )
    is_simulated = serializers.SerializerMethodField()

    class Meta:
        model = AmbulanceVehicle
        fields = (
            "id",
            "provider",
            "provider_name",
            "provider_verification_status",
            "vehicle_identifier",
            "capabilities",
            "availability",
            "data_source",
            "is_simulated",
            "latitude",
            "longitude",
            "location_accuracy_meters",
            "location_updated_at",
            "current_incident",
        )
        read_only_fields = fields

    def get_is_simulated(self, obj):
        return obj.data_source == AmbulanceVehicle.DataSource.SIMULATOR


class NearbyVehiclesQuerySerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)
    max_location_age_seconds = serializers.IntegerField(min_value=1, max_value=3600, default=300)
    max_distance_kilometers = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    required_capability = serializers.CharField(max_length=80, required=False)
    include_simulated = serializers.BooleanField(default=False)


class EmergencyProviderManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyProvider
        fields = (
            "id", "name", "provider_type", "dispatch_phone_number", "general_phone_number",
            "email", "address", "latitude", "longitude", "operating_hours", "coverage_description",
            "verification_status", "verification_source", "verified_by", "verified_at",
            "api_integration_authorized", "fleet_feed_authorized", "integration_authorization_reference",
            "integration_authorized_at", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "verification_status", "verification_source", "verified_by", "verified_at",
            "api_integration_authorized", "fleet_feed_authorized", "integration_authorization_reference",
            "integration_authorized_at", "created_at", "updated_at",
        )


class HealthcareFacilityManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthcareFacility
        fields = (
            "id", "name", "facility_type", "address", "phone_number", "latitude", "longitude",
            "verification_source", "verified_by", "verified_at", "verification_status", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "verification_source", "verified_by", "verified_at", "verification_status",
            "created_at", "updated_at",
        )


class AmbulanceVehicleManagementSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = AmbulanceVehicle
        fields = (
            "id", "provider", "provider_name", "vehicle_identifier", "capabilities", "availability",
            "data_source", "latitude", "longitude", "location_accuracy_meters", "location_updated_at",
            "current_incident", "created_at", "updated_at",
        )
        read_only_fields = ("id", "current_incident", "created_at", "updated_at")

    def validate(self, attrs):
        provider = attrs.get("provider", getattr(self.instance, "provider", None))
        source = attrs.get("data_source", getattr(self.instance, "data_source", None))
        availability = attrs.get(
            "availability",
            getattr(self.instance, "availability", AmbulanceVehicle.Availability.UNAVAILABLE),
        )
        if source == AmbulanceVehicle.DataSource.PROVIDER:
            if not provider or provider.verification_status != EmergencyProvider.VerificationStatus.VERIFIED:
                raise serializers.ValidationError({"provider": "Provider-sourced vehicles require a verified provider."})
            if not provider.fleet_feed_authorized:
                raise serializers.ValidationError({"provider": "Provider fleet-feed authorization is required."})
        elif source == AmbulanceVehicle.DataSource.SIMULATOR:
            if not provider or provider.verification_status != EmergencyProvider.VerificationStatus.SIMULATED:
                raise serializers.ValidationError({"provider": "Simulated vehicles must belong to a simulation-only provider."})
            if self.instance is None and availability != AmbulanceVehicle.Availability.UNAVAILABLE:
                raise serializers.ValidationError({"availability": "Provisioned simulator vehicles must remain unavailable until updated by the simulator."})
        return attrs


class VerifyDirectoryRecordSerializer(serializers.Serializer):
    verification_source = serializers.CharField(max_length=300, allow_blank=False)