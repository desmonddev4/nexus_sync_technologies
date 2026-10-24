from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile, FaceLoginEmbedding, FaceResearchSample


class FaceMotionResearchApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="motion-caretaker", password="safe-password-123")
        AccountProfile.objects.create(user=self.user, role=AccountProfile.Role.EMERGENCY_CONTACT)
        self.client.force_authenticate(self.user)

    @staticmethod
    def frames():
        return [SimpleUploadedFile(f"frame-{n}.jpg", b"mock-frame", content_type="image/jpeg") for n in range(3)]

    @override_settings(
        DEBUG=True,
        BIOMETRIC_MOTION_TEST_ENABLED=True,
        BIOMETRIC_MOTION_CONSENT_VERSION="face-motion-dev-v1",
    )
    @patch("apps.accounts.face_auth_views.head_turn_position", side_effect=[0.0, 0.2, -0.2])
    def test_motion_check_is_shadow_only_and_does_not_save_frames(self, pose):
        from django.core import signing

        challenge = signing.dumps({"steps": ["center", "left", "right"]}, salt="face-motion-challenge-v1")
        response = self.client.post(
            "/api/v1/auth/biometrics/motion-check/",
            {
                "challenge": challenge,
                "consent": "true",
                "consent_version": "face-motion-dev-v1",
                "frames": self.frames(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["motion_passed"])
        self.assertFalse(response.json()["identity_matched"])
        self.assertFalse(response.json()["used_for_sign_in"])
        self.assertFalse(response.json()["server_retained_images"])
        self.assertFalse(FaceResearchSample.objects.exists())
        self.assertFalse(FaceLoginEmbedding.objects.exists())

    @override_settings(
        DEBUG=True,
        BIOMETRIC_MOTION_TEST_ENABLED=True,
        BIOMETRIC_MOTION_CONSENT_VERSION="face-motion-dev-v1",
    )
    def test_motion_check_requires_current_explicit_consent(self):
        response = self.client.post("/api/v1/auth/biometrics/motion-check/", {}, format="multipart")
        self.assertEqual(response.status_code, 400)

