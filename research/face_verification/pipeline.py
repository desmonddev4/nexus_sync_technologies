"""Offline research utilities. This package never authenticates users or trains a model."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

REQUIRED_FIELDS = {"sample_id", "subject_id", "image_path", "consent", "review_status"}
PROVENANCE_FIELDS = {"consent_version", "session_id", "protocol_version"}
OPTIONAL_METADATA_FIELDS = {"capture_device", "lighting", "pose", "age_band", "assistive_device"}


class DatasetError(ValueError):
    pass


def load_manifest(manifest_path: Path, image_root: Path) -> list[dict]:
    """Load approved JSONL rows and reject unsafe paths or unreviewed samples."""
    rows: list[dict] = []
    seen_samples: set[str] = set()
    seen_images: set[Path] = set()
    consent_versions: set[str] = set()
    protocol_versions: set[str] = set()
    root = image_root.resolve(strict=True)
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"Invalid JSON on manifest line {line_number}") from exc
            if not isinstance(row, dict) or not REQUIRED_FIELDS.issubset(row):
                raise DatasetError(f"Missing required fields on manifest line {line_number}")
            if not PROVENANCE_FIELDS.issubset(row):
                raise DatasetError(f"Missing consent/session provenance on manifest line {line_number}")
            for key in ("sample_id", "subject_id", "image_path"):
                if not isinstance(row[key], str) or not row[key].strip():
                    raise DatasetError(f"Invalid {key} on manifest line {line_number}")
            for key in PROVENANCE_FIELDS:
                if not isinstance(row[key], str) or not row[key].strip():
                    raise DatasetError(f"Invalid {key} on manifest line {line_number}")
            for key in OPTIONAL_METADATA_FIELDS.intersection(row):
                if not isinstance(row[key], str) or not row[key].strip():
                    raise DatasetError(f"Invalid {key} on manifest line {line_number}")
            if row["sample_id"] in seen_samples:
                raise DatasetError(f"Duplicate sample_id on manifest line {line_number}")
            seen_samples.add(row["sample_id"])
            if row["consent"] is not True or row["review_status"] != "approved":
                raise DatasetError(f"Sample not consented and approved on manifest line {line_number}")
            image = (root / row["image_path"]).resolve(strict=False)
            if not image.is_relative_to(root):
                raise DatasetError(f"Image path escapes dataset root on manifest line {line_number}")
            if not image.is_file():
                raise DatasetError(f"Missing image on manifest line {line_number}")
            if image in seen_images:
                raise DatasetError(f"Image is referenced more than once on manifest line {line_number}")
            seen_images.add(image)
            consent_versions.add(row["consent_version"])
            protocol_versions.add(row["protocol_version"])
            rows.append(row)
    if not rows:
        raise DatasetError("Manifest contains no approved samples")
    if len(consent_versions) != 1 or len(protocol_versions) != 1:
        raise DatasetError("A manifest must use one consent version and one study protocol version")
    return rows


def split_by_subject(rows: list[dict], seed: str = "nexus-face-research-v1",
                     train: float = 0.60, validation: float = 0.20) -> dict[str, list[str]]:
    """Deterministically assign whole identities to partitions; images never cross splits."""
    if not 0 < train < 1 or not 0 < validation < 1 or train + validation >= 1:
        raise ValueError("train and validation fractions must be positive and sum below 1")
    subjects = {row["subject_id"] for row in rows}
    if len(subjects) < 3:
        raise DatasetError("At least three distinct subjects are required for three partitions")
    ordered = sorted(subjects, key=lambda subject: hashlib.sha256(f"{seed}:{subject}".encode()).hexdigest())
    n = len(ordered)
    train_n = min(max(1, math.floor(n * train)), n - 2)
    validation_n = min(max(1, math.floor(n * validation)), n - train_n - 1)
    assignment = {
        "train": ordered[:train_n],
        "validation": ordered[train_n:train_n + validation_n],
        "test": ordered[train_n + validation_n:],
    }
    return assignment


def _read_scores(path: Path) -> list[tuple[bool, float]]:
    """Read pair scores; match labels are derived from subject IDs, not trusted labels."""
    pairs = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"subject_a", "subject_b", "score"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise DatasetError("Score CSV must contain subject_a, subject_b, score columns")
        for line_number, row in enumerate(reader, 2):
            try:
                score = float(row["score"])
            except (TypeError, ValueError) as exc:
                raise DatasetError(f"Invalid score on line {line_number}") from exc
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise DatasetError(f"Score must be finite and between 0 and 1 on line {line_number}")
            if not row["subject_a"] or not row["subject_b"]:
                raise DatasetError(f"Missing subject ID on line {line_number}")
            pairs.append((row["subject_a"] == row["subject_b"], score))
    if not pairs or not any(match for match, _ in pairs) or not any(not match for match, _ in pairs):
        raise DatasetError("Evaluation requires at least one genuine and one impostor pair")
    return pairs


def metrics(pairs: list[tuple[bool, float]], threshold: float) -> dict:
    genuine = [score for match, score in pairs if match]
    impostor = [score for match, score in pairs if not match]
    false_accepts = sum(score >= threshold for score in impostor)
    false_rejects = sum(score < threshold for score in genuine)
    false_match_rate = false_accepts / len(impostor)
    false_non_match_rate = false_rejects / len(genuine)
    return {
        "threshold": threshold,
        "genuine_pairs": len(genuine),
        "impostor_pairs": len(impostor),
        "false_matches": false_accepts,
        "false_non_matches": false_rejects,
        "false_match_rate": false_match_rate,
        "false_match_rate_95ci": _wilson_interval(false_accepts, len(impostor)),
        "false_non_match_rate": false_non_match_rate,
        "false_non_match_rate_95ci": _wilson_interval(false_rejects, len(genuine)),
    }


def _wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> dict:
    """Return a two-sided 95% Wilson interval for a binomial rate."""
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("Wilson interval requires 0 <= successes <= positive total")
    rate = successes / total
    z_squared = z * z
    denominator = 1 + z_squared / total
    center = (rate + z_squared / (2 * total)) / denominator
    half_width = z * math.sqrt(rate * (1 - rate) / total + z_squared / (4 * total * total)) / denominator
    return {"lower": max(0.0, center - half_width), "upper": min(1.0, center + half_width)}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_threshold(validation_pairs: list[tuple[bool, float]], target_far: float) -> float:
    """Select a threshold on validation only, minimizing FRR under the requested FAR cap."""
    if not 0 <= target_far <= 1:
        raise ValueError("target FAR must be between 0 and 1")
    if not any(match for match, _ in validation_pairs) or not any(not match for match, _ in validation_pairs):
        raise DatasetError("Validation needs genuine and impostor pairs")
    candidates = sorted({0.0, 1.0, *(score for _, score in validation_pairs)})
    valid = [threshold for threshold in candidates
             if metrics(validation_pairs, threshold)["false_match_rate"] <= target_far]
    if not valid:
        raise DatasetError("No threshold satisfies target FAR on validation data")
    return min(valid, key=lambda t: (metrics(validation_pairs, t)["false_non_match_rate"], -t))


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline, research-only face evaluation utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-manifest")
    validate.add_argument("manifest", type=Path)
    validate.add_argument("--image-root", type=Path, required=True)
    split = sub.add_parser("split")
    split.add_argument("manifest", type=Path)
    split.add_argument("--image-root", type=Path, required=True)
    split.add_argument("--seed", default="nexus-face-research-v1")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("validation_scores", type=Path)
    evaluate.add_argument("test_scores", type=Path)
    evaluate.add_argument("--target-far", type=float, default=0.001)
    evaluate.add_argument("--model-version", default="unspecified")
    evaluate.add_argument("--study-version", default="unspecified")
    evaluate.add_argument("--output", type=Path, help="Write the review report as JSON (contains no identities or images)")
    args = parser.parse_args()
    if args.command in {"validate-manifest", "split"}:
        rows = load_manifest(args.manifest, args.image_root)
        if args.command == "validate-manifest":
            print(json.dumps({"approved_samples": len(rows), "subjects": len({r['subject_id'] for r in rows})}))
        else:
            print(json.dumps(split_by_subject(rows, args.seed), indent=2))
        return
    if not 0 <= args.target_far <= 1:
        parser.error("target-far must be between 0 and 1")
    validation_pairs = _read_scores(args.validation_scores)
    test_pairs = _read_scores(args.test_scores)
    threshold = select_threshold(validation_pairs, args.target_far)
    validation_report = metrics(validation_pairs, threshold)
    test_report = metrics(test_pairs, threshold)
    warnings = [
        "Research metrics only; they do not establish identity, liveness, security, or authentication readiness.",
        "The threshold was selected using validation scores and evaluated unchanged on test scores.",
        "Wilson intervals treat pair rows as independent; pairs may share participants and captures, so interval coverage can be optimistic.",
    ]
    if test_report["false_match_rate_95ci"]["upper"] > args.target_far:
        warnings.append("The test false-match 95% confidence interval exceeds the requested target; this run does not demonstrate that the target is met.")
    report = {
        "report_version": 1,
        "model_version": args.model_version,
        "study_version": args.study_version,
        "target_false_match_rate": args.target_far,
        "threshold": threshold,
        "threshold_selected_on": "validation",
        "confidence_interval_method": "95% Wilson binomial intervals at pair level; independence assumption may be violated",
        "validation": validation_report,
        "test": test_report,
        "inputs": {
            "validation_scores_sha256": _sha256_file(args.validation_scores),
            "test_scores_sha256": _sha256_file(args.test_scores),
        },
        "warnings": warnings,
    }
    print(json.dumps(report, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote evaluation report: {args.output}")


if __name__ == "__main__":
    main()


