from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import FaceResearchSample


class Command(BaseCommand):
    help = "Permanently delete expired encrypted face-research captures."

    def handle(self, *args, **options):
        expired = FaceResearchSample.objects.filter(expires_at__lte=timezone.now())
        count = expired.count()
        expired.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired face research sample(s)."))
