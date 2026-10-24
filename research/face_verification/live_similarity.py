"""Live webcam face-embedding similarity viewer. It never grants access or stores frames."""
import argparse
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
    import torch
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit("Install research dependencies with pip install -r requirements.txt") from exc

from model import FaceEmbeddingNet
from preprocess import CropRejected, create_detector, make_face_crop

IMAGE_SIZE = 112
PREPROCESSING_VERSION = "rgb-center-112-bilinear-v1"


def tensor_from_rgb(rgb):
    resized = Image.fromarray(rgb).resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
    tensor = torch.from_numpy(np.asarray(resized).copy()).permute(2, 0, 1).float() / 255.0
    return ((tensor - 0.5) / 0.5).unsqueeze(0)


def reference_images(folder: Path):
    paths = sorted(path for path in folder.rglob("*") if path.is_file() and not path.is_symlink()
                   and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"})
    if len(paths) < 2:
        raise SystemExit("Provide at least two approved, aligned reference crops.")
    return paths


def main():
    parser = argparse.ArgumentParser(description="Compare live face embeddings with a reference set (research only)")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("reference_dir", type=Path, help="Approved, aligned reference crops for one claimed person")
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    if not args.checkpoint.is_file() or not args.reference_dir.is_dir():
        parser.error("checkpoint and reference_dir must exist")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=True)
    if checkpoint.get("checkpoint_version") != 1 or checkpoint.get("architecture") != "nexus-face-cnn-v1":
        raise SystemExit("Unsupported checkpoint version or architecture")
    if checkpoint.get("image_size") != IMAGE_SIZE or checkpoint.get("preprocessing") != PREPROCESSING_VERSION:
        raise SystemExit("Unsupported model input preprocessing version")
    model = FaceEmbeddingNet(checkpoint["embedding_size"]).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    refs = []
    try:
        with torch.inference_mode():
            for path in reference_images(args.reference_dir):
                with Image.open(path) as opened:
                    image = np.asarray(ImageOps.exif_transpose(opened).convert("RGB"))
                refs.append(model(tensor_from_rgb(image).to(device))[0])
            template = torch.nn.functional.normalize(torch.stack(refs).mean(dim=0), p=2, dim=0)
    except (OSError, ValueError) as exc:
        raise SystemExit("Could not read the reference crops.") from exc

    detector = create_detector()
    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        camera.release()
        raise SystemExit("Could not open the selected camera.")
    print("Research view only: similarity score, no match threshold, liveness, or access decision. Press Q to close.")
    try:
        with torch.inference_mode():
            while True:
                ok, frame = camera.read()
                if not ok:
                    print("Camera frame unavailable; stopping.")
                    break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                try:
                    crop = make_face_crop(rgb, detector)
                    query = model(tensor_from_rgb(crop).to(device))[0]
                    similarity = float(torch.dot(template, query).item())
                    label = f"Embedding similarity: {similarity:.3f}"
                    color = (80, 220, 150)
                except CropRejected as exc:
                    label = f"Capture rejected: {exc}"
                    color = (80, 170, 255)
                cv2.putText(frame, label, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.68, color, 2, cv2.LINE_AA)
                cv2.putText(frame, "Research only | spoof checks unavailable", (18, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow("Nexus face embedding research", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                    break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
