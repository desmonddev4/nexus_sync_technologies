"""Train the research CNN from scratch; never used by the application sign-in path."""
import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

try:
    import torch
    from PIL import Image
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
except ImportError as exc:
    raise SystemExit("Install only this research package's dependencies: pip install -r requirements.txt") from exc

from pipeline import DatasetError, load_manifest, split_by_subject
from model import AngularMarginHead, FaceEmbeddingNet

IMAGE_SIZE = 112


class FaceDataset(Dataset):
    def __init__(self, rows, labels):
        self.rows = rows
        self.labels = labels

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        path = self.image_root / row["image_path"]
        with Image.open(path) as opened:
            image = opened.convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
        tensor = torch.from_numpy(__import__("numpy").asarray(image).copy()).permute(2, 0, 1).float() / 255.0
        tensor = (tensor - 0.5) / 0.5
        return tensor, self.labels[row["subject_id"]]


def require_partition_data(rows, split):
    grouped = {name: [row for row in rows if row["subject_id"] in subjects]
               for name, subjects in split.items()}
    counts = {name: Counter(row["subject_id"] for row in part) for name, part in grouped.items()}
    problems = []
    if len(counts["train"]) < 2:
        problems.append("training needs at least 2 distinct identities")
    if any(value < 2 for value in counts["train"].values()):
        problems.append("each training identity needs at least 2 captures")
    for name in ("validation", "test"):
        if len(counts[name]) < 2:
            problems.append(f"{name} needs at least 2 distinct identities")
        if any(value < 2 for value in counts[name].values()):
            problems.append(f"each {name} identity needs at least 2 captures")
    if problems:
        raise DatasetError("Insufficient data: " + "; ".join(problems))
    return grouped


def main():
    parser = argparse.ArgumentParser(description="Research-only custom face embedding trainer")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", default="nexus-face-research-v1")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 2:
        parser.error("epochs must be positive and batch-size at least 2")

    try:
        rows = load_manifest(args.manifest, args.image_root)
        split = split_by_subject(rows, args.seed)
        partitions = require_partition_data(rows, split)
    except (DatasetError, OSError) as exc:
        raise SystemExit(str(exc)) from exc

    # This pipeline expects already cropped and centered face images; no landmark alignment is performed.
    # A face detector/alignment component and PAD are not implemented here.
    seed_value = int.from_bytes(hashlib.sha256(args.seed.encode("utf-8")).digest()[:4], "big")
    random.seed(seed_value)
    torch.manual_seed(seed_value)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed_value)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    data_generator = torch.Generator().manual_seed(seed_value)
    labels_by_subject = {subject: i for i, subject in enumerate(sorted(split["train"]))}
    train_data = FaceDataset(partitions["train"], labels_by_subject)
    train_data.image_root = args.image_root.resolve()
    loader = DataLoader(train_data, batch_size=args.batch_size, shuffle=True, num_workers=0, generator=data_generator)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = FaceEmbeddingNet().to(device)
    head = AngularMarginHead(128, len(labels_by_subject)).to(device)
    optimizer = torch.optim.AdamW(list(model.parameters()) + list(head.parameters()), lr=0.001, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(args.epochs):
        model.train()
        head.train()
        total_loss = 0.0
        seen = 0
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(head(model(images)), labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * labels.size(0)
            seen += labels.size(0)
        print(f"epoch={epoch + 1}/{args.epochs} train_loss={total_loss / max(seen, 1):.4f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    split_fingerprint = hashlib.sha256(json.dumps(split, sort_keys=True).encode("utf-8")).hexdigest()
    torch.save({"checkpoint_version": 1, "model_state": model.cpu().state_dict(),
                "architecture": "nexus-face-cnn-v1", "preprocessing": "rgb-center-112-bilinear-v1",
                "embedding_size": 128, "image_size": IMAGE_SIZE, "seed": args.seed,
                "seed_value": seed_value, "epochs": args.epochs, "batch_size": args.batch_size,
                "optimizer": "AdamW", "learning_rate": 0.001,
                "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                "split_sha256": split_fingerprint,
                "training_capture_count": len(partitions["train"]),
                "training_subject_count": len(labels_by_subject),
                "validation_subject_count": len(split["validation"]),
                "test_subject_count": len(split["test"]),
                "warning": "Research-only. No PAD, validated threshold, or authentication use."}, args.output)
    print(f"Saved research checkpoint: {args.output}")
    print("Next: generate validation and test pair scores; choose a threshold on validation only.")
    print("This command does not use validation/test images for training or authenticate anyone.")


if __name__ == "__main__":
    main()


