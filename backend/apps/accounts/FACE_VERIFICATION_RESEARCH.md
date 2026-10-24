# Face verification research boundary

## Status

This document defines the safe implementation boundary. The mobile app supports device-local session unlock and an optional, consented development motion-check screen. That screen only checks prompted head movement; it does not compare an uploaded face with a backend identity, retain its frames, or affect login. The research system must remain disconnected from login until evaluation and independent review are complete.

## Identity and enrollment

- Patients enroll only while authenticated to their provisioned account. Caretakers enroll to their own account; the backend associates the account role and its active patient grants. A coordinator must not silently enroll a caretaker or patient from an arbitrary photograph.
- Enrollment requires a clear, versioned, explicit opt-in that is separate from general health-monitoring consent. Declining or withdrawing must preserve password sign-in and must not reduce care access.
- Collect camera captures only for a stated purpose. No gallery search, face identification across unrelated accounts, or silent capture. Encrypt any retained sample/template with keys held outside the database, restrict access, audit reads and deletion, and define retention before collecting real faces.
- Never put photographs, embeddings, match scores, or challenge material in ordinary application logs or audit metadata. Delete raw capture promptly after deriving an approved representation, unless a separately consented research protocol explicitly retains it.

## Verification and model lifecycle

- Enrollment creates a versioned reference representation for 1:1 verification. A submitted username/account selects the claimed identity; do not perform 1:N identification.
- A verifier must combine face comparison with presentation-attack detection (PAD). Image similarity alone, a blink prompt alone, or a client-supplied `live=true` flag is not proof of liveness.
- Keep verification in shadow/research mode: record only the minimum permitted evaluation outcome and never issue/revoke a login token based on the model. Password authentication remains authoritative and available.
- Never train or alter model weights from sign-in attempts. Training data must be separately consented, correctly labelled, reviewed, versioned, and separated from evaluation data. Freeze a model version for each evaluation run so results are reproducible.
- A caretaker's face is bound to the caretaker account. Patient access still comes only from the backend's existing patient grant and scope checks; a face match must never create or widen a patient grant.

## Required evaluation before any access decision

Use a documented consented dataset with independent train, validation, and test partitions. Evaluate false-match and false-non-match rates at a fixed threshold; report results by relevant demographic and capture-condition groups, including lighting, camera quality, pose, age range, and assistive-device effects. Evaluate PAD against printed photos, screen replays, masks, and camera-injection attempts. Include rate limits, lockouts, replay resistance, model rollback, deletion, account recovery, and an accessible non-biometric alternative. Do not claim production readiness from a small demo set or synthetic faces.

NIST SP 800-63B-4 requires PAD for facial recognition, treats biometric data as sensitive, requires an alternative authentication method, and describes biometric use as part of multi-factor authentication. Its performance targets are evaluation requirements, not claims we can make without measured evidence. Ghana-specific privacy and health-data requirements, consent wording, lawful basis, retention, hosting location, and processor terms must be reviewed before real enrollment.

## Build sequence

1. Write and review data-protection, consent, retention, deletion, and threat-model decisions.
2. Build consented enrollment and deletion APIs, encrypted capture storage, and caretaker identity binding. Keep capture disabled unless encryption and consent are configured; keep verification disabled until an evaluated model is configured.
3. Select and document an independently evaluated face representation and PAD method; define model license, device support, data residency, and operating costs.
4. Build offline training/evaluation tooling that cannot promote a model automatically. Record model/data versions and reproducible metrics.
5. Continue the research-only mobile capture and shadow-evaluation screen. No access tokens depend on its result.
6. Conduct independent security, privacy, and performance review before considering a separate approval to use verification as an authentication factor.

## Non-goals for the initial prototype

The initial prototype will not use vitals to decide identity, diagnose a person, dispatch care, train itself during sign-in, or block password access. Health measurements and face verification answer different questions and must remain separate systems.
