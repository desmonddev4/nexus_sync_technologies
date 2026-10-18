import uuid

from django.db import transaction
from django.utils import timezone

from apps.emergency_services.models import AmbulanceVehicle, EmergencyProvider
from apps.monitoring.models import PatientLocation
from apps.notifications.services import queue_incident_notifications

from .models import Incident, IncidentEvent, IncidentLocationSnapshot


class InvalidIncidentTransition(Exception):
    pass


class InvalidResponderAssignment(Exception):
    pass


ALLOWED_TRANSITIONS = {
    Incident.Status.CREATED: {
        Incident.Status.ACKNOWLEDGED,
        Incident.Status.CANCELLED,
    },
    Incident.Status.ACKNOWLEDGED: {
        Incident.Status.RESPONDER_ASSIGNED,
        Incident.Status.RESOLVED,
        Incident.Status.CANCELLED,
    },
    Incident.Status.RESPONDER_ASSIGNED: {
        Incident.Status.DISPATCH_REQUESTED,
        Incident.Status.DECLINED,
        Incident.Status.CANCELLED,
    },
    Incident.Status.DISPATCH_REQUESTED: {
        Incident.Status.DISPATCH_CONFIRMED,
        Incident.Status.DECLINED,
    },
    Incident.Status.DISPATCH_CONFIRMED: {Incident.Status.RESPONDER_EN_ROUTE},
    Incident.Status.RESPONDER_EN_ROUTE: {Incident.Status.ARRIVED},
    Incident.Status.ARRIVED: {Incident.Status.RESOLVED},
    Incident.Status.RESOLVED: {Incident.Status.CLOSED},
    Incident.Status.DECLINED: {Incident.Status.ACKNOWLEDGED},
    Incident.Status.CLOSED: set(),
    Incident.Status.CANCELLED: set(),
}


@transaction.atomic
def create_sos_incident(*, patient, event_id, trigger_source, actor):
    incident, created = Incident.objects.get_or_create(
        patient=patient,
        source_event_id=event_id,
        defaults={
            "incident_type": Incident.Type.MANUAL_SOS,
            "priority": Incident.Priority.HIGH,
            "trigger_source": trigger_source,
        },
    )
    if created:
        snapshot_latest_patient_location(incident=incident, patient=patient)
        IncidentEvent.objects.create(
            incident=incident,
            event_type=IncidentEvent.Type.CREATED,
            actor=actor,
            details={"trigger_source": trigger_source},
        )
        queue_incident_notifications(incident)
    return incident, created


@transaction.atomic
def create_measurement_alert(*, measurement, rule, details):
    event_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"nexus-monitoring-rule:{rule.pk}:{measurement.pk}",
    )
    incident, created = Incident.objects.get_or_create(
        patient=measurement.patient,
        source_event_id=event_id,
        defaults={
            "incident_type": Incident.Type.MEASUREMENT_ALERT,
            "priority": rule.priority,
            "trigger_source": Incident.Source.RULE,
        },
    )
    if created:
        snapshot_latest_patient_location(incident=incident, patient=measurement.patient)
        IncidentEvent.objects.create(
            incident=incident,
            event_type=IncidentEvent.Type.CREATED,
            details={"trigger_source": Incident.Source.RULE, **details},
        )
        queue_incident_notifications(incident)
    return incident, created


def snapshot_latest_patient_location(*, incident, patient):
    location = (
        PatientLocation.objects.filter(patient=patient)
        .order_by("-received_at", "-created_at")
        .first()
    )
    if location is None:
        return None
    return IncidentLocationSnapshot.objects.create(
        incident=incident,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy_meters=location.accuracy_meters,
        source=location.source,
        quality=location.quality,
        recorded_at=location.recorded_at,
        received_at=location.received_at,
    )


@transaction.atomic
def transition_incident(*, incident, new_status, actor):
    incident = Incident.objects.select_for_update().get(pk=incident.pk)
    allowed = ALLOWED_TRANSITIONS.get(incident.status, set())
    if new_status not in allowed:
        raise InvalidIncidentTransition(
            f"Cannot transition incident from {incident.status} to {new_status}."
        )

    old_status = incident.status
    incident.status = new_status
    incident.save(update_fields=("status", "updated_at"))
    event_type = (
        IncidentEvent.Type.ACKNOWLEDGED
        if new_status == Incident.Status.ACKNOWLEDGED
        else IncidentEvent.Type.STATUS_CHANGED
    )
    IncidentEvent.objects.create(
        incident=incident,
        event_type=event_type,
        actor=actor,
        details={"from": old_status, "to": new_status},
    )
    if new_status in {
        Incident.Status.CLOSED,
        Incident.Status.CANCELLED,
        Incident.Status.DECLINED,
    }:
        release_assigned_vehicle(incident)
    return incident


