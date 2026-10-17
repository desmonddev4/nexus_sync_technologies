from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.incidents.models import Incident
from apps.incidents.services import create_measurement_alert

from .models import Measurement, MonitoringRule, MonitoringRuleEvaluation, PatientLocation


@transaction.atomic
def ingest_measurement(*, data, actor):
    values = {**data, "recorded_by": actor}
    measurement, created = Measurement.objects.get_or_create(
        patient=data["patient"],
        event_id=data["event_id"],
        defaults=values,
    )
    if created:
        evaluate_measurement_for_rules(measurement)
    return measurement, created


@transaction.atomic
def evaluate_measurement_for_rules(measurement):
    rule_ids = MonitoringRule.objects.filter(
        measurement_type=measurement.measurement_type,
        is_enabled=True,
        reviewed_by__isnull=False,
        reviewed_at__isnull=False,
    ).values_list("pk", flat=True)
    return [
        evaluate_measurement_against_rule(measurement=measurement, rule_id=rule_id)
        for rule_id in rule_ids
    ]


@transaction.atomic
def evaluate_measurement_against_rule(*, measurement, rule_id):
    rule = MonitoringRule.objects.select_for_update().get(pk=rule_id)
    existing = MonitoringRuleEvaluation.objects.filter(
        rule=rule,
        measurement=measurement,
    ).first()
    if existing:
        return existing

    details = {
        "rule_id": str(rule.pk),
        "rule_name": rule.name,
        "rule_version": rule.version,
        "measurement_id": str(measurement.pk),
        "measurement_type": measurement.measurement_type,
        "measurement_source": measurement.source,
        "value": str(measurement.value),
        "unit": measurement.unit,
        "threshold": str(rule.threshold),
        "operator": rule.operator,
    }
    if measurement.quality != Measurement.Quality.ACCEPTABLE:
        return MonitoringRuleEvaluation.objects.create(
            rule=rule,
            measurement=measurement,
            status=MonitoringRuleEvaluation.Status.QUALITY_REJECTED,
            details={**details, "quality": measurement.quality},
        )
    if (
        measurement.source == Measurement.Source.SIMULATOR
        and not rule.include_simulated
    ):
        return MonitoringRuleEvaluation.objects.create(
            rule=rule,
            measurement=measurement,
            status=MonitoringRuleEvaluation.Status.SIMULATED_SKIPPED,
            details=details,
        )
    if measurement.measured_at < timezone.now() - timedelta(minutes=5):
        return MonitoringRuleEvaluation.objects.create(
            rule=rule,
            measurement=measurement,
            status=MonitoringRuleEvaluation.Status.STALE_READING,
            details={**details, "maximum_age_seconds": 300},
        )

    comparison = {
        MonitoringRule.Operator.GREATER_THAN: lambda value: value > rule.threshold,
        MonitoringRule.Operator.GREATER_THAN_OR_EQUAL: lambda value: value >= rule.threshold,
        MonitoringRule.Operator.LESS_THAN: lambda value: value < rule.threshold,
        MonitoringRule.Operator.LESS_THAN_OR_EQUAL: lambda value: value <= rule.threshold,
    }[rule.operator]
    window_start = measurement.measured_at - timedelta(seconds=rule.lookback_window_seconds)
    readings = list(
        Measurement.objects.filter(
            patient=measurement.patient,
            measurement_type=measurement.measurement_type,
            source=measurement.source,
            quality=Measurement.Quality.ACCEPTABLE,
            measured_at__gte=window_start,
            measured_at__lte=measurement.measured_at,
        )
        .order_by("-measured_at", "-received_at")[: rule.minimum_consecutive_readings]
    )
    details["consecutive_readings_required"] = rule.minimum_consecutive_readings
    details["consecutive_readings_found"] = len(readings)
    if len(readings) < rule.minimum_consecutive_readings:
        return MonitoringRuleEvaluation.objects.create(
            rule=rule,
            measurement=measurement,
            status=MonitoringRuleEvaluation.Status.INSUFFICIENT_READINGS,
            details=details,
        )
    if any(not comparison(reading.value) for reading in readings):
        return MonitoringRuleEvaluation.objects.create(
            rule=rule,
            measurement=measurement,
            status=MonitoringRuleEvaluation.Status.NO_MATCH,
            details=details,
        )

    active_statuses = (
        Incident.Status.CREATED,
        Incident.Status.ACKNOWLEDGED,
        Incident.Status.RESPONDER_ASSIGNED,
        Incident.Status.DISPATCH_REQUESTED,
        Incident.Status.DISPATCH_CONFIRMED,
        Incident.Status.RESPONDER_EN_ROUTE,
        Incident.Status.ARRIVED,
    )
    existing_active = (
        MonitoringRuleEvaluation.objects.filter(
            rule=rule,
            measurement__patient=measurement.patient,
            incident__status__in=active_statuses,
        )
        .exclude(incident__isnull=True)
        .select_related("incident")
        .order_by("-created_at")
        .first()
    )
    if existing_active:
        incident = existing_active.incident
        evaluation_status = MonitoringRuleEvaluation.Status.LINKED_TO_ACTIVE_INCIDENT
        details["active_incident_id"] = str(incident.pk)
        from apps.incidents.models import IncidentEvent

        IncidentEvent.objects.create(
            incident=incident,
            event_type=IncidentEvent.Type.EVIDENCE_RECORDED,
            details=details,
        )
    else:
        incident, _ = create_measurement_alert(measurement=measurement, rule=rule, details=details)
        evaluation_status = MonitoringRuleEvaluation.Status.TRIGGERED

    return MonitoringRuleEvaluation.objects.create(
        rule=rule,
        measurement=measurement,
        incident=incident,
        status=evaluation_status,
        details=details,
    )


@transaction.atomic
def ingest_patient_location(*, data, actor):
    values = {**data, "recorded_by": actor}
    return PatientLocation.objects.get_or_create(
        patient=data["patient"],
        event_id=data["event_id"],
        defaults=values,
    )