# Nexus Sync Build Checklist

Status reviewed: 2026-10-17

`[x]` implemented and covered by tests; `[ ]` not yet complete. A checked software task does not imply clinical validation or real-world provider approval.

## Current Product Direction

- [x] Django REST Framework backend, built as separate domain apps.
- [x] Custom React + TypeScript web admin dashboard is the current operator UI direction.
- [ ] Keep every dashboard page and reusable component in its own file/directory, with its own CSS file.
- [ ] Treat React Native as a separate later patient/responder client; do not merge it into the web admin bundle.
- [x] Keep simulator data clearly distinguished from live provider/device data.

## Implemented Backend Foundation

- [x] Django project, API versioning, development/production settings, environment-based secrets, SQLite development database, and PostgreSQL configuration.
- [x] Domain app boundaries for accounts, audit, devices, emergency services, incidents, monitoring, notifications, patients, and core.
- [x] User token authentication and role profiles.
- [x] Patient records, emergency contacts, consent history, and role-scoped patient access.
- [x] UUID-based device registry, hashed/revocable device credentials, and device heartbeat endpoint.
- [x] Measurement and patient-location ingestion with validation, source attribution, and event deduplication.
- [x] Explicit patient and device permissions on monitoring ingestion.
- [x] SOS incident creation, idempotency, incident state transitions, event history, and incident-time location snapshots.
- [x] Consent- and verification-gated notification outbox with SasuSync sandbox/live adapter, signed webhooks, status polling, and operator-visible delivery states.
- [x] Rule evaluation framework with disabled-by-default, clinician-reviewed rules, quality/freshness/simulation gates, consecutive-reading support, and rule evidence on incidents.
- [x] Provider, facility, and vehicle directory models; freshness-aware nearby lookup; explicit UPSA simulation seed.
- [x] Responder assignment, operator-recorded dispatch request/confirmation, vehicle release, and simulation labels.
- [x] Google Routes adapter, stale-coordinate rejection, route estimate history, and simulated-route labeling.
- [x] Metadata-only audit logging for patient/incident access and measurement/location ingestion, including object-level denials.
- [x] Backend system checks, migrations, and 80 automated tests.

## Immediate Priority: Custom Admin Dashboard

### Foundation and Authentication

- [ ] Replace the Vite demo screen with the actual admin application entry point.
- [ ] Add client identity endpoint such as `GET /api/v1/auth/me/` returning user ID, role, and account status.
- [ ] Build login, logout, token refresh/re-authentication behavior, and protected routes.
- [ ] Store authentication tokens using an appropriate secure web storage strategy; never expose provider API keys in the browser.
- [ ] Add role-based navigation and deny access to non-operations roles.
- [ ] Update the root README to reflect the custom web admin and separate future React Native app; do not use Django admin as the operational interface.

### Required Pages

- [ ] Operations dashboard: active incidents, unacknowledged alerts, device/location freshness, notification failures, and recent events.
- [ ] Incident queue: priority, trigger, patient identifier, age, status, and clear stale/simulation indicators.
- [ ] Incident detail: immutable location snapshot, event timeline, relevant measurements, consent-aware notification status, assignment, route/ETA, and operator-reported dispatch confirmation.
- [ ] Patient directory and patient detail: profile, emergency contacts, consent, device health, recent readings, location history, and incidents.
- [ ] Monitoring/rule management: draft, clinician review, versioning, enable/disable, evaluation history, and evidence.
- [ ] Emergency-services directory: provider/facility verification, contact type, source, and last-verified date.
- [ ] Fleet view: vehicle availability, source, freshness, stale marker, simulation marker, and nearby filter.
- [ ] Audit log viewer with filters for actor, action, resource, date, and outcome.
- [ ] Account/role administration that replaces any dependency on Django admin for routine operations.
- [ ] Settings for escalation policy and authorized operational configuration.

### Dashboard Structure and Quality

- [ ] Organize routes/pages under `src/pages/<PageName>/` with a page file and page-local CSS file.
- [ ] Organize reusable UI under `src/components/<ComponentName>/` with a component file and component-local CSS file.
- [ ] Keep API clients, types, auth, navigation, and shared design tokens in separate modules.
- [ ] Replace demo/mock content with backend API loading, error, empty, and permission-denied states.
- [ ] Add responsive desktop/tablet layouts and verify text/table behavior at smaller widths.
- [ ] Add frontend tests for login, access control, incident workflows, stale data, and simulated data labeling.
- [ ] Run lint, typecheck, production build, and browser-based end-to-end checks.

## Backend Work Remaining

