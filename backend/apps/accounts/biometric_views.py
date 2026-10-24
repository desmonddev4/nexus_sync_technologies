"""Consent-based research capture endpoint; intentionally not an auth factor."""

import os
import warnings
from datetime import timedelta
from io import BytesIO

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import AccountProfile, FaceResearchSample
from apps.audit.models import AuditLog
from apps.audit.services import record_audit_event


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
NORMALIZED_IMAGE_DIMENSION = 1024
MAX_SAMPLES_PER_30_DAYS = 10
SAMPLE_RETENTION_DAYS = 30


def _cipher():
    key = os.getenv("BIOMETRIC_SAMPLE_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured("Biometric research capture encryption is not configured.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured("Biometric research capture encryption key is invalid.") from exc


def _normalize_image(image_bytes):
    """Validate, resize, strip metadata, and normalize an upload before encryption."""
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as probe:
                if probe.format not in {"JPEG", "PNG"}:
                    return None
                width, height = probe.size
                if min(width, height) < 256 or max(width, height) > MAX_IMAGE_DIMENSION:
                    return None
                probe.verify()
            with Image.open(BytesIO(image_bytes)) as opened:
                opened.load()
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((NORMALIZED_IMAGE_DIMENSION, NORMALIZED_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
                normalized = BytesIO()
                image.save(normalized, format="JPEG", quality=85, optimize=True)
                return normalized.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None


class FaceResearchSamplesView(APIView):
    """Create/list/delete a user's own consented research captures; no sample readback."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric_capture"

    def get_throttles(self):
        if self.request.method != "POST":
            return []
        return super().get_throttles()

    @staticmethod
    def _eligible_user(user):
        profile = getattr(user, "profile", None)
        return bool(
            profile
            and (
                profile.role == AccountProfile.Role.EMERGENCY_CONTACT
                or (profile.role == AccountProfile.Role.PATIENT and profile.patient_id)
            )
        )

    def get(self, request):
        if not self._eligible_user(request.user):
            return Response({"detail": "Only patient and caretaker accounts can manage their own research enrollment."}, status=403)
        consent_version = getattr(settings, "BIOMETRIC_RESEARCH_CONSENT_VERSION", "")
        try:
            _cipher()
            encryption_ready = True
        except ImproperlyConfigured:
            encryption_ready = False
        samples = FaceResearchSample.objects.filter(user=request.user).values(
            "id", "image_type", "consent_version", "review_status", "created_at", "expires_at"
        )
        result = [
            {
                **sample,
                "id": str(sample["id"]),
                "created_at": sample["created_at"].isoformat(),
                "expires_at": sample["expires_at"].isoformat(),
            }
            for sample in samples
        ]
        record_audit_event(
            request=request,
            action="biometric.research_samples.list",
            resource_type="biometric_research_sample",
            metadata={"result_count": len(result)},
        )
        return Response({
            "enrollment_enabled": bool(getattr(settings, "BIOMETRIC_RESEARCH_ENABLED", False) and consent_version and encryption_ready),
            "consent_version": consent_version,
            "motion_test_enabled": bool(
                settings.DEBUG
                and getattr(settings, "BIOMETRIC_MOTION_TEST_ENABLED", False)
                and getattr(settings, "BIOMETRIC_MOTION_CONSENT_VERSION", "")
            ),
            "motion_consent_version": getattr(settings, "BIOMETRIC_MOTION_CONSENT_VERSION", ""),
            "retention_days": SAMPLE_RETENTION_DAYS,
            "samples": result,
        })

    @transaction.atomic
    def post(self, request):
        if not self._eligible_user(request.user):
            return Response({"detail": "Only patient and caretaker accounts can enroll their own research samples."}, status=403)

        if not getattr(settings, "BIOMETRIC_RESEARCH_ENABLED", False):
            return Response({"detail": "Face research enrollment is disabled."}, status=503)
        consent_version = getattr(settings, "BIOMETRIC_RESEARCH_CONSENT_VERSION", "")
        if not consent_version:
            return Response({"detail": "Research enrollment is not configured."}, status=503)
        if request.data.get("consent") != "true" or request.data.get("consent_version") != consent_version:
            return Response({"detail": "Explicit consent to the current research notice is required."}, status=400)

        now = timezone.now()
        captures = AuditLog.objects.filter(
            actor=request.user,
            action="biometric.research_sample.created",
            created_at__gte=now - timedelta(days=30),
        )
        daily_count = captures.filter(created_at__gte=now - timedelta(days=1)).count()
        if daily_count >= 5 or captures.count() >= MAX_SAMPLES_PER_30_DAYS:
            return Response({"detail": "The research capture limit has been reached."}, status=429)

        upload = request.FILES.get("image")
        if upload is None or upload.size > MAX_IMAGE_BYTES:
            return Response({"detail": "Upload one JPEG or PNG image no larger than 5 MB."}, status=400)
        original_bytes = upload.read(MAX_IMAGE_BYTES + 1)
        image_bytes = _normalize_image(original_bytes)
        if image_bytes is None:
            return Response({"detail": "The image must be a valid JPEG or PNG between 256 and 4096 pixels per side."}, status=400)

        try:
            encrypted_image = _cipher().encrypt(image_bytes)
        except ImproperlyConfigured:
            return Response({"detail": "Research enrollment is unavailable because secure storage is not configured."}, status=503)

        sample = FaceResearchSample.objects.create(
            user=request.user,
            encrypted_image=encrypted_image,
            image_type=FaceResearchSample.ImageType.JPEG,
            consent_version=consent_version,
            expires_at=now + timedelta(days=SAMPLE_RETENTION_DAYS),
        )
        record_audit_event(
            request=request,
            action="biometric.research_sample.created",
            resource_type="biometric_research_sample",
            resource_id=sample.pk,
            metadata={"image_type": FaceResearchSample.ImageType.JPEG, "retention_days": SAMPLE_RETENTION_DAYS},
        )
        return Response(
            {
                "id": str(sample.pk),
                "status": sample.review_status,
                "expires_at": sample.expires_at.isoformat(),
                "used_for_sign_in": False,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        if not self._eligible_user(request.user):
            return Response({"detail": "Only patient and caretaker accounts can manage their own research enrollment."}, status=403)
        deleted_count, _ = FaceResearchSample.objects.filter(user=request.user).delete()
        record_audit_event(
            request=request,
            action="biometric.research_samples.deleted",
            resource_type="biometric_research_sample",
            metadata={"deleted_count": deleted_count, "reason": "participant_request"},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
