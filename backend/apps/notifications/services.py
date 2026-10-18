from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.patients.models import ConsentRecord, EmergencyContact

from .models import EscalationPolicy, IncidentNotification, NotificationEvent


ALLOWED_TRANSITIONS = {
    IncidentNotification.Status.QUEUED: {IncidentNotification.Status.PROCESSING},
    IncidentNotification.Status.PROCESSING: {
        IncidentNotification.Status.SUBMITTED,
        IncidentNotification.Status.FAILED,
        IncidentNotification.Status.SUBMISSION_UNKNOWN,
        IncidentNotification.Status.DELIVERED,
    },
    IncidentNotification.Status.SUBMITTED: {
        IncidentNotification.Status.DELIVERED,
        IncidentNotification.Status.FAILED,
    },
    IncidentNotification.Status.SUBMISSION_UNKNOWN: {
        IncidentNotification.Status.SUBMITTED,
        IncidentNotification.Status.DELIVERED,
        IncidentNotification.Status.FAILED,
        IncidentNotification.Status.QUEUED,
    },
    IncidentNotification.Status.FAILED: {IncidentNotification.Status.QUEUED},
    IncidentNotification.Status.DELIVERED: {
        IncidentNotification.Status.ACKNOWLEDGED,
    },
    IncidentNotification.Status.ACKNOWLEDGED: set(),
}


@transaction.atomic
def queue_incident_notifications(incident):
    consent = (
        ConsentRecord.objects.filter(
            patient=incident.patient,
            scope=ConsentRecord.Scope.EMERGENCY_CONTACTS,
        )
        .order_by("-recorded_at", "-created_at")
        .first()
    )
    if consent is None or consent.status != ConsentRecord.Status.GRANTED:
        return 0

    contacts = EmergencyContact.objects.filter(
        patient=incident.patient,
        verification_status=EmergencyContact.VerificationStatus.VERIFIED,
    ).exclude(phone_number="")
    queued = 0
    for contact in contacts:
        preferences = contact.notification_preferences
        if isinstance(preferences, dict) and preferences.get("sms") is False:
            continue
        notification, created = IncidentNotification.objects.get_or_create(
            incident=incident,
            emergency_contact=contact,
            channel=IncidentNotification.Channel.SMS,
            defaults={"recipient_address_snapshot": contact.phone_number},
        )
        if created:
            NotificationEvent.objects.create(
                notification=notification,
                event_type=IncidentNotification.Status.QUEUED,
                details={"channel": IncidentNotification.Channel.SMS},
            )
            queued += 1
    return queued


@transaction.atomic
def transition_notification(
    *,
    notification,
    new_status,
    actor=None,
    provider_name=None,
    provider_task_id=None,
    provider_message_id=None,
    failure_code=None,
):
    notification = IncidentNotification.objects.select_for_update().get(pk=notification.pk)
    allowed = ALLOWED_TRANSITIONS.get(notification.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition notification from {notification.status} to {new_status}."
        )

    now = timezone.now()
    notification.status = new_status
    update_fields = ["status", "updated_at"]
    if new_status in (
        IncidentNotification.Status.PROCESSING,
        IncidentNotification.Status.SUBMITTED,
        IncidentNotification.Status.FAILED,
        IncidentNotification.Status.SUBMISSION_UNKNOWN,
    ):
        notification.last_attempt_at = now
        notification.next_attempt_at = None
        update_fields.extend(("last_attempt_at", "next_attempt_at"))
    if new_status == IncidentNotification.Status.PROCESSING:
        notification.processing_started_at = now
        update_fields.append("processing_started_at")
    elif notification.processing_started_at is not None:
        notification.processing_started_at = None
        update_fields.append("processing_started_at")
    if new_status == IncidentNotification.Status.SUBMITTED:
        notification.submitted_at = now
        update_fields.append("submitted_at")
    elif new_status == IncidentNotification.Status.DELIVERED:
        notification.delivered_at = now
        update_fields.append("delivered_at")
    elif new_status == IncidentNotification.Status.ACKNOWLEDGED:
        notification.acknowledged_at = now
        update_fields.append("acknowledged_at")
    elif new_status == IncidentNotification.Status.QUEUED:
        notification.retry_count += 1
        notification.failure_code = ""
        update_fields.extend(("retry_count", "failure_code"))

    if provider_message_id is not None:
        notification.provider_message_id = provider_message_id
        update_fields.append("provider_message_id")
    if provider_task_id is not None:
        notification.provider_task_id = provider_task_id
        update_fields.append("provider_task_id")
    if provider_name is not None:
        notification.provider_name = provider_name
        update_fields.append("provider_name")
    if failure_code is not None:
        notification.failure_code = failure_code
        update_fields.append("failure_code")
    notification.save(update_fields=update_fields)
    NotificationEvent.objects.create(
        notification=notification,
        event_type=new_status,
        actor=actor,
        details={
            key: value
            for key, value in (
                ("failure_code", failure_code),
                ("provider_name", provider_name),
                ("provider_task_id", provider_task_id),
                ("provider_message_id", provider_message_id),
            )
            if value
        },
    )
    return notification


