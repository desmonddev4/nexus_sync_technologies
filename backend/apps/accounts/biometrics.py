"""Fail-closed boundary for experimental face verification.

This module intentionally contains no built-in face matcher. A real verifier
must be configured explicitly, evaluated, and kept outside authentication until
approved. Never trust a client-provided match or liveness flag.
"""

from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string


class BiometricVerifierUnavailable(RuntimeError):
    """Raised when research verification is not configured and enabled."""


@dataclass(frozen=True)
class VerificationResult:
    """Minimum in-memory result contract; do not persist raw captures or scores in logs."""

    matched: bool
    live: bool
    verifier_version: str
    evaluation_id: str


class FaceVerifier(Protocol):
    """Research-only verifier interface for claimed-identity 1:1 comparisons."""

    def verify(self, *, claimed_user_id: int, capture: bytes) -> VerificationResult: ...


def get_research_verifier() -> FaceVerifier:
    """Load an explicitly configured verifier or fail closed."""
    if not getattr(settings, "BIOMETRIC_RESEARCH_ENABLED", False):
        raise BiometricVerifierUnavailable("Research face verification is disabled.")
    dotted_path = getattr(settings, "BIOMETRIC_VERIFIER_CLASS", "")
    if not dotted_path:
        raise BiometricVerifierUnavailable("No face verifier has been configured.")
    verifier_class = import_string(dotted_path)
    return verifier_class()


def evaluate_claimed_identity(*, claimed_user_id: int, capture: bytes) -> VerificationResult:
    """Run an experimental check without issuing credentials or changing access."""
    verifier = get_research_verifier()
    result = verifier.verify(claimed_user_id=claimed_user_id, capture=capture)
    if not isinstance(result, VerificationResult):
        raise TypeError("Face verifier returned an invalid result.")
    return result
