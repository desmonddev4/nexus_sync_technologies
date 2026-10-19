from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import record_audit_event

from .models import AmbulanceVehicle, EmergencyProvider, HealthcareFacility
from .permissions import CanManageEmergencyDirectory, IsEmergencyOperationsStaff
from .serializers import (
    AmbulanceVehicleManagementSerializer,
    AmbulanceVehicleSerializer,
    EmergencyProviderManagementSerializer,
    EmergencyProviderSerializer,
    HealthcareFacilityManagementSerializer,
    HealthcareFacilitySerializer,
    NearbyVehiclesQuerySerializer,
    VerifyDirectoryRecordSerializer,
)
from .services import eligible_vehicles


class ReadOnlyStaffViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsEmergencyOperationsStaff]


class EmergencyProviderViewSet(ReadOnlyStaffViewSet):
    serializer_class = EmergencyProviderSerializer
    queryset = EmergencyProvider.objects.filter(
        verification_status=EmergencyProvider.VerificationStatus.VERIFIED
    )


class HealthcareFacilityViewSet(ReadOnlyStaffViewSet):
    serializer_class = HealthcareFacilitySerializer
    queryset = HealthcareFacility.objects.filter(
        is_active=True,
        verification_status=HealthcareFacility.VerificationStatus.VERIFIED,
    )


class AmbulanceVehicleViewSet(ReadOnlyStaffViewSet):
    serializer_class = AmbulanceVehicleSerializer
    queryset = AmbulanceVehicle.objects.filter(
        provider__verification_status=EmergencyProvider.VerificationStatus.VERIFIED,
    ).select_related("provider", "current_incident")

    @action(detail=False, methods=("get",), url_path="nearby")
    def nearby(self, request):
        query = NearbyVehiclesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        results = eligible_vehicles(**query.validated_data)
        response = []
        for vehicle, distance in results:
            item = dict(self.get_serializer(vehicle).data)
            item["distance_kilometers"] = round(distance, 2)
            response.append(item)
        return Response(response, status=status.HTTP_200_OK)


class DirectoryManagementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [CanManageEmergencyDirectory]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def perform_create(self, serializer):
        record = serializer.save()
        record_audit_event(
            request=self.request,
            action=f"directory.{self.basename}.created",
            resource_type=self.basename,
            resource_id=record.pk,
        )

    def perform_update(self, serializer):
        record = serializer.save()
        record_audit_event(
            request=self.request,
            action=f"directory.{self.basename}.updated",
            resource_type=self.basename,
            resource_id=record.pk,
        )


class ProviderDirectoryManagementViewSet(DirectoryManagementViewSet):
    queryset = EmergencyProvider.objects.all()
    serializer_class = EmergencyProviderManagementSerializer
    basename = "provider"

    @action(detail=True, methods=("post",))
    def verify(self, request, pk=None):
        provider = self.get_object()
        serializer = VerifyDirectoryRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider.verification_status = EmergencyProvider.VerificationStatus.VERIFIED
        provider.verification_source = serializer.validated_data["verification_source"]
        provider.verified_by = request.user.get_username()
        provider.verified_at = timezone.now()
        provider.save(update_fields=("verification_status", "verification_source", "verified_by", "verified_at", "updated_at"))
        record_audit_event(
            request=request,
            action="directory.provider.verified",
            resource_type="provider",
            resource_id=provider.pk,
            metadata={"verification_source": provider.verification_source},
        )
        return Response(self.get_serializer(provider).data)


class FacilityDirectoryManagementViewSet(DirectoryManagementViewSet):
    queryset = HealthcareFacility.objects.all()
    serializer_class = HealthcareFacilityManagementSerializer
    basename = "facility"

    @action(detail=True, methods=("post",))
    def verify(self, request, pk=None):
        facility = self.get_object()
        serializer = VerifyDirectoryRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        facility.verification_status = HealthcareFacility.VerificationStatus.VERIFIED
        facility.verification_source = serializer.validated_data["verification_source"]
        facility.verified_by = request.user.get_username()
        facility.verified_at = timezone.now()
        facility.save(update_fields=("verification_status", "verification_source", "verified_by", "verified_at", "updated_at"))
        record_audit_event(
            request=request,
            action="directory.facility.verified",
            resource_type="facility",
            resource_id=facility.pk,
            metadata={"verification_source": facility.verification_source},
        )
        return Response(self.get_serializer(facility).data)


class VehicleDirectoryManagementViewSet(DirectoryManagementViewSet):
    queryset = AmbulanceVehicle.objects.select_related("provider", "current_incident").all()
    serializer_class = AmbulanceVehicleManagementSerializer
    basename = "vehicle"