from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AmbulanceVehicle, EmergencyProvider, HealthcareFacility
from .permissions import IsEmergencyOperationsStaff
from .serializers import (
    AmbulanceVehicleSerializer,
    EmergencyProviderSerializer,
    HealthcareFacilitySerializer,
    NearbyVehiclesQuerySerializer,
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