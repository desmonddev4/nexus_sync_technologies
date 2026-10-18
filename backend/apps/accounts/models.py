from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimestampedModel


class AccountProfile(UUIDTimestampedModel):
    class Role(models.TextChoices):
        EMERGENCY_COORDINATOR = "emergency_coordinator", "Emergency coordinator"
        CLINICIAN = "clinician", "Clinician"
        PROVIDER_RESPONDER = "provider_responder", "Provider responder"
        PATIENT = "patient", "Patient"
        EMERGENCY_CONTACT = "emergency_contact", "Emergency contact"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    patient = models.OneToOneField(
        "patients.Patient",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="account_profile",
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    phone_number = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ("user__username",)

    def __str__(self):
        return f"{self.user.get_username()} ({self.role})"