- [ ] Add `/api/v1/auth/me/` and any required account lifecycle APIs for the custom dashboard.
- [ ] Replace rule management and quality review through Django admin with role-protected APIs used by the custom dashboard.
- [ ] Add a controlled API for review of measurement quality and rules; enforce clinician/superuser permissions and immutable evaluated versions.
- [ ] Expand audit coverage to authentication failures, user/role changes, rule changes, device credential issuance/revocation, route requests, exports, and administrative actions.
- [ ] Add audit-log retention, export, access-control, and backup policy.
- [ ] Add handling/recovery for notifications left in `processing`, plus operational monitoring for `submission_unknown` outcomes.
- [ ] Add retry/escalation scheduling and a documented operator workflow for failed/unconfirmed notifications.
- [ ] Add provider integration adapters only after a provider authorizes an API or fleet feed; preserve explicit operator confirmation meanwhile.
- [ ] Add data-retention/deletion workflows and access-request procedures for patient data.
- [ ] Review database transaction/locking behavior under concurrent duplicate device events and competing vehicle assignment.

## Integrations and Operational Readiness

- [ ] Configure SasuSync webhook URL and signing secret in the provider portal; test signed delivery callbacks against a public HTTPS deployment.
- [ ] Send a controlled SasuSync sandbox message after account/sender approval; verify queued status and delivery-state handling without claiming sandbox delivery.
- [ ] Conduct an explicitly approved live SMS test with a designated test recipient; record charges, latency, and delivery report.
- [ ] Configure a restricted server-side Google Routes API key and verify one controlled route request; review billing, quotas, and key restrictions.
- [ ] Verify real ambulance providers, dispatch numbers, coverage, operating hours, vehicle capability, and verification source directly with each provider.
- [ ] Agree on provider dispatch, acknowledgement, escalation, unavailability, and arrival procedures in writing.
- [ ] Obtain authorized live vehicle status/location access before displaying any real fleet positions.
- [ ] Set up HTTPS deployment, secret management, backups, restore tests, logs, alerts, and incident response procedures.
- [ ] Define service targets for API availability, ingestion, notification submission, callback processing, and stale-location visibility.

## Simulation and Acceptance Scenarios

- [ ] Manual SOS to dashboard, contact notification queue, acknowledgement, assignment, route, operator-recorded confirmation, arrival, resolution, and closure.
- [ ] Duplicate SOS/measurement/device retries produce no duplicate incidents or notifications.
- [ ] Missing and stale patient GPS remain visibly missing/stale; the system never substitutes invented coordinates.
- [ ] Offline device, reconnection, credential revocation, and queued-event behavior.
- [ ] Notification rejection, timeout/unknown outcome, callback replay, out-of-order callbacks, and delivery reconciliation.
- [ ] Unavailable, stale, unsuitable, unverified, and simulated vehicle selection behavior.
- [ ] Rule quality rejection, stale reading, threshold miss, consecutive-reading trigger, simulation opt-in, and active-incident linking.
- [ ] Permission tests for patient, clinician, emergency coordinator, provider responder, and superuser roles.
- [ ] Confirm no workflow implies a message was delivered or an ambulance dispatched without corresponding evidence.

## Clinical, Privacy, and Safety Gates

- [ ] Obtain Ghana legal/privacy review for data protection, health-sector requirements, and medical-device implications before enrolling real participants.
- [ ] Finalize pilot consent, purpose limitation, data sharing, retention/deletion, participant access, and breach-response procedures.
- [ ] Have clinical advisers approve intended use, measurement quality criteria, thresholds, escalation rules, and human-review protocol.
- [ ] Validate sensors against appropriate references and document accuracy, limitations, motion artifacts, and failure behavior.
- [ ] Evaluate fall-detection false positives/negatives before real use; preserve manual SOS independently of AI/rules.
- [ ] Do not label measurements as diagnoses; do not use an unvalidated model to dispatch or influence care.
- [ ] Complete supervised simulation acceptance tests and provider sign-off before a real-patient pilot.

## Hardware and Later Mobile Work

- [ ] Build and test ESP32 firmware for SOS, measurement timestamps, device identity, battery, and connectivity.
- [ ] Validate heart-rate/SpO2 sensor behavior and correctly distinguish skin temperature from body temperature.
- [ ] Integrate validated BP equipment if BP is required; never infer BP from a MAX30102.
- [ ] Add accelerometer fall-candidate detection and evaluate against normal activity/device drops.
- [ ] Add GPS/phone-assisted location, offline queueing, retry/idempotency, and secure firmware update procedure.
- [ ] Build the separate React Native patient/responder client after the web operations dashboard and API contracts stabilize.

## Pilot Exit Criteria

- [ ] All critical SOS and duplicate-event tests pass in a production-like environment.
- [ ] Notification failures, stale locations, simulated vehicles, and operator-reported confirmations are unambiguous in the UI.
- [ ] Access control, audit coverage, backups, restore, monitoring, and incident escalation are reviewed and demonstrated.
- [ ] Participating provider operational procedure and contact information are verified.
- [ ] Pilot results separate simulated measurements from supervised real-world results; no efficacy claim without evaluation evidence.
