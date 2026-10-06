# BhuDrishti AI frontend

This React/TypeScript/Vite client presents the functional document workflow backed by FastAPI. It signs in named users, uploads actual files, polls persisted processing state, and reads extraction, validation, review, audit, analytics, and GIS results from `/api/v1`. UI transitions never substitute for backend processing.

## Start

Apply backend migrations and create the first administrator as described in the [project README](../README.md). Start FastAPI on `http://127.0.0.1:8000`. For this existing workspace, run in a separate PowerShell terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\frontend'
& 'C:\Program Files\nodejs\npm.cmd' run dev
```

For a new installation, run `npm ci` first. Public settings live in the repository-root `.env`, loaded through Vite's `envDir`:

```dotenv
VITE_APP_URL=http://localhost:5173
VITE_API_BASE_URL=/api/v1
API_PROXY_TARGET=http://127.0.0.1:8000
```

Vite derives its hostname and port from `VITE_APP_URL` and uses `strictPort`, so an occupied port stops startup rather than changing the emailed origin. The backend reads the same URL to build verification and reset links. Restart both services after changing it. Keep secrets in `backend/.env`; never put SMTP credentials into `VITE_*` settings. The frontend uses relative `/api/v1` requests, proxied to the backend, so it needs no separate cross-origin API URL.

Open `http://localhost:5173/#/signup` to register with a requested role, verify the emailed link, then sign in. Revenue Officer, Verifier, and Auditor registrations use the server-assigned role after verification. An Administrator selection creates a pending request with restricted Auditor access until an existing administrator approves it. There are no built-in demo users or passwords. The Vite `/api` proxy targets the local backend; the repository-root `.env.example` documents public URL and API overrides. Sessions are held in browser `sessionStorage`, checked with `/auth/me`, and revoked with `/auth/logout` on sign-out.

If the frontend is stopped, the browser cannot render an application error page for an emailed link. Start Vite using the command above, keep the terminal open, then reopen the link. If Vite is running but the backend is unavailable, the verification page reports the failed request. See [Local email verification](../docs/LOCAL_EMAIL_VERIFICATION.md) for recovery and complete test steps.

For isolated QA on port 5174, set `VITE_APP_URL=http://localhost:5174` in both the QA backend and frontend processes. Set `API_PROXY_TARGET=http://127.0.0.1:8001` and `VITE_QA_WORKSPACE=true` in the frontend process, and point the QA backend at its separate database/storage. Do not start only the QA frontend against the normal database; use the exact two-terminal instructions in the linked guide.

## Routes

- `#/dashboard` — operational metrics and activity from persisted records.
- `#/documents` — upload, document list, page viewer, and evidence-linked extracted fields.
- `#/processing?id=<documentId>` — backend stage and error status.
- `#/validation?id=<documentId>` — actual field, record, reference, score, and routing results.
- `#/review` and `#/review/{recordId}` — human queue, source evidence, corrections, resolutions, and decisions.
- `#/records` and `#/records/{recordId}` — canonical record and verification history.
- `#/gis`, `#/analytics`, `#/audit`, and `#/settings` — persisted map index, metrics, attributed events, account and provider status.

An administrator can add accounts and review Administrator access requests in Settings. Role-based navigation follows the authenticated server role; the backend independently enforces every protected action. GIS displays only sourced parcel geometry, not invented boundaries.

Authorized officers can stage multiple PDF or image files by browsing or dropping them, inspect each file, then confirm the batch. Each file is uploaded through the existing endpoint and starts its own persisted processing job. The activity queue shows actual transfer progress and job status; the document list keeps the current selection while other jobs run. A failed file or job can be retried independently. Completed documents show the latest persisted officer review status, when one exists. The ten presentation tiles map to eight stored backend stages; the three validation tiles share one validation stage and do not run on independent timers.

For text embedded in a PDF, extraction confidence is displayed as **unavailable** because no OCR probability was measured. A scanned image can show Tesseract confidence when the installed language model returns it. Field evidence links to source page text and coordinates. Missing fields stay visible for officer review.

## Checks and structure

```powershell
npm run generate:api
npm test
npm run lint
npm run typecheck
npm run build
```

`src/features/auth/` owns session handling; `src/features/live/` owns upload, processing, viewer, extraction, and validation; `src/features/review/` owns officer work; `src/features/phase4/` owns records, audit, and GIS; `src/features/dashboard/` and `src/features/analytics/` read operational data. `src/types/api.generated.ts` is generated from the backend OpenAPI contract. The frontend tests cover backend stage rendering, score precision, completed-processing refresh, and review links; browser workflow checks cover the integrated product.
