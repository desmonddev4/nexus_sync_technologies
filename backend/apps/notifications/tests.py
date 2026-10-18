import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
import requests

from apps.incidents.models import Incident
from apps.notifications.models import IncidentNotification, NotificationEvent
from apps.notifications.providers import (
    ProviderConfigurationError,
    ProviderLookupError,
    ProviderRejectedError,
    ProviderSubmissionUnknownError,
    SasuSyncSmsProvider,
    SubmissionResult,
)
from apps.notifications.services import (
    apply_sasusync_status,
    claim_notification,
    queue_due_notification_retries,
    reconcile_sasusync_status_snapshot,
    record_submission,
    recover_stuck_processing_notifications,
    schedule_retry_attempt,
    transition_notification,
)
from apps.patients.models import Patient


class NotificationTransitionTests(TestCase):
    def setUp(self):
        patient = Patient.objects.create(full_name="Notification Patient")
        incident = Incident.objects.create(
            patient=patient,
            source_event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
        )
        self.notification = IncidentNotification.objects.create(
            incident=incident,
            recipient_address_snapshot="+233200000001",
            channel=IncidentNotification.Channel.SMS,
        )

    def test_delivery_transitions_preserve_provider_status_history(self):
        processing = claim_notification(
            notification_id=self.notification.pk,
            provider_name="test-provider",
        )
        submitted = transition_notification(
            notification=processing,
            new_status=IncidentNotification.Status.SUBMITTED,
            provider_message_id="provider-message-1",
        )
        delivered = transition_notification(
            notification=submitted,
            new_status=IncidentNotification.Status.DELIVERED,
        )

        self.assertEqual(delivered.status, IncidentNotification.Status.DELIVERED)
        self.assertEqual(delivered.provider_message_id, "provider-message-1")
        self.assertIsNotNone(delivered.submitted_at)
        self.assertIsNotNone(delivered.delivered_at)
        self.assertEqual(NotificationEvent.objects.count(), 3)

    def test_failed_notification_can_be_requeued_and_counted(self):
        processing = claim_notification(
            notification_id=self.notification.pk,
            provider_name="test-provider",
        )
        failed = transition_notification(
            notification=processing,
            new_status=IncidentNotification.Status.FAILED,
            failure_code="temporary_provider_error",
        )
        queued = transition_notification(
            notification=failed,
            new_status=IncidentNotification.Status.QUEUED,
        )

        self.assertEqual(queued.retry_count, 1)
        self.assertEqual(queued.status, IncidentNotification.Status.QUEUED)
        self.assertEqual(queued.failure_code, "")
        self.assertEqual(NotificationEvent.objects.count(), 3)

    def test_invalid_delivery_transition_is_rejected(self):
        with self.assertRaises(ValueError):
            transition_notification(
                notification=self.notification,
                new_status=IncidentNotification.Status.DELIVERED,
            )

    def test_stuck_processing_is_recovered_to_submission_unknown_and_scheduled(self):
        processing = claim_notification(
            notification_id=self.notification.pk,
            provider_name="test-provider",
        )
        processing.processing_started_at = timezone.now() - timedelta(minutes=30)
        processing.save(update_fields=("processing_started_at", "updated_at"))

        recovered_count = recover_stuck_processing_notifications(limit=10)

        self.assertEqual(recovered_count, 1)
        processing.refresh_from_db()
        self.assertEqual(processing.status, IncidentNotification.Status.SUBMISSION_UNKNOWN)
        self.assertEqual(processing.failure_code, "processing_timeout")
        self.assertIsNotNone(processing.next_attempt_at)

    def test_due_submission_unknown_is_requeued_for_retry(self):
        processing = claim_notification(
            notification_id=self.notification.pk,
            provider_name="test-provider",
        )
        unknown = transition_notification(
            notification=processing,
            new_status=IncidentNotification.Status.SUBMISSION_UNKNOWN,
            failure_code="submission_outcome_unknown",
        )
        scheduled = schedule_retry_attempt(
            notification=unknown,
            reason="submission_outcome_unknown",
        )
        scheduled.next_attempt_at = timezone.now() - timedelta(minutes=1)
        scheduled.save(update_fields=("next_attempt_at", "updated_at"))

        queued_count, exhausted = queue_due_notification_retries(limit=10)

        self.assertEqual(queued_count, 1)
        self.assertEqual(exhausted, 0)
        scheduled.refresh_from_db()
        self.assertEqual(scheduled.status, IncidentNotification.Status.QUEUED)
        self.assertEqual(scheduled.retry_count, 1)
        self.assertEqual(scheduled.failure_code, "")

    @patch("apps.notifications.management.commands.process_notifications.SasuSyncSmsProvider")
    def test_sandbox_command_submits_without_claiming_delivery(self, provider_class):
        provider = provider_class.return_value
        provider.provider_name = "sasusync-sandbox"
        provider.submit.return_value = SubmissionResult("sasusync-sandbox", "sandbox-task-1")
        output = StringIO()

        call_command("process_notifications", sandbox=True, stdout=output)

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, IncidentNotification.Status.SUBMITTED)
        self.assertEqual(self.notification.provider_name, "sasusync-sandbox")
        self.assertEqual(self.notification.provider_task_id, "sandbox-task-1")
        self.assertIsNone(self.notification.delivered_at)
        self.assertIn("does not mean delivered", output.getvalue())
        provider_class.assert_called_once_with(sandbox=True)

    def test_notification_command_requires_explicit_sandbox_mode(self):
        with self.assertRaises(CommandError):
            call_command("process_notifications")

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, IncidentNotification.Status.QUEUED)


