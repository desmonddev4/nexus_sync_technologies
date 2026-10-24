from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase, override_settings
from PIL import Image

from apps.accounts.face_model import LivenessCheckFailed, embedding_from_image


def jpeg_bytes():
    stream = BytesIO()
    Image.new("RGB", (256, 256), color=(120, 120, 120)).save(stream, format="JPEG")
    return stream.getvalue()


class FaceLivenessGateTests(SimpleTestCase):
    @override_settings(BIOMETRIC_FACE_LIVENESS_ENABLED=True)
    @patch("apps.accounts.face_model._face_app")
    def test_non_live_detection_is_rejected_before_embedding(self, face_app):
        face = SimpleNamespace(
            liveness=SimpleNamespace(status="ok", is_live=False),
            normed_embedding=np.asarray([1.0, 0.0], dtype=np.float32),
        )
        face_app.return_value.get.return_value = [face]

        with self.assertRaisesRegex(LivenessCheckFailed, "Liveness check failed"):
            embedding_from_image(jpeg_bytes())

    @override_settings(BIOMETRIC_FACE_LIVENESS_ENABLED=True)
    @patch("apps.accounts.face_model._face_app")
    def test_live_detection_allows_embedding(self, face_app):
        face = SimpleNamespace(
            liveness=SimpleNamespace(status="ok", is_live=True),
            normed_embedding=np.asarray([3.0, 4.0], dtype=np.float32),
        )
        face_app.return_value.get.return_value = [face]

        embedding = embedding_from_image(jpeg_bytes())

        np.testing.assert_allclose(embedding, [0.6, 0.8])

    @override_settings(BIOMETRIC_FACE_LIVENESS_ENABLED=True)
    @patch("apps.accounts.face_model._face_app")
    def test_insufficient_crop_is_rejected_with_guidance(self, face_app):
        face = SimpleNamespace(
            liveness=SimpleNamespace(
                status="input_rejected",
                is_live=None,
                reason="Step back from the camera.",
            ),
            normed_embedding=None,
        )
        face_app.return_value.get.return_value = [face]

        with self.assertRaisesRegex(LivenessCheckFailed, "Step back"):
            embedding_from_image(jpeg_bytes())
