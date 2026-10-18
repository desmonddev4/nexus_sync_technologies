# Nexus Sync Operations Admin

Custom React + TypeScript web dashboard for Nexus Sync emergency operations.

## Scope

This app is the operator-facing control room interface for:

- authenticated staff access
- live incident queue and incident detail workflows
- patient directory visibility (role-scoped by backend)
- provider, facility, and fleet directory visibility

This app does not expose provider API keys or run provider-side dispatch actions directly in the browser.

## Run locally

```bash
npm install
npm run dev
```

Default dev URL is provided by Vite.

## Build and quality checks

```bash
npm run lint
npm run build
npm run preview
```

## Environment

- `VITE_API_BASE_URL`: Backend API base URL (defaults to `/api/v1`)

Examples:

- local backend on same host through proxy/path routing: leave unset
- backend on another host: set `VITE_API_BASE_URL` to full API base

For Vercel, set `VITE_API_BASE_URL` to the deployed Render backend origin, for example `https://YOUR_RENDER_BACKEND/api/v1`. The dashboard uses token auth, so cross-origin requests require the backend CORS allowlist to include the Vercel origin.

## Implemented routes

- `/login`: staff sign-in
- `/`: operations overview
- `/incidents`: incident queue
- `/incidents/:incidentId`: incident detail workflow
- `/patients`: patient directory
- `/services`: providers, facilities, and fleet directory

## Auth and access model

- login uses backend token auth endpoint: `POST /api/v1/auth/token/`
- current user check uses: `GET /api/v1/auth/me/`
- protected routes require a valid token and `can_access_operations=true`
- token is stored in browser session storage with in-memory fallback

## Project structure

```text
src/
  api/          # fetch client and operations endpoints
  auth/         # auth context and hooks
  components/   # reusable UI components with local CSS
  pages/        # page modules with local CSS
  styles/       # global shared styles
  types/        # API response/data types
```

## Notes

- Simulator-sourced data is explicitly labeled in UI where available.
- Dispatch confirmation is operator-recorded evidence and should not be interpreted as direct provider system integration.
