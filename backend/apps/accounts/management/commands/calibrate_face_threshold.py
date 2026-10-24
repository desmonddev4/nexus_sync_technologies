"""Estimate a local face-match cutoff from consented genuine/impostor images."""

from __future__ import annotations

import math
from pathlib import Path

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.face_auth_views import _cipher
from apps.accounts.face_model import (
    FaceModelUnavailable,
    compare_embeddings,
    embedding_from_image,
)
from apps.accounts.models import FaceLoginEmbedding


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MINIMUM_PER_CLASS = 20


def _images_in(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise CommandError(f"Image folder does not exist: {folder}")
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def _scores(reference: bytes, paths: list[Path]) -> tuple[list[float], int]:
    scores: list[float] = []
    rejected = 0
    for path in paths:
        try:
            probe = embedding_from_image(path.read_bytes())
            _matched, score = compare_embeddings(reference, probe.tobytes(), threshold=2.0)
        except (OSError, ValueError):
            rejected += 1
            continue
        scores.append(score)
    return scores, rejected


def _rates(genuine: list[float], impostor: list[float], threshold: float) -> tuple[float, float]:
    far = sum(score >= threshold for score in impostor) / len(impostor)
    frr = sum(score < threshold for score in genuine) / len(genuine)
    return far, frr


def _auc(genuine: list[float], impostor: list[float]) -> float:
    wins = sum(g > i for g in genuine for i in impostor)
    ties = sum(g == i for g in genuine for i in impostor)
    return (wins + 0.5 * ties) / (len(genuine) * len(impostor))


def _threshold_for_far(impostor: list[float], target_far: float) -> float | None:
    allowed_accepts = math.floor(target_far * len(impostor))
    if allowed_accepts >= len(impostor):
        return -1.0
    cutoff = math.nextafter(sorted(impostor, reverse=True)[allowed_accepts], math.inf)
    return cutoff if cutoff <= 1.0 else None


class Command(BaseCommand):
    help = "Estimate a development face-match cutoff without saving input images or embeddings."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Enrolled local test account")
        parser.add_argument("--genuine-dir", required=True, type=Path, help="Fresh images of the enrolled operator")
        parser.add_argument("--impostor-dir", required=True, type=Path, help="Images of consenting people who are not enrolled")
        parser.add_argument("--target-far", type=float, default=0.01, help="Maximum empirical false-accept rate, from 0 to less than 1")

    def handle(self, *args, **options):
        if not settings.DEBUG or not getattr(settings, "BIOMETRIC_FACE_LOGIN_ENABLED", False):
            raise CommandError("This command is available only for enabled local development.")
        target_far = options["target_far"]
        if not math.isfinite(target_far) or not 0 <= target_far < 1:
            raise CommandError("--target-far must be a finite value from 0 up to, but not including, 1.")

        try:
            enrollment = FaceLoginEmbedding.objects.select_related("user").get(user__username=options["username"])
        except FaceLoginEmbedding.DoesNotExist as exc:
            raise CommandError("That user has no face-login enrollment.") from exc
        if enrollment.model_name != settings.BIOMETRIC_MODEL_NAME:
            raise CommandError("The enrolled face model differs from the configured model.")
        try:
            reference = _cipher().decrypt(bytes(enrollment.encrypted_embedding))
        except (InvalidToken, ValueError) as exc:
            raise CommandError("The local face enrollment could not be decrypted.") from exc

        genuine_paths = _images_in(options["genuine_dir"])
        impostor_paths = _images_in(options["impostor_dir"])
        if not genuine_paths or not impostor_paths:
            raise CommandError("Both folders must contain JPEG or PNG captures.")
        try:
            genuine, rejected_genuine = _scores(reference, genuine_paths)
            impostor, rejected_impostor = _scores(reference, impostor_paths)
        except FaceModelUnavailable as exc:
            raise CommandError(str(exc)) from exc
        if not genuine or not impostor:
            raise CommandError("No usable face captures remained after image, face, and liveness checks.")

        current_threshold = float(settings.BIOMETRIC_MATCH_THRESHOLD)
        current_far, current_frr = _rates(genuine, impostor, current_threshold)
        self.stdout.write(f"Usable captures: genuine={len(genuine)}/{len(genuine_paths)}, impostor={len(impostor)}/{len(impostor_paths)}")
        self.stdout.write(f"Rejected captures: genuine={rejected_genuine}, impostor={rejected_impostor}")
        if min(len(genuine), len(impostor)) < MINIMUM_PER_CLASS:
            self.stdout.write(self.style.WARNING(
                f"Not enough samples for a threshold recommendation: use at least {MINIMUM_PER_CLASS} usable captures per class."
            ))
            self.stdout.write(f"Exploratory AUC: {_auc(genuine, impostor):.4f}")
            self.stdout.write(f"Current {current_threshold:.6f}: empirical FAR={current_far:.1%}, FRR={current_frr:.1%}")
            return

        candidate = _threshold_for_far(impostor, target_far)
        self.stdout.write(f"AUC: {_auc(genuine, impostor):.4f}")
        self.stdout.write(f"Current {current_threshold:.6f}: empirical FAR={current_far:.1%}, FRR={current_frr:.1%}")
        self.stdout.write(f"Target empirical FAR: {target_far:.1%}")
        if candidate is None:
            self.stdout.write(self.style.ERROR("No cutoff in the cosine-score range [-1, 1] meets the requested FAR."))
            return
        candidate_far, candidate_frr = _rates(genuine, impostor, candidate)
        self.stdout.write(self.style.SUCCESS(f"Exploratory cutoff: {candidate:.6f}"))
        self.stdout.write(f"At cutoff: empirical FAR={candidate_far:.1%}, FRR={candidate_frr:.1%}")
        self.stdout.write(self.style.WARNING(
            "This is an in-sample development estimate, not a validated security threshold. "
            "Keep a separate consenting validation set and do not use it for production decisions."
        ))