@transaction.atomic
def assign_responder(*, incident, vehicle, actor, include_simulated=False):
    incident = Incident.objects.select_for_update().get(pk=incident.pk)
    vehicle_ids = {vehicle.pk}
    if incident.assigned_vehicle_id:
        vehicle_ids.add(incident.assigned_vehicle_id)
    locked_vehicles = (
        AmbulanceVehicle.objects.select_for_update()
        .select_related("provider")
        .filter(pk__in=vehicle_ids)
        .order_by("pk")
    )
    vehicles_by_id = {locked_vehicle.pk: locked_vehicle for locked_vehicle in locked_vehicles}
    vehicle = vehicles_by_id.get(vehicle.pk)
    if vehicle is None:
        raise InvalidResponderAssignment("The selected vehicle no longer exists.")
    if incident.status not in (Incident.Status.ACKNOWLEDGED, Incident.Status.RESPONDER_ASSIGNED):
        raise InvalidIncidentTransition("Acknowledge the incident before assigning a responder.")
    if vehicle.availability != AmbulanceVehicle.Availability.AVAILABLE:
        raise InvalidResponderAssignment("The vehicle is not available.")
    if vehicle.current_incident_id not in (None, incident.pk):
        raise InvalidResponderAssignment("The vehicle is already assigned to another incident.")
    if vehicle.latitude is None or vehicle.longitude is None or vehicle.location_updated_at is None:
        raise InvalidResponderAssignment("The vehicle has no current location.")
    if vehicle.location_updated_at < timezone.now() - timezone.timedelta(minutes=5):
        raise InvalidResponderAssignment("The vehicle location is stale.")

    is_simulated = vehicle.data_source == AmbulanceVehicle.DataSource.SIMULATOR
    if is_simulated:
        if not include_simulated:
            raise InvalidResponderAssignment("Explicitly opt in to assign a simulated vehicle.")
        if vehicle.provider.verification_status != EmergencyProvider.VerificationStatus.SIMULATED:
            raise InvalidResponderAssignment("Simulated vehicles require a simulation-only provider.")
    else:
        if vehicle.provider.verification_status != EmergencyProvider.VerificationStatus.VERIFIED:
            raise InvalidResponderAssignment("The vehicle provider is not verified.")
        if not vehicle.provider.fleet_feed_authorized:
            raise InvalidResponderAssignment(
                "The provider feed is not authorized for live operational dispatch."
            )

    previous_vehicle = incident.assigned_vehicle
    if previous_vehicle and previous_vehicle.pk != vehicle.pk:
        release_assigned_vehicle(incident, vehicle=vehicles_by_id.get(previous_vehicle.pk))

    previous_status = incident.status
    incident.assigned_vehicle = vehicle
    incident.assigned_operator = actor
    incident.is_simulated_dispatch = is_simulated
    if incident.status == Incident.Status.ACKNOWLEDGED:
        incident.status = Incident.Status.RESPONDER_ASSIGNED
    incident.save(
        update_fields=(
            "assigned_vehicle",
            "assigned_operator",
            "is_simulated_dispatch",
            "status",
            "updated_at",
        )
    )
    vehicle.current_incident = incident
    vehicle.availability = AmbulanceVehicle.Availability.ON_CALL
    vehicle.save(update_fields=("current_incident", "availability", "updated_at"))
    IncidentEvent.objects.create(
        incident=incident,
        event_type=IncidentEvent.Type.RESPONDER_ASSIGNED,
        actor=actor,
        details={
            "vehicle_id": str(vehicle.pk),
            "vehicle_identifier": vehicle.vehicle_identifier,
            "provider_name": vehicle.provider.name,
            "is_simulated": is_simulated,
            "previous_status": previous_status,
        },
    )
    return incident


@transaction.atomic
def record_dispatch_request(*, incident, actor):
    incident = Incident.objects.select_for_update().get(pk=incident.pk)
    if incident.status != Incident.Status.RESPONDER_ASSIGNED or not incident.assigned_vehicle_id:
        raise InvalidIncidentTransition("Assign a responder before recording a dispatch request.")
    incident.status = Incident.Status.DISPATCH_REQUESTED
    incident.dispatch_requested_at = timezone.now()
    incident.save(update_fields=("status", "dispatch_requested_at", "updated_at"))
    IncidentEvent.objects.create(
        incident=incident,
        event_type=IncidentEvent.Type.DISPATCH_REQUEST_RECORDED,
        actor=actor,
        details={
            "provider_contacted_by_system": False,
            "is_simulated": incident.is_simulated_dispatch,
        },
    )
    return incident


@transaction.atomic
def record_dispatch_confirmation(*, incident, actor, confirmation_reference):
    incident = Incident.objects.select_for_update().get(pk=incident.pk)
    if incident.status != Incident.Status.DISPATCH_REQUESTED:
        raise InvalidIncidentTransition("Record a dispatch request before its confirmation.")
    if not incident.assigned_vehicle_id:
        raise InvalidIncidentTransition("A responder must be assigned before confirmation.")

    incident.status = Incident.Status.DISPATCH_CONFIRMED
    incident.dispatch_confirmed_at = timezone.now()
    incident.dispatch_confirmation_reference = confirmation_reference
    incident.save(
        update_fields=(
            "status",
            "dispatch_confirmed_at",
            "dispatch_confirmation_reference",
            "updated_at",
        )
    )
    IncidentEvent.objects.create(
        incident=incident,
        event_type=IncidentEvent.Type.DISPATCH_CONFIRMATION_RECORDED,
        actor=actor,
        details={
            "confirmation_source": "operator_reported",
            "confirmation_reference": confirmation_reference,
            "is_simulated": incident.is_simulated_dispatch,
        },
    )
    return incident


def release_assigned_vehicle(incident, *, vehicle=None):
    if not incident.assigned_vehicle_id:
        return
    vehicle = vehicle or (
        AmbulanceVehicle.objects.select_for_update()
        .filter(pk=incident.assigned_vehicle_id)
        .first()
    )
    if vehicle is None:
        incident.assigned_vehicle = None
        incident.assigned_operator = None
        incident.save(update_fields=("assigned_vehicle", "assigned_operator", "updated_at"))
        return
    vehicle.current_incident = None
    if vehicle.availability == AmbulanceVehicle.Availability.ON_CALL:
        vehicle.availability = AmbulanceVehicle.Availability.AVAILABLE
    vehicle.save(update_fields=("current_incident", "availability", "updated_at"))
    incident.assigned_vehicle = None
    incident.assigned_operator = None
    incident.save(
        update_fields=("assigned_vehicle", "assigned_operator", "updated_at")
    )