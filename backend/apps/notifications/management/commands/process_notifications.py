from django.core.management.base import BaseCommand, CommandError

from apps.notifications.models import IncidentNotification
from apps.notifications.providers import (
    ProviderConfigurationError,
    ProviderRejectedError,
    ProviderSubmissionUnknownError,
    SasuSyncSmsProvider,
)
from apps.notifications.services import claim_notification, record_submission, transition_notification
from apps.notifications.services import (
    get_default_escalation_policy,
    queue_due_notification_retries,
    recover_stuck_processing_notifications,
    schedule_retry_attempt,
)


class Command(BaseCommand):
    help = "Submit queued notifications through the explicitly selected provider."

    def add_arguments(self, parser):
        provider_group = parser.add_mutually_exclusive_group(required=True)
        provider_group.add_argument(
            "--sandbox",
            action="store_true",
            help="Use SasuSync's free sandbox endpoint; it does not deliver messages.",
        )
        provider_group.add_argument(
            "--sasusync",
            action="store_true",
            help="Send real SMS through SasuSync using configured credentials.",
        )
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        if options["sandbox"] == options["sasusync"]:
            raise CommandError("Select exactly one mode: --sandbox or --sasusync.")
        if options["limit"] < 1:
            raise CommandError("--limit must be greater than zero.")
        policy = get_default_escalation_policy()

        try:
            provider = SasuSyncSmsProvider(sandbox=options["sandbox"])
        except ProviderConfigurationError as error:
            raise CommandError(str(error)) from error
        recovered = recover_stuck_processing_notifications(policy=policy, limit=options["limit"])
        retried, exhausted = queue_due_notification_retries(policy=policy, limit=options["limit"])

        notification_ids = IncidentNotification.objects.filter(
            status=IncidentNotification.Status.QUEUED,
        ).order_by("created_at").values_list("pk", flat=True)[: options["limit"]]

        submitted = 0
        rejected = 0
        unknown = 0
        for notification_id in notification_ids:
            notification = claim_notification(
                notification_id=notification_id,
                provider_name=provider.provider_name,
            )
            if notification is None:
                continue
            try:
                result = provider.submit(notification, idempotency_key=str(notification.pk))
            except ProviderRejectedError as error:
                failed = transition_notification(
                    notification=notification,
                    new_status=IncidentNotification.Status.FAILED,
                    failure_code=error.failure_code,
                )
                schedule_retry_attempt(
                    notification=failed,
                    policy=policy,
                    reason=error.failure_code,
                )
                rejected += 1
            except ProviderSubmissionUnknownError:
                unknown_notification = transition_notification(
                    notification=notification,
                    new_status=IncidentNotification.Status.SUBMISSION_UNKNOWN,
                    failure_code="submission_outcome_unknown",
                )
                schedule_retry_attempt(
                    notification=unknown_notification,
                    policy=policy,
                    reason="submission_outcome_unknown",
                )
                unknown += 1
            else:
                record_submission(
                    notification=notification,
                    provider_name=result.provider_name,
                    provider_task_id=result.task_id,
                )
                submitted += 1

        unknown_open = IncidentNotification.objects.filter(
            status=IncidentNotification.Status.SUBMISSION_UNKNOWN
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Recovered processing: {recovered}; due retries queued: {retried}; retries exhausted: {exhausted}; "
                f"submitted: {submitted}; rejected: {rejected}; outcome unknown: {unknown}; "
                f"open submission_unknown: {unknown_open}. "
                "Submission does not mean delivered."
            )
        )