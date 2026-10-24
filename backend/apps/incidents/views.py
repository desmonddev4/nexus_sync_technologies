from datetime import timedelta

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.accounts.models import AccountProfile
from apps.audit.services import record_audit_event
from apps.devices.models import Device
from apps.patients.access import has_patient_access
from apps.patients.models import PatientAccessGrant
from apps.emergency_services.models import AmbulanceVehicle
from apps.emergency_services.routing import (
    GoogleRoutesProvider,
    RouteCalculationError,
    RouteConfigurationError,
)
from apps.monitoring.models import PatientLocation
from apps.notifications.models import IncidentNotification
from apps.notifications.services import transition_notification
from apps.notifications.serializers import IncidentNotificationStatusSerializer

from .models import Incident, IncidentEvent, IncidentLocationSnapshot, IncidentRoute
from .permissions import CanAccessIncidents
from .serializers import (
    AssignResponderSerializer,
    DispatchConfirmationSerializer,
    IncidentSerializer,
    IncidentEventSerializer,
    IncidentStatusTransitionSerializer,
    SOSCreateSerializer,
)
from .services import (
    InvalidIncidentTransition,
    InvalidResponderAssignment,
    assign_responder as assign_responder_service,
    create_sos_incident,
    record_dispatch_confirmation as record_dispatch_confirmation_service,
    record_dispatch_request as record_dispatch_request_service,
    transition_incident,
)


class IncidentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = IncidentSerializer
    permission_classes = [CanAccessIncidents]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Incident.objects.select_related("patient", "assigned_vehicle__provider")
        profile = getattr(user, "profile", None)
        if profile is None:
            return Incident.objects.none()
        if profile.role in {AccountProfile.Role.EMERGENCY_COORDINATOR, AccountProfile.Role.CLINICIAN}:
            return Incident.objects.select_related("patient", "assigned_vehicle__provider")
        if profile.role == AccountProfile.Role.PATIENT:
            return Incident.objects.filter(patient_id=profile.patient_id).select_related("patient", "assigned_vehicle__provider")
        if profile.role == AccountProfile.Role.EMERGENCY_CONTACT:
            grants = PatientAccessGrant.objects.filter(user=user, revoked_at__isnull=True).select_related("patient")
            patient_ids = [grant.patient_id for grant in grants if "incidents" in grant.scopes and has_patient_access(user, grant.patient, "incidents")]
            return Incident.objects.filter(patient_id__in=patient_ids).select_related("patient", "assigned_vehicle__provider")
        return Incident.objects.none()
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_audit_event(
            request=request,
            action="incident.list",
            resource_type="incident",
            metadata={"result_count": len(response.data)},
        )
        return response

    def get_object(self):
        try:
            incident = super().get_object()
        except (Http404, DjangoPermissionDenied, DRFPermissionDenied):
            record_audit_event(
                request=self.request,
                action="incident.access_denied",
                resource_type="incident",
                resource_id=self.kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""),
                outcome="denied",
            )
            raise
        record_audit_event(
            request=self.request,
            action=f"incident.{self.action}.accessed",
            resource_type="incident",
            resource_id=incident.pk,
        )
        return incident

    @action(detail=False, methods=("post",), url_path="sos")
    def sos(self, request):
        serializer = SOSCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        incident, created = create_sos_incident(
            patient=serializer.validated_data["patient"],
            event_id=serializer.validated_data["event_id"],
            trigger_source=serializer.validated_data["trigger_source"],
            actor=None if isinstance(request.auth, Device) else request.user,
            location=serializer.validated_data.get("location"),
        )
        record_audit_event(
            request=request,
            action="incident.sos.created" if created else "incident.sos.retried",
            resource_type="incident",
            resource_id=incident.pk,
            metadata={"trigger_source": incident.trigger_source},
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(IncidentSerializer(incident).data, status=response_status)

    @action(detail=True, methods=("post",))
    def acknowledge(self, request, pk=None):
        incident = self.get_object()
        try:
            incident = transition_incident(
                incident=incident,
                new_status=Incident.Status.ACKNOWLEDGED,
                actor=request.user,
            )
        except InvalidIncidentTransition as error:
            raise ValidationError({"status": str(error)}) from error
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=("get",), url_path="notifications")
    def notifications(self, request, pk=None):
        incident = self.get_object()
        notifications = IncidentNotification.objects.filter(incident=incident).select_related("emergency_contact")
        profile = getattr(request.user, "profile", None)
        if profile and profile.role == AccountProfile.Role.EMERGENCY_CONTACT:
            notifications = notifications.filter(emergency_contact__phone_number=profile.phone_number)
        serializer = IncidentNotificationStatusSerializer(notifications, many=True)
        return Response(serializer.data)
    @action(detail=True, methods=("post",), url_path=r"notifications/(?P<notification_id>[^/.]+)/acknowledge")
    def acknowledge_notification(self, request, pk=None, notification_id=None):
        incident = self.get_object()
        profile = getattr(request.user, "profile", None)
        if profile is None or profile.role != AccountProfile.Role.EMERGENCY_CONTACT or not profile.phone_number:
            raise DRFPermissionDenied("Only the verified contact receiving this notification can acknowledge it.")
        notification = IncidentNotification.objects.filter(
            pk=notification_id, incident=incident,
            emergency_contact__phone_number=profile.phone_number,
        ).first()
        if notification is None:
            raise Http404
        try:
            notification = transition_notification(notification=notification, new_status=IncidentNotification.Status.ACKNOWLEDGED, actor=request.user)
        except ValueError as error:
            raise ValidationError({"status": str(error)}) from error
        record_audit_event(request=request, action="incident.notification.acknowledged", resource_type="incident_notification", resource_id=notification.pk, metadata={"incident": str(incident.pk)})
        return Response(IncidentNotificationStatusSerializer(notification).data)
    @action(detail=True, methods=("get",), url_path="events")
    def events(self, request, pk=None):
        incident = self.get_object()
        events = IncidentEvent.objects.filter(incident=incident).select_related("actor")
        return Response(IncidentEventSerializer(events, many=True).data)

    @action(detail=True, methods=("post",), url_path="assign-responder")
    def assign_responder(self, request, pk=None):
        incident = self.get_object()
        serializer = AssignResponderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle = get_object_or_404(AmbulanceVehicle, pk=serializer.validated_data["vehicle"])
        try:
            incident = assign_responder_service(
                incident=incident,
                vehicle=vehicle,
                actor=request.user,
                include_simulated=serializer.validated_data["include_simulated"],
            )
        except (InvalidIncidentTransition, InvalidResponderAssignment) as error:
            raise ValidationError({"assignment": str(error)}) from error
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=("post",), url_path="record-dispatch-request")
    def record_dispatch_request(self, request, pk=None):
        incident = self.get_object()
        try:
            incident = record_dispatch_request_service(incident=incident, actor=request.user)
        except InvalidIncidentTransition as error:
            raise ValidationError({"status": str(error)}) from error
        return Response(
            {
                "incident": self.get_serializer(incident).data,
                "provider_contacted_by_system": False,
                "note": "Dispatch request recorded locally; contact the provider through its authorized channel.",
            }
        )

    @action(detail=True, methods=("post",), url_path="record-dispatch-confirmation")
    def record_dispatch_confirmation(self, request, pk=None):
        incident = self.get_object()
        serializer = DispatchConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            incident = record_dispatch_confirmation_service(
                incident=incident,
                actor=request.user,
                confirmation_reference=serializer.validated_data["confirmation_reference"],
            )
        except InvalidIncidentTransition as error:
            raise ValidationError({"status": str(error)}) from error
        return Response(
            {
                "incident": self.get_serializer(incident).data,
                "confirmation_source": "operator_reported",
                "note": "This records operator-reported provider confirmation; it is not verified by a provider integration.",
            }
        )

    @action(detail=True, methods=("post",), url_path="status")
    def advance_status(self, request, pk=None):
        incident = self.get_object()
        serializer = IncidentStatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            incident = transition_incident(
                incident=incident,
                new_status=serializer.validated_data["status"],
                actor=request.user,
            )
        except InvalidIncidentTransition as error:
            raise ValidationError({"status": str(error)}) from error
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=("post",))
    def route(self, request, pk=None):
        incident = self.get_object()
        vehicle = incident.assigned_vehicle
        if vehicle is None or vehicle.latitude is None or vehicle.longitude is None:
            raise ValidationError({"vehicle": "Assign a responder with a known location first."})
        try:
            location = incident.location_snapshot
        except IncidentLocationSnapshot.DoesNotExist:
            raise ValidationError({"location": "This incident has no patient location snapshot."})

        now = timezone.now()
        if location.quality == PatientLocation.Quality.STALE or location.recorded_at < now - timedelta(minutes=5):
            raise ValidationError({"location": "The incident patient location is stale."})
        if vehicle.location_updated_at is None or vehicle.location_updated_at < now - timedelta(minutes=5):
            raise ValidationError({"vehicle": "The assigned vehicle location is stale."})

        try:
            provider = GoogleRoutesProvider()
            route = provider.calculate_driving_route(
                origin=(vehicle.latitude, vehicle.longitude),
                destination=(location.latitude, location.longitude),
            )
        except RouteConfigurationError as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except RouteCalculationError as error:
            return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)

        route_record = IncidentRoute.objects.create(
            incident=incident,
            vehicle=vehicle,
            origin_latitude=vehicle.latitude,
            origin_longitude=vehicle.longitude,
            destination_latitude=location.latitude,
            destination_longitude=location.longitude,
            distance_meters=route.distance_meters,
            duration_seconds=route.duration_seconds,
            encoded_polyline=route.encoded_polyline,
            is_simulated=incident.is_simulated_dispatch,
        )
        return Response(
            {
                "id": route_record.pk,
                "routing_provider": route_record.routing_provider,
                "distance_meters": route_record.distance_meters,
                "duration_seconds": route_record.duration_seconds,
                "duration_minutes": (route_record.duration_seconds + 59) // 60,
                "encoded_polyline": route_record.encoded_polyline,
                "is_simulated": route_record.is_simulated,
                "computed_at": route_record.created_at,
            },
            status=status.HTTP_200_OK,
        )
