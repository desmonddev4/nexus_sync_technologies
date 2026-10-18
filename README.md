# Nexus Sync

Nexus Sync is a health-monitoring and emergency-coordination platform. Development starts with a dependable Django backend and simulated data. Hardware, provider integrations, and clinical use are separate milestones.

## Project layout

```text
backend/
	apps/
		accounts/            # Authentication, roles, and permissions
		core/                # Shared infrastructure and service health API
		devices/             # Device registration and credentials
		patients/             # Patient profiles, contacts, and consent
		monitoring/           # Measurements, locations, and safety rules
		incidents/            # Emergency workflow and incident history
		emergency_services/   # Verified providers, facilities, and vehicles
		notifications/        # Delivery, retries, and escalation
		audit/                # Sensitive access and change history
	config/
		settings/             # Shared, development, and production settings
	manage.py
	requirements.txt
frontend/
	admin/
		src/
			api/                # API clients for backend operations endpoints
			auth/               # Login/session context and route protection
			components/         # Reusable UI components, each in its own directory
			pages/              # Dashboard pages, each in its own directory
			types/              # Shared frontend API/data contracts
```

Each backend domain is a separate Django app. Backend models, serializers, services, API views, and tests belong with the domain that owns them; shared behavior belongs in `apps/core` only when it is genuinely cross-domain.

The active operator interface is a custom React + TypeScript web dashboard in `frontend/admin`. Keep each page and reusable component in its own file/directory with page-local or component-local CSS.

React Native remains a separate later phase for patient/responder mobile clients after web dashboard workflows and API contracts stabilize.

## Frontend admin setup
```bash
cd frontend/admin
npm install
npm run dev
```

Set `VITE_API_BASE_URL` if your API is not served from `/api/v1`.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The development settings use SQLite by default so the API can be started locally without external services. To use PostgreSQL, set `DB_ENGINE=postgresql` and configure the `DB_*` values in `backend/.env`. Never commit `.env` or real credentials.

Create user accounts and assign their `AccountProfile` roles through trusted admin provisioning. There is no public user-registration endpoint.

## Deployment on Render and Vercel

Backend production runs from `backend/config/wsgi.py`, which defaults to the production settings module. A Render blueprint is available at `render.yaml` for the backend service and links `DATABASE_URL` to the existing Render Postgres resource named `nexus_sync_db`.

Use these Render settings for the Django web service:

- build command: `pip install -r backend/requirements.txt && cd backend && python manage.py collectstatic --noinput --settings=config.settings.base`
- start command: `cd backend && python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- environment variables: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DB_ENGINE=postgresql`, and `DATABASE_URL` linked to Render Postgres
- optional frontend origin allowlist: `CORS_ALLOWED_ORIGINS=https://YOUR_FRONTEND_DOMAIN`

For the Vercel frontend, set the project's Root Directory to `frontend`, because the latest build log showed Vercel looking for `/frontend/package.json`. The Vercel config there installs and builds from `admin/`. Set `VITE_API_BASE_URL` to the deployed backend base URL, for example `https://YOUR_RENDER_BACKEND/api/v1`. If you do not set it, the app will use a same-origin `/api/v1` path, which only works when the frontend is served from the same host or through a proxy.

Register a device in Django admin, assign it to a patient, and set it to active before issuing credentials. The credential is printed once and stored on the server only as a digest:

```bash
python manage.py issue_device_credential NS-DEVICE-001
python manage.py issue_device_credential NS-DEVICE-001 --revoke
```

## SasuSync SMS setup

After the account and sender ID are approved, configure these values in the untracked `backend/.env` file:

- `SASUSYNC_API_KEY`
- `SASUSYNC_SENDER_ID` (must be approved on the SasuSync account)
- `SASUSYNC_BASE_URL` (defaults to `https://sms.sasusync.com`)
- `SASUSYNC_WEBHOOK_SECRET` (the signing secret issued when enabling a webhook for the API key)

In the SasuSync API-key settings, configure the webhook URL as `https://YOUR_PUBLIC_API_HOST/api/v1/integrations/sasusync/webhook/`. The endpoint validates `X-Webhook-Signature` over the raw request body, ignores duplicate events, and applies only events newer than the most recently recorded provider timestamp.

`python manage.py process_notifications --sandbox --limit 50` uses SasuSync's free sandbox endpoint; it requires the API key and an approved sender ID, but it does not deliver messages. Sandbox submissions are stored separately and never count as real delivery. `python manage.py process_notifications --sasusync --limit 50` sends real SMS and can incur charges. A send response records the provider task ID and `submitted` status. Signed webhooks update delivery status; `python manage.py reconcile_sasusync_status --limit 50` polls submitted live task IDs if a webhook is missed. Transient HTTP errors use bounded backoff. Network timeouts are held as ambiguous and are never blindly resent. Do not run live sending against test patient data.

### Operator workflow for failed or unconfirmed notifications

1. Run `python manage.py process_notifications --sasusync --limit 50` on schedule.
2. The command automatically recovers notifications stuck in `processing` beyond policy timeout and marks them `submission_unknown`.
3. The command schedules retries for `failed` and `submission_unknown` outcomes using the escalation policy retry interval and max attempts.
4. Run `python manage.py reconcile_sasusync_status --limit 50` to reconcile submitted live task IDs when callbacks are delayed or missing.
5. If `open submission_unknown` remains non-zero after retries, treat as unconfirmed delivery and perform manual contact escalation per your emergency SOP.

## Current API

Application endpoints require authentication except health and token login. The SasuSync webhook uses its raw-body HMAC signature. Patient and incident data are restricted by account role and patient association.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/auth/token/` | Obtain a user token |
| `GET` | `/api/v1/auth/me/` | Return current username, role, and operations-access flag |
| `GET` | `/api/v1/health/` | JSON service health |
| `POST` | `/api/v1/devices/heartbeat/` | Update device health using device credentials |
| `GET`, `POST` | `/api/v1/patients/` | List or create patients |
| `GET`, `PATCH`, `PUT` | `/api/v1/patients/{id}/` | Read or update a patient |
| `GET` | `/api/v1/providers/` | List verified emergency providers for operations staff |
| `GET` | `/api/v1/facilities/` | List verified healthcare facilities for operations staff |
| `GET` | `/api/v1/vehicles/` | List vehicles belonging to verified providers |
| `GET` | `/api/v1/vehicles/nearby/?latitude={lat}&longitude={lon}` | List fresh, available live vehicles nearest to a location |
| `POST` | `/api/v1/measurements/` | Ingest one sourced measurement |
| `GET` | `/api/v1/measurements/review/` | List measurement-quality review queue (clinician/superuser only) |
| `POST` | `/api/v1/measurements/{id}/review/` | Record one immutable acceptable/questionable quality decision (clinician/superuser only) |
| `POST` | `/api/v1/locations/` | Ingest one timestamped location |
| `POST` | `/api/v1/incidents/sos/` | Create an idempotent SOS incident; device-authenticated calls derive patient and trigger source from device credentials |
| `GET` | `/api/v1/incidents/` | List visible incidents |
| `POST` | `/api/v1/incidents/{id}/acknowledge/` | Acknowledge as authorized staff |
| `POST` | `/api/v1/incidents/{id}/assign-responder/` | Assign an eligible vehicle; simulated vehicles require explicit opt-in |
| `POST` | `/api/v1/incidents/{id}/route/` | Calculate and save a traffic-aware route/ETA for the assigned vehicle |
| `POST` | `/api/v1/incidents/{id}/record-dispatch-request/` | Record an operator request; does not contact a provider |
| `POST` | `/api/v1/incidents/{id}/record-dispatch-confirmation/` | Record operator-reported confirmation and reference |
| `POST` | `/api/v1/incidents/{id}/status/` | Record allowed en-route, arrival, resolution, or closure transitions |
| `GET` | `/api/v1/incidents/{id}/notifications/` | View contact notification status as staff |
| `GET` | `/api/v1/incidents/{id}/events/` | View audit timeline and monitoring-rule evidence as staff |
| `POST` | `/api/v1/integrations/sasusync/webhook/` | Signed SasuSync delivery callback |

## Google Routes setup

Enable Google Routes API and billing for the Google Cloud project, restrict the key to the Routes API and your backend environment, then set `GOOGLE_MAPS_API_KEY` in the untracked `backend/.env`. Route calculation requires an assigned vehicle and fresh patient/vehicle coordinates; it refuses stale locations and returns a configuration error if the key is absent. Each calculation is retained as an incident route estimate. Simulated routes carry `is_simulated=true` and are not evidence of an actual ambulance route or dispatch.

## Monitoring rules

Monitoring rules are configured through the role-protected dashboard APIs. No clinical thresholds are seeded. Rules are disabled by default and can be enabled only by a clinician or superuser, which records the reviewer and review time. Measurements begin as `unreviewed`; clinicians and superusers use the dashboard's Measurement review page to record a one-way quality decision before an acceptable reading can trigger a rule. Readings older than five minutes are skipped, and simulated readings require explicit opt-in on the rule. Consecutive-reading count and lookback window are configurable. Evaluated rule definitions are immutable; create a new version to change an evaluated rule. Each evaluation records its rule version and reading evidence; repeat triggers link to the active incident rather than creating an incident for every reading. Authorized staff can inspect history at `/api/v1/incidents/{id}/events/`. These rules are alerts, not diagnoses.

## Audit logs

Authorized admins can review patient and incident access, object-level denied access attempts, patient changes, SOS creation/retries, and measurement/location ingestion in Django admin under Audit logs. Entries record the actor when authenticated, action, resource identifier, request method, request ID, client IP, and outcome. Audit metadata intentionally excludes patient names, medical notes, coordinates, measurement values, message bodies, and credentials. Incident timeline events remain separately available at `/api/v1/incidents/{id}/events/`.

Emergency coordinators and superusers can export filtered logs at `GET /api/v1/audit/logs/export/` as CSV (subject to `AUDIT_EXPORT_MAX_ROWS`). Clinicians can view logs but cannot export.

Run `python manage.py prune_audit_logs --dry-run` to preview retention cleanup and `python manage.py prune_audit_logs` to delete rows older than `AUDIT_RETENTION_DAYS` (or override with `--days N`). Include this command in your scheduled backup/maintenance runbook before backup snapshots.

Device-originated monitoring data requires an active, patient-assigned device credential. The backend derives the patient, device, and source from that credential rather than trusting those fields in the request. Credentials can be rotated by issuing again and revoked with `--revoke`. Simulator, manual, and validated-external sources remain explicit in stored measurement records. SOS creates queued notification records only for verified contacts when the latest emergency-contact consent is granted.

Seed the local UPSA demo fleet with `python manage.py seed_upsa_simulation`. The seeded provider and vehicle are marked simulation-only; simulated vehicles appear in nearby results only when `include_simulated=true` is explicitly requested. Their positions are not real ambulance locations and do not establish dispatch availability.

Verified providers now require explicit fleet-feed authorization before provider-sourced live vehicles can appear in nearby/assignment workflows. This prevents accidental operational use of unapproved provider feeds. Dispatch confirmation remains operator-recorded evidence (`record-dispatch-confirmation`) and is not auto-confirmed from provider integrations.

To exercise the outbox against SasuSync without delivering a real message, configure the approved API key and sender ID, then run `python manage.py process_notifications --sandbox`.

Run backend checks and tests from `backend/`:

```bash
python manage.py check
python manage.py test apps.core apps.accounts apps.patients apps.devices apps.incidents apps.monitoring apps.notifications apps.emergency_services apps.audit
```

The API returns JSON only. The domain apps are being built incrementally, with backend behavior and tests supporting the custom web operations dashboard.

## Safety and pilot boundary

Initial development uses simulator-generated data. A successful API response, alert, or provider listing is not evidence that an emergency contact received a message or that an ambulance was dispatched. Live health data, patient enrollment, clinical decision support, and real dispatch require appropriate consent, security controls, provider authorization, and supervised validation.

## Authenticated device simulator

A Python simulator is available at [simulator/device_simulator.py](simulator/device_simulator.py). It exercises device-authenticated heartbeat, measurement, location, and SOS endpoints; event IDs make measurement/location/SOS retries idempotent. Failed requests are queued in an ignored local JSONL file and can be retried with `--flush-queue`. The queue can contain precise test coordinates and must remain private.

Set `NEXUS_API_BASE` (defaults to local `http://127.0.0.1:8000/api/v1`), `NEXUS_DEVICE_ID`, and `NEXUS_DEVICE_SECRET` in the shell environment. Obtain a simulator device credential through the trusted credential-issuance command after creating and assigning a simulator device:

