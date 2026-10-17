from django.core.management.base import BaseCommand, CommandError

from apps.notifications.models import IncidentNotification
from apps.notifications.providers import (
    ProviderConfigurationError,
    ProviderRejectedError,
    ProviderSubmissionUnknownError,
    SasuSyncSmsProvider,
)
from apps.notifications.services import claim_notification, record_submission, transition_notification


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

        try:
            provider = SasuSyncSmsProvider(sandbox=options["sandbox"])
        except ProviderConfigurationError as error:
            raise CommandError(str(error)) from error
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
                transition_notification(
                    notification=notification,
                    new_status=IncidentNotification.Status.FAILED,
                    failure_code=error.failure_code,
                )
                rejected += 1
            except ProviderSubmissionUnknownError:
                transition_notification(
                    notification=notification,
                    new_status=IncidentNotification.Status.SUBMISSION_UNKNOWN,
                    failure_code="submission_outcome_unknown",
                )
                unknown += 1
            else:
                record_submission(
                    notification=notification,
                    provider_name=result.provider_name,
                    provider_task_id=result.task_id,
                )
                submitted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Submitted: {submitted}; rejected: {rejected}; outcome unknown: {unknown}. "
                "Submission does not mean delivered."
            )
        )