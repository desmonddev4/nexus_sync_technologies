"""Development-only password plus face and randomized motion challenge endpoints."""

import os
import secrets

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ImproperlyConfigured
from django.core import signing
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from .face_model import FaceModelUnavailable, LivenessCheckFailed, compare_embeddings, embedding_from_image, head_turn_position
from .models import AccountProfile, FaceLoginEmbedding


MAX_CAPTURE_BYTES = 5 * 1024 * 1024
OPERATIONS_ROLES = {
    AccountProfile.Role.EMERGENCY_COORDINATOR,
    AccountProfile.Role.CLINICIAN,
}


def _enabled():
    return bool(
        settings.DEBUG
        and getattr(settings, "BIOMETRIC_FACE_LOGIN_ENABLED", False)
        and getattr(settings, "BIOMETRIC_FACE_CONSENT_VERSION", "")
    )


def _cipher():
    key = os.getenv("BIOMETRIC_FACE_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured("Biometric sample encryption is not configured.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured("Biometric sample encryption key is invalid.") from exc


def _is_operations_user(user):
    if user.is_superuser:
        return True
    try:
        profile = user.profile
    except AccountProfile.DoesNotExist:
        return False
    return bool(profile and profile.role in OPERATIONS_ROLES)


def _read_capture(request):
    image = request.FILES.get("image")
    if image is None or image.size > MAX_CAPTURE_BYTES:
        return None
    content = image.read(MAX_CAPTURE_BYTES + 1)
    return content if 0 < len(content) <= MAX_CAPTURE_BYTES else None


def _challenge_steps(request):
    token = str(request.data.get("challenge", ""))
    frames = request.FILES.getlist("frames")
    if len(frames) != 3 or any(frame.size > MAX_CAPTURE_BYTES for frame in frames):
        raise ValueError("Complete all three face challenge steps and try again.")
    try:
        challenge = signing.loads(token, salt="face-motion-challenge-v1", max_age=120)
    except signing.BadSignature as exc:
        raise ValueError("The face challenge expired. Start again.") from exc
    steps = challenge.get("steps") if isinstance(challenge, dict) else None
    if not isinstance(steps, list) or len(steps) != 3 or steps[0] != "center" or set(steps) != {"center", "left", "right"}:
        raise ValueError("The face challenge is invalid. Start again.")
    positions = []
    for frame in frames:
        content = frame.read(MAX_CAPTURE_BYTES + 1)
        if not 0 < len(content) <= MAX_CAPTURE_BYTES:
            raise ValueError("A challenge frame is invalid. Start again.")
        positions.append(head_turn_position(content))
    center = positions[0]
    turn_offsets = [positions[1] - center, positions[2] - center]
    # Front-facing camera mirroring and facial asymmetry can invert the landmark
    # direction. Require two clear, opposing turns in the signed prompt order.
    if min(abs(offset) for offset in turn_offsets) < 0.06 or turn_offsets[0] * turn_offsets[1] >= 0:
        raise ValueError("The head-turn challenge was not completed. Turn clearly to one side, then the other, and try again.")
    return steps, positions


class FaceLivenessChallengeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric_liveness_challenge"

    def get(self, request):
        motion_enabled = bool(
            settings.DEBUG
            and getattr(settings, "BIOMETRIC_MOTION_TEST_ENABLED", False)
            and getattr(settings, "BIOMETRIC_MOTION_CONSENT_VERSION", "")
        )
        if not _enabled() and not motion_enabled:
            return Response({"detail": "Development face sign-in is disabled."}, status=503)
        steps = ["center", "left", "right"]
        if secrets.randbelow(2):
            steps[1:] = reversed(steps[1:])
        return Response({
            "challenge": signing.dumps({"steps": steps}, salt="face-motion-challenge-v1"),
            "steps": steps,
            "motion_test_enabled": motion_enabled,
            "consent_version": getattr(settings, "BIOMETRIC_MOTION_CONSENT_VERSION", "") if motion_enabled else "",
        })


class FaceMotionResearchCheckView(APIView):
    """Evaluate a consented motion sequence in memory; never issue auth or store frames."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric_motion_test"

    def post(self, request):
        enabled = bool(
            settings.DEBUG
            and getattr(settings, "BIOMETRIC_MOTION_TEST_ENABLED", False)
            and getattr(settings, "BIOMETRIC_MOTION_CONSENT_VERSION", "")
        )
        if not enabled:
            return Response({"detail": "The development motion check is disabled."}, status=503)
        profile = getattr(request.user, "profile", None)
        eligible = bool(
            profile
            and (
                profile.role == AccountProfile.Role.EMERGENCY_CONTACT
                or (profile.role == AccountProfile.Role.PATIENT and profile.patient_id)
            )
        )
        if not eligible:
            return Response({"detail": "Only patient and caretaker accounts can run this research check."}, status=403)
        consent_version = settings.BIOMETRIC_MOTION_CONSENT_VERSION
        if request.data.get("consent") != "true" or request.data.get("consent_version") != consent_version:
            return Response({"detail": "Explicit consent to the current motion-check notice is required."}, status=400)
        try:
            _challenge_steps(request)
        except ValueError as exc:
            record_audit_event(
                request=request,
                action="biometric.motion_check.failed",
                resource_type="biometric_motion_check",
                outcome="failure",
                metadata={"reason": "motion_challenge"},
            )
            return Response({"detail": str(exc)}, status=400)
        except FaceModelUnavailable:
            return Response({"detail": "The development face landmark model is unavailable."}, status=503)
        record_audit_event(
            request=request,
            action="biometric.motion_check.completed",
            resource_type="biometric_motion_check",
            metadata={"result": "passed", "images_stored": False, "used_for_sign_in": False},
        )
        return Response({
            "motion_passed": True,
            "identity_matched": False,
            "used_for_sign_in": False,
            "server_retained_images": False,
        })


class FaceLoginEnrollmentView(APIView):
    """Enroll or remove the signed-in user's own development face template."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not _enabled():
            return Response({"detail": "Development face sign-in is disabled."}, status=503)
        if not _is_operations_user(request.user):
            return Response({"detail": "Only operations accounts can enroll."}, status=403)
        version = settings.BIOMETRIC_FACE_CONSENT_VERSION
        if request.data.get("consent") != "true" or request.data.get("consent_version") != version:
            return Response({"detail": "Explicit consent to the current face sign-in test notice is required."}, status=400)
        image_bytes = _read_capture(request)
        if image_bytes is None:
            return Response({"detail": "Upload one image no larger than 5 MB."}, status=400)
        try:
            _challenge_steps(request)
            embedding = embedding_from_image(image_bytes)
            encrypted = _cipher().encrypt(embedding.tobytes())
        except LivenessCheckFailed as exc:
            record_audit_event(
                request=request,
                action="auth.face_enrollment.failed",
                resource_type="face_login_enrollment",
                actor=request.user,
                outcome="failure",
                metadata={"reason": "liveness"},
            )
            return Response({"detail": str(exc)}, status=400)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except (FaceModelUnavailable, ImproperlyConfigured):
            return Response({"detail": "Development face model or encryption is unavailable."}, status=503)

        FaceLoginEmbedding.objects.update_or_create(
            user=request.user,
            defaults={
                "encrypted_embedding": encrypted,
                "model_name": settings.BIOMETRIC_MODEL_NAME,
                "consent_version": version,
            },
        )
        record_audit_event(
            request=request,
            action="auth.face_enrollment.created",
            resource_type="face_login_enrollment",
            actor=request.user,
            metadata={"model": settings.BIOMETRIC_MODEL_NAME},
        )
        return Response({"enrolled": True, "development_only": True}, status=201)

    def delete(self, request):
        deleted, _ = FaceLoginEmbedding.objects.filter(user=request.user).delete()
        record_audit_event(
            request=request,
            action="auth.face_enrollment.deleted",
            resource_type="face_login_enrollment",
            actor=request.user,
            metadata={"deleted": bool(deleted)},
        )
        return Response(status=204)


class FaceTokenView(APIView):
    """Issue a development token only after both password and face checks pass."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric_face_login"

    def post(self, request):
        if not _enabled():
            return Response({"detail": "Development face sign-in is disabled."}, status=503)

        username = str(request.data.get("username", ""))[:150]
        user = authenticate(
            request=request,
            username=username,
            password=request.data.get("password", ""),
        )
        capture = _read_capture(request)
        enrollment = FaceLoginEmbedding.objects.filter(user=user).first() if user else None
        if not user or not user.is_active or not _is_operations_user(user) or not capture or not enrollment:
            record_audit_event(
                request=request,
                action="auth.face_token.failed",
                resource_type="auth",
                outcome="failure",
                metadata={"username": username},
            )
            return Response({"detail": "Sign-in could not be verified."}, status=400)

        try:
            _challenge_steps(request)
        except ValueError as exc:
            record_audit_event(
                request=request,
                action="auth.face_token.failed",
                resource_type="auth",
                outcome="failure",
                metadata={"username": username, "reason": "motion_challenge"},
            )
            return Response({"detail": str(exc)}, status=400)
        except FaceModelUnavailable:
            return Response({"detail": "Development face model is unavailable."}, status=503)

        try:
            if enrollment.model_name != settings.BIOMETRIC_MODEL_NAME:
                raise ValueError("Model version differs from enrollment.")
            reference = _cipher().decrypt(bytes(enrollment.encrypted_embedding))
            probe = embedding_from_image(capture).tobytes()
            matched, _score = compare_embeddings(reference, probe)
        except LivenessCheckFailed as exc:
            record_audit_event(
                request=request,
                action="auth.face_token.failed",
                resource_type="auth",
                outcome="failure",
                metadata={"username": username, "reason": "liveness"},
            )
            return Response({"detail": str(exc)}, status=400)
        except (ValueError, InvalidToken, ImproperlyConfigured):
            matched = False
        except FaceModelUnavailable:
            return Response({"detail": "Development face model is unavailable."}, status=503)

        if not matched:
            record_audit_event(
                request=request,
                action="auth.face_token.failed",
                resource_type="auth",
                outcome="failure",
                metadata={"username": username},
            )
            return Response({"detail": "Sign-in could not be verified."}, status=400)

        token, _ = Token.objects.get_or_create(user=user)
        try:
            profile = user.profile
        except AccountProfile.DoesNotExist:
            profile = None
        record_audit_event(
            request=request,
            action="auth.face_token.issued",
            resource_type="auth",
            resource_id=user.pk,
            actor=user,
            metadata={"username": user.get_username(), "role": profile.role if profile else "superuser"},
        )
        return Response({"token": token.key}, status=status.HTTP_200_OK)