@transaction.atomic
def claim_notification(*, notification_id, provider_name):
    notification = IncidentNotification.objects.select_for_update().get(pk=notification_id)
    if notification.status != IncidentNotification.Status.QUEUED:
        return None
    return transition_notification(
        notification=notification,
        new_status=IncidentNotification.Status.PROCESSING,
        provider_name=provider_name,
    )


@transaction.atomic
def record_submission(*, notification, provider_name, provider_task_id):
    notification = IncidentNotification.objects.select_for_update().get(pk=notification.pk)
    if notification.provider_name != provider_name:
        raise ValueError("Notification provider does not match the submission.")
    if notification.provider_task_id and notification.provider_task_id != provider_task_id:
        raise ValueError("Provider task ID does not match the notification.")
    if notification.status == IncidentNotification.Status.PROCESSING:
        return transition_notification(
            notification=notification,
            new_status=IncidentNotification.Status.SUBMITTED,
            provider_name=provider_name,
            provider_task_id=provider_task_id,
        )
    if notification.status in (
        IncidentNotification.Status.SUBMITTED,
        IncidentNotification.Status.DELIVERED,
        IncidentNotification.Status.FAILED,
    ):
        if not notification.provider_task_id:
            notification.provider_task_id = provider_task_id
            notification.save(update_fields=("provider_task_id", "updated_at"))
        return notification
    raise ValueError(f"Cannot record submission while notification is {notification.status}.")


@transaction.atomic
def apply_sasusync_status(
    *,
    notification_id,
    message_id,
    recipient,
    provider_status,
    event_at,
):
    notification = IncidentNotification.objects.select_for_update().get(pk=notification_id)
    if notification.provider_name != "sasusync":
        raise ValueError("Notification was not submitted through SasuSync.")
    if (
        message_id
        and notification.provider_message_id
        and notification.provider_message_id != message_id
    ):
        raise ValueError("SasuSync message ID does not match the notification.")

    if recipient:
        normalized_recipient = "".join(character for character in recipient if character.isdigit())
        expected_recipient = "".join(
            character
            for character in notification.recipient_address_snapshot
            if character.isdigit()
        )
        if normalized_recipient != expected_recipient:
            raise ValueError("SasuSync recipient does not match the notification.")
    if (
        notification.provider_status_updated_at is not None
        and event_at <= notification.provider_status_updated_at
    ):
        return notification

    status_map = {
        "sent": IncidentNotification.Status.SUBMITTED,
        "delivered": IncidentNotification.Status.DELIVERED,
        "failed": IncidentNotification.Status.FAILED,
        "expired": IncidentNotification.Status.FAILED,
    }
    target_status = status_map.get(provider_status)
    if target_status is None:
        return notification

    if target_status == notification.status:
        return notification

    previous_status = notification.status
    notification.status = target_status
    if message_id:
        notification.provider_message_id = message_id
    notification.provider_status_updated_at = event_at
    notification.processing_started_at = None
    update_fields = [
        "status",
        "provider_message_id",
        "provider_status_updated_at",
        "processing_started_at",
        "updated_at",
    ]
    if notification.submitted_at is None:
        notification.submitted_at = event_at
        update_fields.append("submitted_at")
    if target_status == IncidentNotification.Status.DELIVERED:
        notification.delivered_at = event_at
        update_fields.append("delivered_at")
    if target_status == IncidentNotification.Status.FAILED:
        notification.failure_code = provider_status
        update_fields.append("failure_code")
    else:
        notification.failure_code = ""
        update_fields.append("failure_code")
    notification.save(update_fields=update_fields)
    NotificationEvent.objects.create(
        notification=notification,
        event_type=target_status,
        details={
            "provider": "sasusync",
            "provider_message_id": message_id,
            "provider_timestamp": event_at.isoformat(),
            "provider_status": provider_status,
            "previous_status": previous_status,
        },
    )
    return notification


