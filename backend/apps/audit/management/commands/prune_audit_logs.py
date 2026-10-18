from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "Delete audit log rows older than configured retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override retention days (defaults to AUDIT_RETENTION_DAYS setting).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview deletion count without deleting records.",
        )

    def handle(self, *args, **options):
        retention_days = options["days"]
        if retention_days is None:
            retention_days = int(getattr(settings, "AUDIT_RETENTION_DAYS", 365))
        if retention_days < 1:
            raise CommandError("Retention days must be greater than zero.")

        cutoff = timezone.now() - timedelta(days=retention_days)
        queryset = AuditLog.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {count} audit log rows older than {retention_days} days would be deleted."
                )
            )
            return

        deleted, _ = queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} audit log rows older than {retention_days} days."
            )
        )
