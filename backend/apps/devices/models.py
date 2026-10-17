import hashlib
import hmac
import secrets

from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import UUIDTimestampedModel
from apps.patients.models import Patient


class Device(UUIDTimestampedModel):
    class Type(models.TextChoices):
        WEARABLE = "wearable", "Wearable"
        SIMULATOR = "simulator", "Simulator"
        PHONE_GATEWAY = "phone_gateway", "Phone gateway"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        REVOKED = "revoked", "Revoked"

    device_identifier = models.CharField(max_length=100, unique=True)
    patient = models.ForeignKey(
        Patient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="devices",
    )
    device_type = models.CharField(max_length=24, choices=Type.choices)
    firmware_version = models.CharField(max_length=40, blank=True)
    battery_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(100)],
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REGISTERED,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(battery_percent__isnull=True) | Q(battery_percent__lte=100),
                name="device_battery_percent_lte_100",
            )
        ]

    def __str__(self):
        return self.device_identifier


class DeviceCredential(UUIDTimestampedModel):
    device = models.OneToOneField(
        Device,
        on_delete=models.CASCADE,
        related_name="credential",
    )
    secret_digest = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, device):
        secret = secrets.token_urlsafe(32)
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        cls.objects.update_or_create(
            device=device,
            defaults={"secret_digest": digest, "revoked_at": None, "last_used_at": None},
        )
        return secret

    def matches_secret(self, secret):
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        return hmac.compare_digest(self.secret_digest, digest)

    def __str__(self):
        return f"Credential for {self.device_id}"