# Dataset workspace (empty by design)

This folder is the local research dataset boundary. It contains no participant photos or labels yet. Do not add real face images until the study protocol, participant information, consent process, retention/deletion plan, access controls, and applicable institutional/privacy review are approved.

## Folder layout

- `images/`: authorized research captures only. Keep this folder out of source control and backups that are not approved for biometric data.
- `metadata/manifest.jsonl`: one row per capture, with pseudonymous subject IDs and explicit consent/review state. No names, emails, phone numbers, account IDs, patient IDs, diagnoses, or other direct identifiers.
- `metadata/identity-key.csv`: if a re-identification key is necessary, store it separately under restricted access. This repository is not an appropriate place for that key.

`manifest.template.jsonl` is a schema example only and must never be treated as a real sample. Manifest rows are not training-ready until the participant has consented to this exact research purpose and a reviewer has approved data quality and labels.

## Capture protocol outline

After a study is approved, collect multiple sessions per participant rather than bursts from one sitting. Record the study protocol version and opaque subject/session IDs. Vary ordinary capture conditions such as indoor lighting, camera distance, pose, and supported phone model. Do not ask participants to remove assistive devices or change medically necessary equipment. Offer breaks and a clear withdrawal/deletion route. Do not collect health measurements for face matching or use face capture to make care decisions.

The first research dataset should support 1:1 verification: each trial compares a claimed participant with a capture. Keep identities disjoint across training, validation, and test partitions. Keep sessions from an identity together in a partition. The current pipeline performs identity-level partitioning; it does not generate face crops, embeddings, or pair scores.

## Before adding real data

1. Approve the study purpose, eligibility, risks, participant-facing information, explicit opt-in/withdrawal process, retention period, deletion method, access list, encryption and backup policy, and contact for questions.
2. Decide whether the data may be used to train a custom model and for which exact future purposes; consent to capture alone is not blanket consent to all future model training.
3. Collect only from participants who can give informed consent under the approved process. Do not use patient records or staff photos as a shortcut.
4. Store source images in an approved encrypted location with limited access. Keep this workspace empty unless it is explicitly approved for that data.
5. Review data quality and labels before setting `review_status` to `approved`; retain a record of the reviewer and review protocol outside public reports.
6. Run `python pipeline.py validate-manifest dataset/metadata/manifest.jsonl --image-root dataset` only after adding real, authorized samples. The current pipeline does not itself encrypt or securely erase images.

This is a research dataset preparation guide, not a consent form, legal opinion, ethics approval, recognition model, liveness detector, or authentication system. No synthetic-face examples are included because they cannot validate the intended real-person identity task.
