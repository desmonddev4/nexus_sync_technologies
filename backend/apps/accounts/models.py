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

class FaceResearchSample(UUIDTimestampedModel):
    """Encrypted, consented research capture; never used directly for authentication."""

    class ImageType(models.TextChoices):
        JPEG = "image/jpeg", "JPEG"
        PNG = "image/png", "PNG"

    class ReviewStatus(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed research capture"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="face_research_samples",
    )
    encrypted_image = models.BinaryField()
    image_type = models.CharField(max_length=16, choices=ImageType.choices)
    consent_version = models.CharField(max_length=40)
    review_status = models.CharField(
        max_length=16,
        choices=ReviewStatus.choices,
        default=ReviewStatus.UNREVIEWED,
    )
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "created_at"))]

    def __str__(self):
        return f"Research face sample {self.pk} ({self.review_status})"


class FaceLoginEmbedding(UUIDTimestampedModel):
    """Opt-in development verification template, separate from research photos."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="face_login_embedding",
    )
    encrypted_embedding = models.BinaryField()
    model_name = models.CharField(max_length=64)
    consent_version = models.CharField(max_length=40)

    def __str__(self):
        return f"Development face verification for {self.user.get_username()}"
