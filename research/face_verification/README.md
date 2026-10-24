# Face verification research pipeline

This standalone research package validates an explicitly consented and reviewed image manifest, splits identities into train/validation/test partitions, trains a small custom CNN from random initialization, and evaluates 1:1 pair scores. It is not connected to the application sign-in or authorization paths.

The custom network starts from random weights and uses an ArcFace-style angular-margin training head; the design is informed by the published [ArcFace paper](https://openaccess.thecvf.com/content_CVPR_2019/html/Deng_ArcFace_Additive_Angular_Margin_Loss_for_Deep_Face_Recognition_CVPR_2019_paper.html). This is an implementation baseline, not a reproduction of that paper's full system or results.

## Current limits

No trained model or participant dataset is included. The dataset directory contains only a manifest template, so the pipeline cannot train or evaluate a recognizer yet. The default 60/20/20 identity split means the current trainer needs at least 10 distinct identities with at least 2 captures each (20 captures) before it can start. This is only a software smoke-test floor, not enough data to claim a useful or safe recognizer. Real evaluation needs a substantially larger, representative, consented dataset, including different capture sessions and conditions. Add other consenting participants later; do not create duplicate or synthetic identities to bypass the guard.

This research model is only an initial engineering baseline. It expects centered 112x112 face crops; it does not align facial landmarks. Presentation-attack detection (PAD), liveness, mobile inference, demographic/condition analysis, model calibration, security review, and authentication integration are not implemented. No model accuracy or safety claim can be made. Do not connect model output to care access or sign-in.

## Dataset manifest

Use UTF-8 JSON Lines with one row per capture. Keep direct identifiers out of the manifest; use opaque subject IDs. `consent` must be boolean `true`, `review_status` must be `approved`, and each `image_path` must resolve to a file under the image root. The manifest template is at `dataset/metadata/manifest.template.jsonl` and is not a real sample.

Required fields: `sample_id`, `subject_id`, `image_path`, `consent`, `review_status`, `consent_version`, `session_id`, and `protocol_version`. A manifest must use one consent notice and one protocol version, and each image path must refer to a unique file under the image root. Optional capture metadata fields are `capture_device`, `lighting`, `pose`, `age_band`, and `assistive_device`; use only approved, non-identifying categories. Store names, contact details, account IDs, patient IDs, and any re-identification key separately from this workspace.

## Setup and workflow

Run the commands below from `research/face_verification`.

Install these dependencies in an isolated research environment, not the backend or mobile app:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Validate and split identities deterministically:

```powershell
python pipeline.py validate-manifest dataset\metadata\manifest.jsonl --image-root dataset
python pipeline.py split dataset\metadata\manifest.jsonl --image-root dataset --seed study-v1
```

Train from scratch only after the dataset passes the trainer's identity/capture requirements:

```powershell
python train.py dataset\metadata\manifest.jsonl --image-root dataset --output checkpoints\nexus-face-cnn-v1.pt --seed study-v1
```

Generate scores separately for validation and test identities, then select a threshold using validation scores and evaluate that fixed threshold on test scores. Save the resulting review report with explicit model and study version labels:

```powershell
python score_pairs.py dataset\metadata\manifest.jsonl checkpoints\nexus-face-cnn-v1.pt --image-root dataset --partition validation --output checkpoints\validation-pairs.csv --seed study-v1
python score_pairs.py dataset\metadata\manifest.jsonl checkpoints\nexus-face-cnn-v1.pt --image-root dataset --partition test --output checkpoints\test-pairs.csv --seed study-v1
python pipeline.py evaluate checkpoints\validation-pairs.csv checkpoints\test-pairs.csv --target-far 0.001 --model-version nexus-face-cnn-v1 --study-version study-v1 --output checkpoints\evaluation-report.json
```

A genuine pair is derived when the opaque subject IDs match. Impostor pairs are capped to 100,000 by default; set a higher cap for larger evaluation sets. The report includes genuine/impostor counts, errors, Wilson 95% confidence intervals, the validation-selected threshold, unchanged validation and test results, version labels, and SHA-256 hashes of both score files. It warns when the test false-match interval does not support the requested target. The report deliberately omits subject IDs and image data. The intervals treat pair rows as independent, while pairs can reuse the same participants and captures; this can make intervals optimistic, so they are a screening aid rather than a readiness claim. Low false-match targets require many independent impostor comparisons: even zero observed false matches does not establish a very low rate when the sample is small. Each checkpoint records the preprocessing identifier, seed, training settings, manifest SHA-256, and split SHA-256; the seed controls the Python, Torch, CUDA, and data-loader random generators. This improves traceability, but exact reproducibility across different hardware and library versions is not guaranteed. Keep score-generation code version and study protocol/data version with the report. Never tune on test data.

The pair-score CSV contains pseudonymous identity labels and must be treated as sensitive research data. Checkpoints and image folders are ignored by Git; this is not encryption or a substitute for approved storage. Pair-score generation checks the checkpoint version, preprocessing identifier, seed, manifest hash, and split hash before reading evaluation images, and stops if any of them differ. The trainer does not copy source images into the checkpoint.

## Face embeddings and local live capture

`FaceEmbeddingNet` is our own randomly initialized CNN. It maps each 112x112 crop to a 128-dimensional L2-normalized face embedding. Training uses an ArcFace-style identity classification head; at inference, reference embeddings are averaged and normalized, then compared with a new capture using cosine similarity. Embeddings are sensitive biometric templates.

After a model has been trained and the test threshold/evaluation have been reviewed, `live_similarity.py` can exercise a local webcam and show the embedding similarity to one claimed person's reference crops:

```powershell
python live_similarity.py checkpoints\nexus-face-cnn-v1.pt C:\FaceResearchPrivate\aligned\subject-001
```

This viewer displays a score only. It does not choose a login threshold, prove liveness, record video, save frames, or issue/revoke credentials. A printed face or replay can still produce a score. Do not use it to grant access.
## Data handling

See `dataset/README.md` before adding any real photos. Do not add participant images until the study purpose, consent, retention/deletion, access controls, storage, and review process are agreed and approved. The pipeline does not encrypt or securely erase images.

## Image preparation

The training code requires one centered face crop resized to 112x112. `preprocess.py` uses OpenCV's bundled frontal-face Haar cascade to find exactly one face, crop a square region, and resize it to 112x112. This is a conventional pretrained detector used only to locate a face; the recognition CNN still starts with random weights and is trained by this project. OpenCV documents `CascadeClassifier.detectMultiScale` as returning face/object rectangles: [OpenCV cascade classifier documentation](https://docs.opencv.org/doc/doxygen/html/db/d28/tutorial_cascade_classifier.html).

Run from this package directory and write crops to a private local folder outside OneDrive and this repository:

```powershell
python preprocess.py dataset\images C:\FaceResearchPrivate\aligned
```

Ensure the output folder is on an encrypted drive and not cloud-synced. The script does not alter source photos, never overwrites an existing crop, rejects no-face/multi-face/tiny images, strips EXIF metadata from output crops, and logs only aggregate counts. Haar detection is an old, limited frontal-face method and can miss or falsely detect faces. It does not align eyes, verify identity, detect presentation attacks, or establish image quality/fairness. Inspect generated crops locally before marking a manifest entry approved. Do not use this as a real-time mobile sign-in capture component.





