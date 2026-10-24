"""Development-only InsightFace adapter; never use its result as the sole auth factor.

InsightFace's public buffalo_l weights are licensed for non-commercial research.
Keep this model replaceable through BIOMETRIC_MODEL_NAME and do not ship
these weights in a commercial deployment without separate authorization.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import math
import struct
import warnings

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError


class FaceModelUnavailable(RuntimeError):
    pass


class LivenessCheckFailed(ValueError):
    pass


@lru_cache(maxsize=1)
def _face_app():
    try:
        from insightface.app import FaceAnalysis
        import onnxruntime
    except ImportError as exc:
        raise FaceModelUnavailable(
            "InsightFace/ONNX Runtime did not load. Install the optional dependencies and Windows VC++ runtime."
        ) from exc

    providers = ["CPUExecutionProvider"]
    if "CPUExecutionProvider" not in onnxruntime.get_available_providers():
        raise FaceModelUnavailable("ONNX Runtime CPU provider is unavailable.")
    liveness_enabled = getattr(settings, "BIOMETRIC_FACE_LIVENESS_ENABLED", False)
    try:
        app = FaceAnalysis(
            name=getattr(settings, "BIOMETRIC_MODEL_NAME", "buffalo_l"),
            root=getattr(settings, "BIOMETRIC_MODEL_ROOT", None),
            allowed_modules=["detection", "recognition"],
            addons=["liveness"] if liveness_enabled else [],
            liveness_mode="normal",
            liveness_threshold=getattr(settings, "BIOMETRIC_LIVENESS_THRESHOLD", 0.8),
            providers=providers,
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
    except Exception as exc:
        if liveness_enabled:
            raise FaceModelUnavailable("The development face or liveness model could not be loaded.") from exc
        raise
    return app


def embedding_from_image(image_bytes: bytes) -> np.ndarray:
    """Return one normalized embedding, rejecting invalid or ambiguous captures."""
    try:
        import numpy as np
    except ImportError as exc:
        raise FaceModelUnavailable("Install the optional face research dependencies.") from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as probe:
                if probe.format not in {"JPEG", "PNG"}:
                    raise ValueError("Upload a JPEG or PNG face image.")
                width, height = probe.size
                if min(width, height) < 256 or max(width, height) > 4096:
                    raise ValueError("The image dimensions are outside the supported range.")
                probe.verify()
            with Image.open(BytesIO(image_bytes)) as opened:
                opened.load()
                image = ImageOps.exif_transpose(opened).convert("RGB")
            rgb = np.asarray(image)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("The image dimensions"):
            raise
        raise ValueError("Upload a valid face image.") from exc

    faces = _face_app().get(rgb[:, :, ::-1])
    if len(faces) != 1:
        raise ValueError("The capture must contain exactly one detectable face.")
    if getattr(settings, "BIOMETRIC_FACE_LIVENESS_ENABLED", False):
        liveness = getattr(faces[0], "liveness", None)
        if liveness is None:
            raise FaceModelUnavailable("The liveness model did not return a result.")
        if liveness.status == "input_rejected":
            raise LivenessCheckFailed(
                getattr(liveness, "reason", None)
                or "The face was too close or too tightly cropped. Step back and try again."
            )
        if liveness.status != "ok" or liveness.is_live is not True:
            raise LivenessCheckFailed("Liveness check failed. Capture a live face and try again.")
    vector = np.asarray(faces[0].normed_embedding, dtype=np.float32)
    if vector.ndim != 1 or not np.isfinite(vector).all() or np.linalg.norm(vector) < 1e-6:
        raise ValueError("The face model returned an invalid embedding.")
    return vector / np.linalg.norm(vector)


def head_turn_position(image_bytes: bytes) -> float:
    """Return the nose's horizontal position between the two detected eyes."""
    try:
        import numpy as np
    except ImportError as exc:
        raise FaceModelUnavailable("Install the optional face research dependencies.") from exc
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            rgb = np.asarray(ImageOps.exif_transpose(image).convert("RGB"))
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Upload a valid face image.") from exc
    faces = _face_app().get(rgb[:, :, ::-1])
    if len(faces) != 1:
        raise ValueError("Each challenge frame must contain exactly one face.")
    points = getattr(faces[0], "kps", None)
    if points is None or len(points) < 3:
        raise FaceModelUnavailable("The face detector did not return pose landmarks.")
    eye_midpoint = (float(points[0][0]) + float(points[1][0])) / 2
    eye_distance = abs(float(points[1][0]) - float(points[0][0]))
    if eye_distance < 1:
        raise ValueError("The face pose could not be measured. Try again.")
    return (float(points[2][0]) - eye_midpoint) / eye_distance


def compare_embeddings(reference: bytes, probe: bytes, threshold: float | None = None) -> tuple[bool, float]:
    """Compare same-model serialized float32 embeddings; caller controls threshold."""
    if not reference or len(reference) != len(probe) or len(reference) % 4:
        raise ValueError("Enrollment and verification embeddings are incompatible.")
    count = len(reference) // 4
    left = struct.unpack(f"<{count}f", reference)
    right = struct.unpack(f"<{count}f", probe)
    if not all(math.isfinite(value) for value in (*left, *right)):
        raise ValueError("Face embedding contains a non-finite value.")
    score = math.fsum(a * b for a, b in zip(left, right))
    cutoff = threshold if threshold is not None else float(getattr(settings, "BIOMETRIC_MATCH_THRESHOLD", 0.45))
    return score >= cutoff, score