class SasuSyncIntegrationTests(TestCase):
    base_url = "https://sms.sasusync.com"
    webhook_path = "/api/v1/integrations/sasusync/webhook/"
    webhook_secret = "test-webhook-secret"

    def setUp(self):
        patient = Patient.objects.create(full_name="SasuSync Test Patient")
        incident = Incident.objects.create(
            patient=patient,
            source_event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
        )
        self.notification = IncidentNotification.objects.create(
            incident=incident,
            recipient_address_snapshot="+233200000001",
            channel=IncidentNotification.Channel.SMS,
        )

    @override_settings(
        SASUSYNC_API_KEY="ss-test-key",
        SASUSYNC_SENDER_ID="NexusSync",
        SASUSYNC_BASE_URL=base_url,
    )
    def test_sandbox_send_uses_documented_request_and_returns_task_id(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "success": True,
            "data": {"status": "queued", "task_id": "task-123"},
        }
        session = Mock()
        session.post.return_value = response
        provider = SasuSyncSmsProvider(sandbox=True, session=session, sleep=Mock())

        result = provider.submit(self.notification, idempotency_key=str(self.notification.pk))

        self.assertEqual(result, SubmissionResult("sasusync-sandbox", "task-123"))
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], f"{self.base_url}/smssandbox/v1/send")
        self.assertEqual(kwargs["headers"]["X-API-Key"], "ss-test-key")
        self.assertEqual(kwargs["json"]["sender"], "NexusSync")
        self.assertEqual(kwargs["json"]["recipients"], ["+233200000001"])
        self.assertEqual(
            kwargs["json"]["metadata"]["notification_id"],
            str(self.notification.pk),
        )

    @override_settings(
        SASUSYNC_API_KEY="ss-test-key",
        SASUSYNC_SENDER_ID="NexusSync",
        SASUSYNC_BASE_URL=base_url,
    )
    def test_live_send_uses_live_endpoint(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "success": True,
            "data": {"status": "queued", "task_id": "task-live"},
        }
        session = Mock()
        session.post.return_value = response
        provider = SasuSyncSmsProvider(session=session, sleep=Mock())

        provider.submit(self.notification, idempotency_key=str(self.notification.pk))

        self.assertEqual(session.post.call_args.args[0], f"{self.base_url}/api/v1/send")

    @override_settings(SASUSYNC_API_KEY="", SASUSYNC_SENDER_ID="")
    def test_provider_requires_key_and_approved_sender_configuration(self):
        with self.assertRaises(ProviderConfigurationError):
            SasuSyncSmsProvider()

    @override_settings(
        SASUSYNC_API_KEY="ss-test-key",
        SASUSYNC_SENDER_ID="NexusSync",
        SASUSYNC_BASE_URL=base_url,
    )
    def test_definitive_http_rejection_is_not_retried(self):
        response = Mock(status_code=403)
        session = Mock()
        session.post.return_value = response
        provider = SasuSyncSmsProvider(session=session, sleep=Mock())

        with self.assertRaises(ProviderRejectedError) as error:
            provider.submit(self.notification, idempotency_key=str(self.notification.pk))

        self.assertEqual(error.exception.failure_code, "403")
        session.post.assert_called_once()

    @override_settings(
        SASUSYNC_API_KEY="ss-test-key",
        SASUSYNC_SENDER_ID="NexusSync",
        SASUSYNC_BASE_URL=base_url,
    )
    def test_retryable_server_error_uses_backoff_before_success(self):
        unavailable = Mock(status_code=503)
        accepted = Mock(status_code=200)
        accepted.json.return_value = {
            "success": True,
            "data": {"status": "queued", "task_id": "task-retry"},
        }
        session = Mock()
        session.post.side_effect = [unavailable, accepted]
        sleeper = Mock()
        provider = SasuSyncSmsProvider(session=session, sleep=sleeper)

        result = provider.submit(self.notification, idempotency_key=str(self.notification.pk))

        self.assertEqual(result.task_id, "task-retry")
        self.assertEqual(session.post.call_count, 2)
        sleeper.assert_called_once_with(1)

    @override_settings(
        SASUSYNC_API_KEY="ss-test-key",
        SASUSYNC_SENDER_ID="NexusSync",
        SASUSYNC_BASE_URL=base_url,
    )
    def test_network_timeout_is_ambiguous_and_never_blindly_retried(self):
        session = Mock()
        session.post.side_effect = requests.Timeout()
        provider = SasuSyncSmsProvider(session=session, sleep=Mock())

        with self.assertRaises(ProviderSubmissionUnknownError):
            provider.submit(self.notification, idempotency_key=str(self.notification.pk))

        session.post.assert_called_once()

    @override_settings(
        SASUSYNC_API_KEY="ss-test-key",
        SASUSYNC_SENDER_ID="",
        SASUSYNC_BASE_URL=base_url,
    )
    def test_status_lookup_uses_task_endpoint_without_sender_id(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "success": True,
            "task_id": "task-123",
            "delivery_status": "delivered",
            "messages": [
                {
                    "message_id": "message-123",
                    "recipient": "233200000001",
                    "status": "delivered",
                }
            ],
        }
        session = Mock()
        session.get.return_value = response
        provider = SasuSyncSmsProvider(session=session, sleep=Mock(), require_sender=False)

        result = provider.fetch_status("task-123")

        self.assertEqual(result["delivery_status"], "delivered")
        self.assertEqual(
            session.get.call_args.args[0],
            f"{self.base_url}/api/v1/status/task-123",
        )
        self.assertEqual(session.get.call_args.kwargs["headers"]["X-API-Key"], "ss-test-key")

    def test_status_snapshot_updates_live_notification_but_ignores_stale_snapshot(self):
        self.notification.status = IncidentNotification.Status.SUBMITTED
        self.notification.provider_name = "sasusync"
        self.notification.provider_task_id = "task-123"
        self.notification.save(
            update_fields=("status", "provider_name", "provider_task_id", "updated_at")
        )
        snapshot = {
            "success": True,
            "task_id": "task-123",
            "delivery_status": "delivered",
            "messages": [
                {
                    "message_id": "message-123",
                    "recipient": "233200000001",
                    "status": "delivered",
                }
            ],
        }

        updated = reconcile_sasusync_status_snapshot(
            notification=self.notification,
            snapshot=snapshot,
        )
        stale = reconcile_sasusync_status_snapshot(
            notification=updated,
            snapshot={**snapshot, "stale": True, "delivery_status": "failed"},
        )

        self.assertEqual(updated.status, IncidentNotification.Status.DELIVERED)
        self.assertEqual(stale.status, IncidentNotification.Status.DELIVERED)

    def test_compact_final_status_reconciles_without_message_details(self):
        self.notification.status = IncidentNotification.Status.SUBMITTED
        self.notification.provider_name = "sasusync"
        self.notification.provider_task_id = "task-compact"
        self.notification.save(
            update_fields=("status", "provider_name", "provider_task_id", "updated_at")
        )
        snapshot = {
            "success": True,
            "delivery_status": "delivered",
        }

        reconciled = reconcile_sasusync_status_snapshot(
            notification=self.notification,
            snapshot=snapshot,
        )
        event_count = NotificationEvent.objects.count()
        replay = reconcile_sasusync_status_snapshot(
            notification=reconciled,
            snapshot=snapshot,
        )

        self.assertEqual(reconciled.status, IncidentNotification.Status.DELIVERED)
        self.assertEqual(replay.status, IncidentNotification.Status.DELIVERED)
        self.assertEqual(NotificationEvent.objects.count(), event_count)

    @override_settings(
        SASUSYNC_API_KEY="ss-test-key",
        SASUSYNC_SENDER_ID="",
        SASUSYNC_BASE_URL=base_url,
    )
    @patch("apps.notifications.management.commands.reconcile_sasusync_status.SasuSyncSmsProvider")
    def test_reconcile_command_updates_only_live_submitted_messages(self, provider_class):
        live = IncidentNotification.objects.create(
            incident=self.notification.incident,
            recipient_address_snapshot="+233200000002",
            channel=IncidentNotification.Channel.SMS,
            status=IncidentNotification.Status.SUBMITTED,
            provider_name="sasusync",
            provider_task_id="task-live",
        )
        sandbox = IncidentNotification.objects.create(
            incident=self.notification.incident,
            recipient_address_snapshot="+233200000003",
            channel=IncidentNotification.Channel.SMS,
            status=IncidentNotification.Status.SUBMITTED,
            provider_name="sasusync-sandbox",
            provider_task_id="task-sandbox",
        )
        provider = provider_class.return_value
        provider.fetch_status.return_value = {
            "success": True,
            "task_id": "task-live",
            "delivery_status": "delivered",
            "messages": [
                {
                    "message_id": "message-live",
                    "recipient": "233200000002",
                    "status": "delivered",
                }
            ],
        }
        output = StringIO()

        call_command("reconcile_sasusync_status", stdout=output)

        live.refresh_from_db()
        sandbox.refresh_from_db()
        self.assertEqual(live.status, IncidentNotification.Status.DELIVERED)
        self.assertEqual(sandbox.status, IncidentNotification.Status.SUBMITTED)
        provider.fetch_status.assert_called_once_with("task-live")

    @override_settings(SASUSYNC_WEBHOOK_SECRET=webhook_secret)
    def test_signed_webhook_marks_delivery_and_deduplicates_replays(self):
        claim_notification(notification_id=self.notification.pk, provider_name="sasusync")
        payload = self.webhook_payload("delivered", "2026-10-17T18:05:00Z")

        first = self.post_webhook(payload)
        replay = self.post_webhook(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, IncidentNotification.Status.DELIVERED)
        self.assertEqual(self.notification.provider_message_id, "message-123")
        self.assertEqual(NotificationEvent.objects.count(), 2)

    @override_settings(SASUSYNC_WEBHOOK_SECRET=webhook_secret)
    def test_newer_provider_timestamp_wins_over_out_of_order_events(self):
        claim_notification(notification_id=self.notification.pk, provider_name="sasusync")
        self.post_webhook(self.webhook_payload("delivered", "2026-10-17T18:05:00Z"))
        self.post_webhook(self.webhook_payload("failed", "2026-10-17T18:04:00Z"))

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, IncidentNotification.Status.DELIVERED)

        self.post_webhook(self.webhook_payload("failed", "2026-10-17T18:06:00Z"))
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, IncidentNotification.Status.FAILED)

    @override_settings(SASUSYNC_WEBHOOK_SECRET=webhook_secret)
    def test_invalid_webhook_signature_is_rejected(self):
        payload = self.webhook_payload("delivered", "2026-10-17T18:05:00Z")
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        response = APIClient().generic(
            "POST",
            self.webhook_path,
            raw_body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="invalid",
        )

        self.assertEqual(response.status_code, 403)

    def webhook_payload(self, status, timestamp):
        return {
            "event": status,
            "timestamp": timestamp,
            "data": {
                "message_id": "message-123",
                "recipient": "233200000001",
                "status": status,
                "metadata": {"notification_id": str(self.notification.pk)},
            },
        }

    def post_webhook(self, payload):
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return APIClient().generic(
            "POST",
            self.webhook_path,
            raw_body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )