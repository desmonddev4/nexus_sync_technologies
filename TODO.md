# Nexus Sync Build Checklist

Status reviewed: 2026-10-19

`[x]` implemented and covered by tests; `[ ]` not yet complete. A checked software task does not imply clinical validation or real-world provider approval.

## Current Product Direction

- [x] Django REST Framework backend, built as separate domain apps.
- [x] Custom React + TypeScript web admin dashboard is the current operator UI direction.
- [x] Keep every dashboard page and reusable component in its own file/directory, with its own CSS file.
- [x] Treat React Native as a separate later patient/responder client; do not merge it into the web admin bundle.
- [x] Keep simulator data clearly distinguished from live provider/device data.
- [x] Normalize configured frontend API URLs to include `/api/v1`; verified the production token endpoint's preflight for the configured Vercel origin.
- [x] Add a read-only Leaflet operations map with active incident snapshots, verified directory markers when coordinates exist, eligible nearby vehicles, explicit simulation status, and server-calculated route/ETA geometry.
- [x] Add clinician/superuser measurement-quality queue and one-way review API, audit records, rule evaluation on acceptance, and dashboard review workflow.
- [x] Add an authenticated device simulator for heartbeat, measurement, location, and idempotent SOS events, with local retry queue support.
- [x] Allow active simulator/wearable device credentials to create idempotent SOS incidents with patient and source derived by the backend.
- [x] Add controlled patient enrollment, account/role provisioning, coordinator-only device registry and credential lifecycle, and coordinator-managed provider/facility verification with recorded sources.
- [x] Add safe simulated vehicle registration, defaulting vehicles to unavailable and keeping live fleet-feed authorization as a separate approval gate.
- [x] Add a configurable ESP32 firmware scaffold for authenticated HTTPS, a durable idempotent event queue, periodic heartbeat, and a standalone manual SOS input; board, sensor, battery, and secure-update validation remain outstanding.

## Specification Roadmap: Remaining Pilot Deliverables

The sections below track the specification's end-to-end milestone. Checked items are implemented in software; they do not imply hardware validation, clinical approval, provider authorization, or a supervised pilot.

### Emergency workflow and operational map

- [x] Backend supports SOS incidents, operator acknowledgement, responder assignment, route estimates, operator-recorded dispatch request/confirmation, status transitions, and incident history.
- [x] Seed and label a simulated UPSA-area provider/vehicle; require explicit opt-in to include simulated vehicles.
- [x] Build an interactive operations map showing incident/patient, provider/facility, and eligible vehicle markers with simulation labels.
- [x] Show patient/vehicle location accuracy and freshness on the map; visibly distinguish missing, stale, simulated, and authorized live locations.
- [x] Display the selected vehicle's route and ETA in the map workflow, with clear labeling that route calculation is not dispatch confirmation.
- [ ] Verify UPSA/Madina/East Legon provider directory records, service coverage, facility suitability, contact sources, and last-verification dates directly with providers.
- [ ] Complete and record the full simulated SOS acceptance path against a running deployment, including contact delivery-state verification, operator action, response tracking, resolution, and closure.

### Device, risk analysis, and authorized integrations

- [x] Implement backend measurement/location ingestion, device authentication and revocation, deduplication, and a disabled-by-default, explainable monitoring-rules framework.
- [x] Create the device/simulator client that exercises authenticated heartbeat, measurement, location, SOS, retry queue, and reconnection workflows against the API.
- [ ] Build the firmware on the selected ESP32 board and validate wearable sensors; preserve a dependable manual SOS path independent of AI or rules.
- [ ] Add and evaluate fall-candidate detection; do not treat a candidate fall as a diagnosis.
- [ ] Add AI-assisted trend analysis only after governed, appropriately labelled data and clinical evaluation are available; report uncertainty and require human review.
- [ ] Obtain provider authorization and document an approved fleet/status integration and dispatch-confirmation procedure before using live vehicle data.
- [ ] Complete provider-approved notification configuration and controlled delivery tests; distinguish submission, delivery, acknowledgement, and unknown outcomes.

### Safety, privacy, testing, and pilot readiness

- [x] Backend and dashboard communicate simulation and dispatch-confirmation limits; monitoring rules remain disabled by default and require authorized review.
- [x] Add local automated coverage for simulation, failure-mode, role-permission, missing/stale-location, threshold-miss, notification-state, and lifecycle acceptance scenarios.
- [ ] Repeat the critical simulation, failure-mode, role-permission, and end-to-end acceptance scenarios against a production-like environment.
- [ ] Complete Ghana legal/privacy and health/medical-device review, pilot consent and data-sharing procedures, retention decisions, and breach response before real participant use.
- [ ] Obtain clinical review of intended use, measurement quality, thresholds, escalation rules, and fall-detection protocol; validate sensors against appropriate references.
- [ ] Verify production backups and restoration, operational monitoring/alerts, secret restrictions, and incident-response procedures.
- [ ] Obtain provider sign-off and conduct a supervised pilot only after all applicable acceptance, safety, security, and operational gates pass.

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
- [x] Backend system checks and migrations; 148 automated tests pass (verified with the complete backend test suite on 2026-10-19).

## Immediate Priority: Custom Admin Dashboard

### Foundation and Authentication

- [x] Replace the Vite demo screen with the actual admin application entry point.
- [x] Add client identity endpoint `GET /api/v1/auth/me/` returning username, role, and operations-access status.
- [x] Build login, logout, session restore/re-authentication behavior, and protected routes.
- [x] Store authentication tokens using an appropriate secure web storage strategy; never expose provider API keys in the browser.
- [x] Add role-based navigation and deny access to non-operations roles.
- [x] Update the root README to reflect the custom web admin and separate future React Native app; do not use Django admin as the operational interface.

### Required Pages

- [x] Operations dashboard: active incidents, unacknowledged alerts, location freshness, and recent incident queue visibility.
- [x] Incident queue: priority, trigger, patient identifier, age, status, and clear stale/simulation indicators.
- [x] Incident detail: immutable location snapshot, event timeline, notification status, assignment, route/ETA, and operator-reported dispatch confirmation.
- [x] Patient directory and patient detail: profile, emergency contacts, consent, device health, recent readings, location history, and incidents.
- [x] Patient detail baseline page: patient profile and linked incident history with incident drill-down.
- [x] Patient detail consent/contact extension: emergency contacts and consent history surfaced from API and rendered in dashboard.
- [x] Patient detail monitoring extension: recent measurements and location history surfaced from API and rendered in dashboard.
- [x] Patient detail device-health extension: assigned devices, status, battery, last-seen freshness, and stale indicators surfaced from API and rendered in dashboard.
- [x] Monitoring/rule management: draft, clinician review, versioning, enable/disable, evaluation history, and evidence.
- [x] Emergency-services directory: provider/facility verification status and operational contact/directory context.
- [x] Fleet view: vehicle availability, source, freshness timestamp, and simulation marker.
- [x] Audit log viewer with filters for actor, action, resource, date, and outcome.
- [x] Account/role administration that replaces any dependency on Django admin for routine operations.
- [x] Add dashboard workflows for patient creation, device assignment/status and credential issue/revocation, and pending emergency-directory records with audited source-based verification.
- [x] Settings for escalation policy and authorized operational configuration.

### Dashboard Structure and Quality

- [x] Organize routes/pages under `src/pages/<PageName>/` with a page file and page-local CSS file.
- [x] Organize reusable UI under `src/components/<ComponentName>/` with a component file and component-local CSS file.
- [x] Keep API clients, types, auth, and navigation in separate modules.
- [x] Replace demo/mock content with backend API loading, error, empty, and permission-denied states.
- [x] Add responsive desktop/tablet layouts and verify text/table behavior at smaller widths.
- [x] Add frontend tests for login, access control, incident workflows, stale data, and simulated data labeling.
- [x] Run frontend lint, typecheck, production build, and unit/component tests.
- [x] Add and run local browser-based end-to-end tests for authentication, role denial, and dashboard navigation using controlled API fixtures.
- [ ] Run browser-based end-to-end tests against a production-like deployment and verify the full API lifecycle there.

## Backend Work Remaining

- [x] Add `/api/v1/auth/me/` for custom dashboard identity and operations-access checks.
- [x] Replace monitoring-rule management through Django admin with role-protected APIs used by the custom dashboard; evaluated rule versions are immutable.
- [x] Add a controlled API for measurement-quality review and expose it in the dashboard; enforce clinician/superuser permissions and audit one-way decisions.
- [x] Add role-protected patient, device-registry, and emergency-directory provisioning APIs; require explicit verification sources and prevent directory verification from granting fleet-feed authorization.
- [x] Require explicit account roles at creation and when provisioning legacy accounts without profiles; prevent implicit coordinator-role assignment and test partial patient-link updates.
- [x] Expand audit coverage to authentication failures, user/role changes, rule changes, device credential issuance/revocation, route requests, exports, and administrative actions.
- [x] Add audit-log retention, export, access-control, and backup policy.
- [x] Add handling/recovery for notifications left in `processing`, plus operational monitoring for `submission_unknown` outcomes.
- [x] Add retry/escalation scheduling and a documented operator workflow for failed/unconfirmed notifications.
- [x] Add provider integration adapters only after a provider authorizes an API or fleet feed; preserve explicit operator confirmation meanwhile.
- [x] Add data-retention/deletion workflows and access-request procedures for patient data.
- [x] Lock incident and vehicle rows for responder assignment; enforce one current vehicle per incident at the database layer and test reassignment/duplicate-link rejection.
- [ ] Exercise concurrent duplicate-device requests and competing vehicle assignment against PostgreSQL under production-like conditions.

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

- [ ] Run and record manual SOS end-to-end against a test deployment: dashboard, notification delivery-state checks, acknowledgement, assignment, route, operator-recorded confirmation, arrival, resolution, and closure.
- [x] Automated local tests verify duplicate SOS/measurement/device retries do not duplicate records; repeat this acceptance check against a production-like deployment.
- [x] Local API/UI tests verify missing and stale patient GPS remain visibly missing/stale and never substitute invented coordinates.
- [x] Add local simulator tests for offline queue retention, successful retry preserving event IDs, and SOS confirmation guard.
- [ ] Run the simulator against a test deployment to verify offline queue flush, reconnection, and credential revocation behavior.
- [x] Local backend/frontend tests cover notification rejection, timeout/unknown outcome, callback replay, out-of-order callbacks, delivery reconciliation, and operator-visible delivery states.
- [x] Local tests cover unavailable, stale, unsuitable, unverified, and simulated vehicle selection behavior.
- [x] Local tests cover rule quality rejection, stale reading, threshold miss, consecutive-reading trigger, simulation opt-in, and active-incident linking.
- [x] Local tests cover patient, clinician, emergency coordinator, provider responder, and superuser permission cases.
- [x] Local workflow/UI tests verify no message is presented as delivered and no ambulance as dispatched without corresponding evidence.
- [ ] Repeat notification, vehicle-selection, rules, permissions, and evidence checks against a production-like deployment.
- [x] Add one local SOS lifecycle API acceptance test covering consent-gated queueing, acknowledgement, simulated assignment, route estimate, operator-reported confirmation, and closure without claiming live delivery or dispatch.
- [x] Add an incident list/action role matrix for patient, clinician, coordinator, provider responder, emergency contact, and superuser.

## Clinical, Privacy, and Safety Gates

- [ ] Obtain Ghana legal/privacy review for data protection, health-sector requirements, and medical-device implications before enrolling real participants.
- [ ] Finalize pilot consent, purpose limitation, data sharing, retention/deletion, participant access, and breach-response procedures.
- [ ] Have clinical advisers approve intended use, measurement quality criteria, thresholds, escalation rules, and human-review protocol.
- [ ] Validate sensors against appropriate references and document accuracy, limitations, motion artifacts, and failure behavior.
- [ ] Evaluate fall-detection false positives/negatives before real use; preserve manual SOS independently of AI/rules.
- [ ] Do not label measurements as diagnoses; do not use an unvalidated model to dispatch or influence care.
- [ ] Complete supervised simulation acceptance tests and provider sign-off before a real-patient pilot.

## Hardware and Later Mobile Work

- [ ] Build and test the firmware on the selected ESP32 board for SOS, measurement timestamps, device identity, calibrated battery reporting, and connectivity.
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

## Local software work we can advance

- [ ] Add PostgreSQL concurrency acceptance coverage for duplicate device registration and competing vehicle assignment (coverage added; PostgreSQL execution pending).
- [x] Build the patient/caretaker React Native app with live backend sign-in, scoped patient records, and optional device biometric unlock.
- [x] Add patient-controlled caretaker access grants with explicit scopes, phone verification matching, audit logging, and revocation.
- [x] Add phone location to SOS and show real notification delivery/acknowledgement status in the mobile app (live SMS delivery still depends on provider configuration).
- [ ] Add a repeatable production-like acceptance runbook and evidence template for the SOS lifecycle, simulator retry/revocation, notifications, and permissions.
- [ ] Run production-like browser and backend acceptance against a configured deployment; record results and unresolved failures.
- [ ] Define service targets and operational monitoring checks for API availability, ingestion, notification processing, callbacks, and stale locations.

Provider authorization, provider record verification, clinical/legal review, sensor validation, live delivery tests, and supervised pilot sign-off require external participants and stay as separate gates.
