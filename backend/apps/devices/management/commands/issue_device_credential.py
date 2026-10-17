from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.devices.models import Device, DeviceCredential


class Command(BaseCommand):
    help = "Issue or revoke the credential for a registered Nexus Sync device."

    def add_arguments(self, parser):
        parser.add_argument("device_identifier")
        parser.add_argument(
            "--revoke",
            action="store_true",
            help="Revoke the device credential instead of issuing or rotating it.",
        )

    def handle(self, *args, **options):
        try:
            device = Device.objects.get(device_identifier=options["device_identifier"])
        except Device.DoesNotExist as error:
            raise CommandError("Device was not found.") from error

        if options["revoke"]:
            try:
                credential = device.credential
            except DeviceCredential.DoesNotExist as error:
                raise CommandError("Device has no credential to revoke.") from error
            credential.revoked_at = timezone.now()
            credential.save(update_fields=("revoked_at", "updated_at"))
            self.stdout.write(self.style.SUCCESS("Device credential revoked."))
            return

        if device.status != Device.Status.ACTIVE or device.patient_id is None:
            raise CommandError("Activate and assign the device before issuing credentials.")
        if device.device_type not in (Device.Type.WEARABLE, Device.Type.SIMULATOR):
            raise CommandError("Only wearable and simulator devices can receive credentials.")

        secret = DeviceCredential.issue(device)
        self.stdout.write(self.style.SUCCESS("Credential issued. Store this secret securely; it will not be shown again."))
        self.stdout.write(f"Authorization: Device {device.device_identifier}:{secret}")