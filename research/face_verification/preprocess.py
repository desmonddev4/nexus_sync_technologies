"""Offline Haar-cascade face crop preparation; does not identify people or detect spoofing."""
import argparse
from collections import Counter
from pathlib import Path

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit("Install research dependencies with pip install -r requirements.txt") from exc

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class CropRejected(ValueError):
    pass


def create_detector():
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        raise RuntimeError("OpenCV frontal-face cascade failed to load")
    return detector


def make_face_crop(image_rgb: np.ndarray, detector, output_size: int = 112) -> np.ndarray:
    """Return one square RGB crop; reject no-face, multi-face, or too-small captures."""
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise CropRejected("unsupported_image")
    height, width = image_rgb.shape[:2]
    if min(height, width) < 160:
        raise CropRejected("image_too_small")
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                      minSize=(80, 80), flags=cv2.CASCADE_SCALE_IMAGE)
    if len(faces) == 0:
        raise CropRejected("no_face")
    if len(faces) != 1:
        raise CropRejected("multiple_faces")
    x, y, face_width, face_height = (int(value) for value in faces[0])
    side = int(round(max(face_width, face_height) * 1.35))
    center_x = x + face_width // 2
    center_y = y + face_height // 2
    left = max(0, center_x - side // 2)
    top = max(0, center_y - side // 2)
    right = min(width, left + side)
    bottom = min(height, top + side)
    left = max(0, right - side)
    top = max(0, bottom - side)
    crop = image_rgb[top:bottom, left:right]
    if crop.size == 0 or min(crop.shape[:2]) < 80:
        raise CropRejected("face_crop_too_small")
    return cv2.resize(crop, (output_size, output_size), interpolation=cv2.INTER_AREA if side > output_size else cv2.INTER_CUBIC)


def main():
    parser = argparse.ArgumentParser(description="Create research face crops; originals remain untouched")
    parser.add_argument("source", type=Path, help="Folder containing source images")
    parser.add_argument("output", type=Path, help="Separate folder for generated face crops")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if not source.is_dir():
        parser.error("source must be a directory")
    output = args.output.resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        parser.error("source and output directories must be separate and non-overlapping")
    files = sorted(path for path in source.rglob("*") if path.is_file() and not path.is_symlink() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        raise SystemExit("No supported image files found")

    detector = create_detector()
    outcomes = Counter()
    for source_path in files:
        relative = source_path.relative_to(source)
        try:
            with Image.open(source_path) as opened:
                rgb = np.asarray(ImageOps.exif_transpose(opened).convert("RGB"))
            face = make_face_crop(rgb, detector)
            target = (output / relative).with_suffix(".jpg")
            if target.exists():
                outcomes["output_exists"] += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            bgr = cv2.cvtColor(face, cv2.COLOR_RGB2BGR)
            if not cv2.imwrite(str(target), bgr, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                outcomes["write_error"] += 1
            else:
                outcomes["cropped"] += 1
        except CropRejected as exc:
            outcomes[str(exc)] += 1
        except (OSError, cv2.error, ValueError):
            outcomes["unreadable_or_processing_error"] += 1
    print(f"Processed {len(files)} image files; outcomes={dict(sorted(outcomes.items()))}")
    print("Inspect crops manually before review/manifest approval. No filenames or face data were printed.")
    print("The Haar detector is a basic frontal-face locator, not face verification or PAD.")


if __name__ == "__main__":
    main()

