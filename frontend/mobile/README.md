# Nexus Sync Mobile

Expo and React Native client for patient accounts, connected to the existing Nexus Sync backend.

## Setup

```bash
cd frontend/mobile
npm install
Copy-Item .env.example .env
npx expo start
```

Set `EXPO_PUBLIC_API_URL` to the backend origin (without `/api/v1`). The production default is `https://nexus-sync-backend.onrender.com`. Accounts must already be provisioned by an administrator; the backend has no public patient registration endpoint. To provision a caretaker, create an emergency_contact account with a phone number matching a verified emergency contact on the patient record. The patient can then grant that username selected access scopes in My Circle.

## Live data and access

The app signs in with the backend username/password token endpoint and stores the token in platform secure storage. Patient accounts load their linked patient record, measurements, devices, emergency contacts, consent records, and incident history from the API. SOS sends a confirmed manual incident to the backend.

Biometric SecureStore authentication requires a native development or production build; Expo Go cannot exercise Face ID protected storage. Caretaker access is patient-controlled. A patient can share selected scopes with a provisioned emergency-contact account whose phone matches a verified emergency contact. Patients can revoke a grant at any time; caretaker profiles redact medical notes, birth date, phone, contact list, and consent history. First sign-in uses the provisioned account password. Optional Face ID or strong device biometrics can then unlock the saved token locally; biometric data is never sent to the backend. Signing out revokes the current backend token.

SOS requests include a current phone location when the user grants OS permission. Notification status is read from the server and refreshed in Activity; a recipient can acknowledge their own alert there. SMS delivery requires active patient consent, verified phone contacts, and configured provider credentials. The app reports the server response accurately and does not imply dispatch. Preferences and contact editing are not offered because no corresponding patient-facing write APIs exist.





## Voluntary face research capture

The Profile screen can capture a user's own face image for a consented research dataset. It is available only when the backend explicitly sets `BIOMETRIC_RESEARCH_ENABLED=true`, `BIOMETRIC_RESEARCH_CONSENT_VERSION`, and `BIOMETRIC_SAMPLE_ENCRYPTION_KEY`. Enable the research flag only after the consent notice and scheduled deletion process have been reviewed. Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store that value as a backend secret; never commit it. Apply backend migrations and schedule `python manage.py prune_face_research_samples` at least daily so the 30-day maximum retention is enforced. The endpoint limits submissions to five per account per day, encrypts image bytes before database storage, provides no image download, and lets the participant delete their samples. Caretakers enroll themselves; a coordinator cannot enroll someone else's face. Existing patient grants remain the sole source of caretaker access.

This capture flow is not face recognition or liveness detection. Samples remain unreviewed research data and never authorize sign-in. Do not enable it with real participants until the consent notice is reviewed for the applicable Ghana privacy and health-data requirements. `BIOMETRIC_VERIFIER_CLASS` remains unset, and the verifier boundary is not connected to authentication. Setting `BIOMETRIC_RESEARCH_ENABLED=true` enables only consented capture; it does not turn on matching or sign-in.
