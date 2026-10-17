from django.core.management.base import BaseCommand, CommandError

from apps.notifications.models import IncidentNotification
from apps.notifications.providers import (
    ProviderConfigurationError,
    ProviderLookupError,
    ProviderRejectedError,
    SasuSyncSmsProvider,
)
from apps.notifications.services import reconcile_sasusync_status_snapshot


class Command(BaseCommand):
    help = "Poll SasuSync task statuses for submitted live messages."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        if options["limit"] < 1:
            raise CommandError("--limit must be greater than zero.")
        try:
            provider = SasuSyncSmsProvider(require_sender=False)
        except ProviderConfigurationError as error:
            raise CommandError(str(error)) from error

        notifications = IncidentNotification.objects.filter(
            provider_name="sasusync",
            status=IncidentNotification.Status.SUBMITTED,
        ).exclude(provider_task_id="").order_by("submitted_at")[: options["limit"]]

        checked = 0
        updated = 0
        lookup_errors = 0
        for notification in notifications:
            try:
                snapshot = provider.fetch_status(notification.provider_task_id)
            except (ProviderLookupError, ProviderRejectedError):
                lookup_errors += 1
                continue

            previous_status = notification.status
            notification = reconcile_sasusync_status_snapshot(
                notification=notification,
                snapshot=snapshot,
            )
            checked += 1
            if notification.status != previous_status:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Checked: {checked}; updated: {updated}; lookup errors: {lookup_errors}."
            )
        )