```powershell
cd backend
python manage.py issue_device_credential NS-SIM-001
```

Then run non-incident test events from the repository root:

```powershell
python simulator/device_simulator.py --event heartbeat
python simulator/device_simulator.py --event measurement
python simulator/device_simulator.py --event location
```

SOS creates an incident and queues notifications for eligible contacts; it is not a live dispatch request. Only when intentionally testing an incident, run `python simulator/device_simulator.py --event sos --confirm-sos`. `--event all` also requires `--confirm-sos` because it includes SOS. Use only test accounts/data. Device credentials are printed once by the issuance command; do not paste them in chat, commit them, or put them in shell history. Prefer secure environment injection and rotate/revoke credentials after use.

## Operations map and measurement review

The admin includes an authenticated operations map with incident-time location snapshots, verified facilities, optional verified provider station coordinates, and eligible nearby vehicle positions. OpenStreetMap tiles are loaded by the browser and require network access; attribution is displayed on the map. Simulated vehicles are explicitly labeled and toggleable. The map never geocodes provider addresses or invents missing coordinates. Route geometry and ETA are requested from the server and remain estimates, not dispatch confirmation. Live fleet positions require provider authorization and a fresh eligible vehicle feed.

Clinicians and superusers can review unreviewed measurement quality in the dashboard. Accepting a reading may evaluate enabled monitoring rules; each measurement review is one-way/immutable and audit logged. This workflow is a quality gate, not clinical diagnosis or approval of thresholds.