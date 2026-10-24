import os
from array import array
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import signing
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import AccountProfile, FaceLoginEmbedding
from apps.accounts.face_model import LivenessCheckFailed


class FaceLoginApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="face-operator", password="safe-password-123"
        )
        AccountProfile.objects.create(user=self.user, role=AccountProfile.Role.CLINICIAN)
        self.embedding = array("f", [1.0, 0.0, 0.0])
        self.key = Fernet.generate_key().decode("ascii")

    def upload(self):
        return SimpleUploadedFile("face.jpg", b"mock-face-capture", content_type="image/jpeg")

    def challenge_payload(self):
        return {
            "challenge": signing.dumps({"steps": ["center", "left", "right"]}, salt="face-motion-challenge-v1"),
            "frames": [self.upload(), self.upload(), self.upload()],
        }

    @override_settings(DEBUG=True, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1")
    def test_issued_challenge_keeps_neutral_frame_first_and_signs_order(self):
        from django.core import signing

        response = self.client.get("/api/v1/auth/face-liveness-challenge/")
        self.assertEqual(response.status_code, 200)
        steps = response.json()["steps"]
        self.assertEqual(steps[0], "center")
        self.assertEqual(set(steps), {"center", "left", "right"})
        self.assertEqual(
            signing.loads(response.json()["challenge"], salt="face-motion-challenge-v1")["steps"],
            steps,
        )

    @override_settings(DEBUG=False, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1")
    def test_face_flow_is_disabled_outside_debug(self):
        response = self.client.post("/api/v1/auth/face-token/", {}, format="multipart")
        self.assertEqual(response.status_code, 503)

    @override_settings(DEBUG=True, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1",
                       BIOMETRIC_MODEL_NAME="buffalo_l")
    @patch.dict(os.environ, {"BIOMETRIC_FACE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    @patch("apps.accounts.face_auth_views.embedding_from_image")
    @patch("apps.accounts.face_auth_views.head_turn_position", side_effect=[0.0, 0.2, -0.2, 0.0, 0.2, -0.2])
    def test_password_and_enrolled_face_issue_token(self, pose, extract_embedding):
        extract_embedding.return_value = self.embedding
        password_login = self.client.post(
            "/api/v1/auth/token/",
            {"username": "face-operator", "password": "safe-password-123"},
            format="json",
        )
        self.assertEqual(password_login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {password_login.json()['token']}")
        enrolled = self.client.post(
            "/api/v1/auth/biometrics/face-enrollment/",
            {
                "consent": "true",
                "consent_version": "face-login-dev-v1",
                "image": self.upload(),
                **self.challenge_payload(),
            },
            format="multipart",
        )
        self.assertEqual(enrolled.status_code, 201)
        self.assertTrue(enrolled.json()["development_only"])
        template = FaceLoginEmbedding.objects.get(user=self.user)
        self.assertNotIn(self.embedding.tobytes(), bytes(template.encrypted_embedding))
        self.client.credentials()

        response = self.client.post(
            "/api/v1/auth/face-token/",
            {
                "username": "face-operator",
                "password": "safe-password-123",
                "image": self.upload(),
                **self.challenge_payload(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["token"])

    @override_settings(DEBUG=True, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1",
                       BIOMETRIC_MODEL_NAME="buffalo_l", BIOMETRIC_MATCH_THRESHOLD=0.9)
    @patch.dict(os.environ, {"BIOMETRIC_FACE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    @patch("apps.accounts.face_auth_views.embedding_from_image")
    @patch("apps.accounts.face_auth_views.head_turn_position", side_effect=[0.0, -0.2, 0.2])
    def test_wrong_face_or_password_does_not_issue_token(self, pose, extract_embedding):
        extract_embedding.return_value = array("f", [0.0, 1.0, 0.0])
        from apps.accounts.face_auth_views import _cipher
        FaceLoginEmbedding.objects.create(
            user=self.user,
            encrypted_embedding=_cipher().encrypt(self.embedding.tobytes()),
            model_name="buffalo_l",
            consent_version="face-login-dev-v1",
        )

        wrong_face = self.client.post(
            "/api/v1/auth/face-token/",
            {"username": "face-operator", "password": "safe-password-123", "image": self.upload(), **self.challenge_payload()},
            format="multipart",
        )
        wrong_password = self.client.post(
            "/api/v1/auth/face-token/",
            {"username": "face-operator", "password": "incorrect", "image": self.upload()},
            format="multipart",
        )

        self.assertEqual(wrong_face.status_code, 400)
        self.assertEqual(wrong_password.status_code, 400)
        self.assertNotIn("token", wrong_face.json())
        self.assertNotIn("token", wrong_password.json())

    @override_settings(DEBUG=True, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1")
    def test_enrollment_requires_explicit_consent(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/auth/biometrics/face-enrollment/",
            {"image": self.upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FaceLoginEmbedding.objects.exists())

    @override_settings(DEBUG=True, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1")
    @patch("apps.accounts.face_auth_views.embedding_from_image")
    @patch("apps.accounts.face_auth_views.head_turn_position", return_value=0.0)
    def test_motion_challenge_rejects_reusing_the_same_still(self, pose, extract_embedding):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/auth/biometrics/face-enrollment/",
            {
                "consent": "true",
                "consent_version": "face-login-dev-v1",
                "image": self.upload(),
                **self.challenge_payload(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("head-turn challenge", response.json()["detail"])
        extract_embedding.assert_not_called()
        self.assertFalse(FaceLoginEmbedding.objects.exists())

    @override_settings(DEBUG=True, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1",
                       BIOMETRIC_FACE_LIVENESS_ENABLED=True)
    @patch.dict(os.environ, {"BIOMETRIC_FACE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    @patch("apps.accounts.face_auth_views.embedding_from_image")
    @patch("apps.accounts.face_auth_views.head_turn_position", side_effect=[0.0, -0.2, 0.2])
    def test_enrollment_rejects_failed_liveness(self, pose, extract_embedding):
        extract_embedding.side_effect = LivenessCheckFailed("Liveness check failed.")
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/auth/biometrics/face-enrollment/",
            {
                "consent": "true",
                "consent_version": "face-login-dev-v1",
                "image": self.upload(),
                **self.challenge_payload(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Liveness check failed", response.json()["detail"])
        self.assertFalse(FaceLoginEmbedding.objects.exists())

    @override_settings(DEBUG=True, BIOMETRIC_FACE_LOGIN_ENABLED=True,
                       BIOMETRIC_FACE_CONSENT_VERSION="face-login-dev-v1",
                       BIOMETRIC_MODEL_NAME="buffalo_l", BIOMETRIC_FACE_LIVENESS_ENABLED=True)
    @patch.dict(os.environ, {"BIOMETRIC_FACE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
    @patch("apps.accounts.face_auth_views.embedding_from_image")
    @patch("apps.accounts.face_auth_views.head_turn_position", side_effect=[0.0, -0.2, 0.2])
    def test_failed_liveness_never_issues_face_token(self, pose, extract_embedding):
        from apps.accounts.face_auth_views import _cipher

        FaceLoginEmbedding.objects.create(
            user=self.user,
            encrypted_embedding=_cipher().encrypt(self.embedding.tobytes()),
            model_name="buffalo_l",
            consent_version="face-login-dev-v1",
        )
        extract_embedding.side_effect = LivenessCheckFailed("Liveness check failed.")

        response = self.client.post(
            "/api/v1/auth/face-token/",
            {
                "username": "face-operator",
                "password": "safe-password-123",
                "image": self.upload(),
                **self.challenge_payload(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Liveness check failed", response.json()["detail"])
        self.assertNotIn("token", response.json())