@transaction.atomic
def reconcile_sasusync_status_snapshot(*, notification, snapshot):
    notification = IncidentNotification.objects.select_for_update().get(pk=notification.pk)
    if notification.provider_name != "sasusync" or snapshot.get("stale") is True:
        return notification
    response_task_id = snapshot.get("task_id")
    if response_task_id and response_task_id != notification.provider_task_id:
        return notification

    messages = snapshot.get("messages")
    message = None
    if isinstance(messages, list) and messages:
        expected_recipient = "".join(
            character
            for character in notification.recipient_address_snapshot
            if character.isdigit()
        )
        message = next(
            (
                item
                for item in messages
                if isinstance(item, dict)
                and "".join(
                    character for character in str(item.get("recipient", "")) if character.isdigit()
                )
                == expected_recipient
            ),
            None,
        )
        if message is None:
            return notification

    provider_status = str(
        (message or {}).get("status") or snapshot.get("delivery_status", "")
    )
    if provider_status in {"pending", "unknown", "partial"}:
        return notification
    message_id = str((message or {}).get("message_id") or notification.provider_message_id)
    recipient = str(
        (message or {}).get("recipient") or notification.recipient_address_snapshot
    )

    return apply_sasusync_status(
        notification_id=notification.pk,
        message_id=message_id,
        recipient=recipient,
        provider_status=provider_status,
        event_at=timezone.now(),
    )


def get_default_escalation_policy():
    policy, _ = EscalationPolicy.objects.get_or_create(singleton_key="default")
    return policy


@transaction.atomic
def schedule_retry_attempt(*, notification, policy=None, reason=""):
    policy = policy or get_default_escalation_policy()
    notification = IncidentNotification.objects.select_for_update().get(pk=notification.pk)
    if notification.retry_count >= policy.max_retry_attempts:
        if notification.failure_code != "max_retries_exhausted":
            notification.failure_code = "max_retries_exhausted"
            notification.next_attempt_at = None
            notification.save(update_fields=("failure_code", "next_attempt_at", "updated_at"))
        return notification

    next_attempt = timezone.now() + timedelta(minutes=policy.retry_interval_minutes)
    notification.next_attempt_at = next_attempt
    if notification.status == IncidentNotification.Status.PROCESSING:
        notification.status = IncidentNotification.Status.SUBMISSION_UNKNOWN
    if reason:
        notification.failure_code = reason[:80]
    notification.save(update_fields=("status", "next_attempt_at", "failure_code", "updated_at"))
    return notification


@transaction.atomic
def recover_stuck_processing_notifications(*, policy=None, now=None, limit=200):
    policy = policy or get_default_escalation_policy()
    now = now or timezone.now()
    stuck_before = now - timedelta(minutes=policy.initial_notification_timeout_minutes)
    notifications = (
        IncidentNotification.objects.select_for_update()
        .filter(
            status=IncidentNotification.Status.PROCESSING,
            processing_started_at__isnull=False,
            processing_started_at__lte=stuck_before,
        )
        .order_by("processing_started_at")[:limit]
    )
    recovered = 0
    for notification in notifications:
        transition_notification(
            notification=notification,
            new_status=IncidentNotification.Status.SUBMISSION_UNKNOWN,
            failure_code="processing_timeout",
        )
        schedule_retry_attempt(
            notification=notification,
            policy=policy,
            reason="processing_timeout",
        )
        recovered += 1
    return recovered


@transaction.atomic
def queue_due_notification_retries(*, policy=None, now=None, limit=200):
    policy = policy or get_default_escalation_policy()
    now = now or timezone.now()
    pending = (
        IncidentNotification.objects.select_for_update()
        .filter(
            status__in=(
                IncidentNotification.Status.FAILED,
                IncidentNotification.Status.SUBMISSION_UNKNOWN,
            ),
            next_attempt_at__isnull=False,
            next_attempt_at__lte=now,
        )
        .order_by("next_attempt_at")[:limit]
    )
    queued = 0
    exhausted = 0
    for notification in pending:
        if notification.retry_count >= policy.max_retry_attempts:
            notification.next_attempt_at = None
            notification.failure_code = "max_retries_exhausted"
            notification.save(update_fields=("next_attempt_at", "failure_code", "updated_at"))
            exhausted += 1
            continue
        transition_notification(
            notification=notification,
            new_status=IncidentNotification.Status.QUEUED,
        )
        queued += 1
    return queued, exhausted