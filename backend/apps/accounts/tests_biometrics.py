import os
from io import BytesIO
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile, FaceResearchSample
from apps.audit.models import AuditLog
from apps.patients.models import Patient


class FaceResearchSamplesApiTests(APITestCase):
    endpoint = "/api/v1/auth/biometrics/research-samples/"

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="research-patient", password="safe-password-123")
        patient = Patient.objects.create(full_name="Research Subject")
        AccountProfile.objects.create(user=self.user, role=AccountProfile.Role.PATIENT, patient=patient)
        self.client.force_authenticate(self.user)
        self.key = Fernet.generate_key().decode("ascii")

    def image_upload(self):
        stream = BytesIO()
        Image.new("RGB", (320, 320), color="white").save(stream, format="JPEG")
        return SimpleUploadedFile("capture.jpg", stream.getvalue(), content_type="image/jpeg")

    @override_settings(BIOMETRIC_RESEARCH_ENABLED=True, BIOMETRIC_RESEARCH_CONSENT_VERSION="face-research-v1")
    def test_capture_requires_explicit_current_consent(self):
        response = self.client.post(self.endpoint, {"image": self.image_upload()}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(FaceResearchSample.objects.exists())

    @override_settings(BIOMETRIC_RESEARCH_ENABLED=True, BIOMETRIC_RESEARCH_CONSENT_VERSION="face-research-v1")
    @patch.dict(os.environ, {"BIOMETRIC_SAMPLE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    def test_capture_is_encrypted_unreviewed_and_not_an_auth_factor(self):
        uploaded = self.image_upload()
        original = uploaded.read()
        uploaded.seek(0)

        response = self.client.post(
            self.endpoint,
            {"image": uploaded, "consent": "true", "consent_version": "face-research-v1"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["used_for_sign_in"])
        sample = FaceResearchSample.objects.get(user=self.user)
        self.assertNotEqual(bytes(sample.encrypted_image), original)
        self.assertEqual(sample.review_status, FaceResearchSample.ReviewStatus.UNREVIEWED)
        metadata = self.client.get(self.endpoint).json()["samples"][0]
        self.assertNotIn("encrypted_image", metadata)

    @override_settings(BIOMETRIC_RESEARCH_ENABLED=True, BIOMETRIC_RESEARCH_CONSENT_VERSION="face-research-v1")
    def test_capture_fails_closed_without_encryption_key(self):
        with patch.dict(os.environ, {"BIOMETRIC_SAMPLE_ENCRYPTION_KEY": ""}):
            response = self.client.post(
                self.endpoint,
                {"image": self.image_upload(), "consent": "true", "consent_version": "face-research-v1"},
                format="multipart",
            )

        self.assertEqual(response.status_code, 503)
        self.assertFalse(FaceResearchSample.objects.exists())

    def test_participant_can_delete_their_samples(self):
        sample = FaceResearchSample.objects.create(
            user=self.user,
            encrypted_image=b"encrypted-sample",
            image_type=FaceResearchSample.ImageType.JPEG,
            consent_version="face-research-v1",
            expires_at="2099-01-01T00:00:00Z",
        )

        response = self.client.delete(self.endpoint)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(FaceResearchSample.objects.filter(pk=sample.pk).exists())

    def test_participant_cannot_view_or_delete_another_accounts_samples(self):
        other = get_user_model().objects.create_user(username="other-researcher")
        sample = FaceResearchSample.objects.create(
            user=other,
            encrypted_image=b"ciphertext",
            image_type=FaceResearchSample.ImageType.JPEG,
            consent_version="face-research-v1",
            expires_at="2099-01-01T00:00:00Z",
        )

        listed = self.client.get(self.endpoint)
        deleted = self.client.delete(self.endpoint)

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["samples"], [])
        self.assertEqual(deleted.status_code, 204)
        self.assertTrue(FaceResearchSample.objects.filter(pk=sample.pk).exists())

    @override_settings(BIOMETRIC_RESEARCH_ENABLED=True, BIOMETRIC_RESEARCH_CONSENT_VERSION="face-research-v1")
    @patch.dict(os.environ, {"BIOMETRIC_SAMPLE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    @override_settings(BIOMETRIC_RESEARCH_ENABLED=True, BIOMETRIC_RESEARCH_CONSENT_VERSION="face-research-v1")
    @patch.dict(os.environ, {"BIOMETRIC_SAMPLE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    def test_database_daily_capture_limit_is_enforced(self):
        for _ in range(5):
            AuditLog.objects.create(actor=self.user, action="biometric.research_sample.created", resource_type="biometric_research_sample")

        response = self.client.post(
            self.endpoint,
            {"image": self.image_upload(), "consent": "true", "consent_version": "face-research-v1"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(AuditLog.objects.filter(actor=self.user, action="biometric.research_sample.created").count(), 5)
    @override_settings(BIOMETRIC_RESEARCH_ENABLED=False, BIOMETRIC_RESEARCH_CONSENT_VERSION="face-research-v1")
    @patch.dict(os.environ, {"BIOMETRIC_SAMPLE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    def test_research_kill_switch_disables_capture(self):
        response = self.client.post(
            self.endpoint,
            {"image": self.image_upload(), "consent": "true", "consent_version": "face-research-v1"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 503)
        self.assertFalse(FaceResearchSample.objects.exists())

    def test_retention_command_deletes_expired_samples(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone

        sample = FaceResearchSample.objects.create(
            user=self.user,
            encrypted_image=b"ciphertext",
            image_type=FaceResearchSample.ImageType.JPEG,
            consent_version="face-research-v1",
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        call_command("prune_face_research_samples", verbosity=0)

        self.assertFalse(FaceResearchSample.objects.filter(pk=sample.pk).exists())
