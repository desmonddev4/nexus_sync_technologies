from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.patients.models import PatientDataRequest


class Command(BaseCommand):
    help = "Delete completed patient data requests older than configured retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override retention days (defaults to PATIENT_DATA_REQUEST_RETENTION_DAYS).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview deletion count without deleting records.",
        )

    def handle(self, *args, **options):
        retention_days = options["days"]
        if retention_days is None:
            retention_days = int(getattr(settings, "PATIENT_DATA_REQUEST_RETENTION_DAYS", 365))
        if retention_days < 1:
            raise CommandError("Retention days must be greater than zero.")

        cutoff = timezone.now() - timedelta(days=retention_days)
        queryset = PatientDataRequest.objects.filter(
            status=PatientDataRequest.Status.FULFILLED,
            updated_at__lt=cutoff,
        )
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {count} patient data request rows older than {retention_days} days would be deleted."
                )
            )
            return

        deleted, _ = queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} patient data request rows older than {retention_days} days."
            )
        )
