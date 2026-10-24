# Local face sign-in experiment

This is a development-only, two-factor experiment: the operator must supply a valid password and a face capture. It uses InsightFace `buffalo_l` public pretrained weights, which are restricted to non-commercial research unless separately licensed. It is not approved for deployment.

The experiment is disabled by default and the API also refuses to run unless Django `DEBUG=true`. Enrollment and sign-in require a short, server-signed challenge: one centered frame followed by randomized left/right head turns. The server checks the face detector's five-point landmarks across all three frames, and the passive InsightFace RGB check runs on the center frame. This basic motion check can reject a single still reused for every prompt, but it is not a certified presentation-attack detector and can be bypassed by more capable replay or injection attacks. Do not use this flow for real operations, emergency dispatch, patient care, or production access decisions.

## Enable locally

From `backend`, create and activate an isolated environment, then install the application and optional face dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-face-dev.txt
python manage.py migrate
```

The first face request downloads InsightFace's public `buffalo_l` package. Review and accept the model's non-commercial research terms before using it. On Windows, ONNX Runtime also requires the Microsoft Visual C++ 2019 runtime. Configure the local backend `.env` with:

```dotenv
DJANGO_DEBUG=true
BIOMETRIC_FACE_LOGIN_ENABLED=true
BIOMETRIC_FACE_CONSENT_VERSION=face-login-dev-v1
BIOMETRIC_MODEL_NAME=buffalo_l
BIOMETRIC_MATCH_THRESHOLD=0.45
BIOMETRIC_FACE_LIVENESS_ENABLED=true
BIOMETRIC_LIVENESS_THRESHOLD=0.8
BIOMETRIC_FACE_ENCRYPTION_KEY=<new Fernet key kept outside source control>
BIOMETRIC_MODEL_ROOT=.face-model-cache
```

With liveness enabled, the first face request also downloads the separate `liveness.onnx` add-on to `.face-model-cache/addons/`. InsightFace verifies this file against its packaged SHA-256 before loading it. Keep the threshold at `0.8` for the initial local experiment; it is not calibrated for this laptop camera or deployment setup.

Generate a Fernet key locally with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Do not commit the generated key. In `frontend/admin/.env.local`, set:

```dotenv
VITE_BIOMETRIC_FACE_LOGIN_ENABLED=true
VITE_BIOMETRIC_FACE_CONSENT_VERSION=face-login-dev-v1
```

Restart both development servers after changing environment variables. Run the accounts migration before starting the backend.

## Try the flow

On the login page, choose **Enroll test face**, review and check the consent box, enter an operations account's username and password, then start the motion check. Capture a centered face and follow the randomized left/right prompts. Enrollment stores the centered frame's encrypted embedding. Sign out, choose **Face test**, enter the same password, and complete a new motion check. The API returns an auth token only when the signed challenge, password, passive check, and face comparison pass. Normal password sign-in remains available for local development.

An enrolled operator can delete their template using the authenticated `DELETE /api/v1/auth/biometrics/face-enrollment/` endpoint. The enrollment and sign-in endpoints audit outcomes without recording images, embeddings, or similarity scores. Browser camera access requires localhost or HTTPS.

This test does not assess real-world false-match rates, demographic performance, robust presentation-attack detection, or whether either threshold is appropriate. A successful live capture and rejected static replay are only smoke checks, not a security evaluation. Use only your own or explicitly consenting test accounts. Do not enroll patients or collect face data for this experiment.

## Explore the face-match threshold

The configured match cutoff (`0.45`) is still a placeholder. To estimate a development cutoff, collect at least 20 usable JPEG/PNG captures of the enrolled operator in `backend/.local-face-calibration/genuine/`, and at least 20 captures of consenting people who are not enrolled in `backend/.local-face-calibration/impostor/`. Include varied lighting and poses; use multiple consenting people for impostor captures when possible. Keep these images local; the folders are ignored by Git.

Run:

```powershell
python manage.py calibrate_face_threshold `
  --username face-test-operator `
  --genuine-dir .local-face-calibration/genuine `
  --impostor-dir .local-face-calibration/impostor `
  --target-far 0.01
```

The command uses the existing encrypted enrollment as its reference. It runs current image, face, and enabled liveness checks; computes scores in memory; and prints empirical false-accept and false-reject rates plus an exploratory cutoff. It does not save images or scores and does not change `BIOMETRIC_MATCH_THRESHOLD`. Use a separate validation set before changing the local setting. Small or repeated captures cannot establish production accuracy.
