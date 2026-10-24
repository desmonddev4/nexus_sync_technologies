"""Generate pair similarity CSVs for validation or test identities; research only."""
import argparse
import csv
import hashlib
import json
import random
from itertools import combinations
from pathlib import Path

try:
    import torch
    from torch.utils.data import DataLoader
except ImportError as exc:
    raise SystemExit("Install research dependencies with pip install -r requirements.txt") from exc

from pipeline import DatasetError, load_manifest, split_by_subject
from model import FaceEmbeddingNet
from train import FaceDataset


def main():
    parser = argparse.ArgumentParser(description="Generate offline face pair scores")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--partition", choices=("validation", "test"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", default="nexus-face-research-v1")
    parser.add_argument("--max-impostor-pairs", type=int, default=100000)
    args = parser.parse_args()
    if args.max_impostor_pairs < 1:
        parser.error("max-impostor-pairs must be positive")

    try:
        rows = load_manifest(args.manifest, args.image_root)
        split = split_by_subject(rows, args.seed)
        subjects = split[args.partition]
    except (DatasetError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
    partition_rows = [row for row in rows if row["subject_id"] in subjects]
    counts = {}
    for row in partition_rows:
        counts[row["subject_id"]] = counts.get(row["subject_id"], 0) + 1
    if len(counts) < 2 or any(count < 2 for count in counts.values()):
        raise SystemExit(f"{args.partition} scoring requires at least 2 identities with 2 captures each")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # weights_only avoids loading arbitrary Python objects from a checkpoint file.
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=True)
    if checkpoint.get("checkpoint_version") != 1 or checkpoint.get("architecture") != "nexus-face-cnn-v1":
        raise SystemExit("Unsupported checkpoint version or architecture")
    if checkpoint.get("image_size") != 112 or checkpoint.get("preprocessing") != "rgb-center-112-bilinear-v1":
        raise SystemExit("Unsupported checkpoint preprocessing version")
    if checkpoint.get("seed") != args.seed:
        raise SystemExit("Split seed does not match the training checkpoint")
    manifest_sha256 = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    split_sha256 = hashlib.sha256(json.dumps(split, sort_keys=True).encode("utf-8")).hexdigest()
    if checkpoint.get("manifest_sha256") != manifest_sha256:
        raise SystemExit("Manifest does not match the training checkpoint")
    if checkpoint.get("split_sha256") != split_sha256:
        raise SystemExit("Identity split does not match the training checkpoint")
    model = FaceEmbeddingNet(checkpoint["embedding_size"]).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    dataset = FaceDataset(partition_rows, {subject: 0 for subject in counts})
    dataset.image_root = args.image_root.resolve()
    loader = DataLoader(dataset, batch_size=64, shuffle=False, num_workers=0)
    embeddings = []
    with torch.inference_mode():
        for images, _ in loader:
            embeddings.extend(model(images.to(device)).cpu())

    genuine = []
    impostor = []
    for i, j in combinations(range(len(partition_rows)), 2):
        # Cosine similarity is mapped monotonically to the evaluator's [0, 1] score range.
        score = (float(torch.dot(embeddings[i], embeddings[j]).item()) + 1.0) / 2.0
        pair = (partition_rows[i]["subject_id"], partition_rows[j]["subject_id"], score)
        (genuine if pair[0] == pair[1] else impostor).append(pair)
    if not genuine or not impostor:
        raise SystemExit("No genuine/impostor pairs could be formed from this partition")
    if len(impostor) > args.max_impostor_pairs:
        impostor = random.Random(args.seed).sample(impostor, args.max_impostor_pairs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("subject_a", "subject_b", "score"))
        writer.writerows(genuine + impostor)
    print(f"Wrote {len(genuine)} genuine and {len(impostor)} impostor pair scores to {args.output}")
    print("Pair scores and identities are sensitive research data; keep this file local and restricted.")


if __name__ == "__main__":
    main()
