# BhuDrishti AI

BhuDrishti AI is a functional local prototype for digitizing land-record documents. A named user uploads an actual PDF or image; the backend stores and processes its bytes, extracts source-linked fields, validates them, and calculates a quality score. Every operational processed record enters officer review, including records whose automated checks pass. Officer edits and decisions are persisted and audited. An approved record can receive a sourced parcel boundary through officer GeoJSON import; records without one remain explicitly unmapped. Explicit sample uploads and sources that identify themselves as synthetic are kept in a separate, read-only sample view. **The application does not determine legal ownership.**

## Current capabilities

| Area | Implementation |
| --- | --- |
| Identity | Email-verified signup, password recovery, named database accounts, revocable bearer sessions, and server-enforced Admin, Revenue Officer, Verifier, and Auditor permissions. |
| Documents | PDF, JPG, PNG, and TIFF upload with file validation, UUID-based storage, rendered previews, and persisted processing stages. |
| Text and OCR | PyMuPDF reads usable embedded PDF text first. Scanned pages and images use installed Tesseract language models after OpenCV preprocessing. `/api/v1/health` reports OCR capability and languages. |
| Extraction | Rules read inline labels and aligned table cells. Values, page numbers, source text, and value-cell bounding boxes are stored with the document and record. Missing values remain missing. |
| Validation | Field, record, and officer-approved local-reference checks feed configured 50%/30%/20% scoring. A missing reference is reported rather than counted as a passed comparison. |
| Human decision | Every processed record receives an officer case. Officers accept, correct, or reject fields; resolve issues; and approve, reject, or send a record back. A quality score never approves a record. The original extraction is retained separately from reviewed and final values. |
| Operations | Dashboard, analytics, categorized search, notifications, records, audit history, and Leaflet GIS read persisted operational backend results. GIS draws only imported, source-referenced WGS84 parcel boundaries; otherwise it reports geometry unavailable. A separate sample view retains test documents without mixing them into operational counts. |

Processing runs as a background task in the API process. The UI polls stored status; animation only displays those states. No scenario controls or generated answers drive the operational workflow.

## Run locally

For this existing Windows workspace, keep these two PowerShell terminals open.

Backend terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend'
& 'C:\Python313\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\frontend'
& 'C:\Program Files\nodejs\npm.cmd' run dev
```

The repository-root `.env` supplies the shared public configuration:

```dotenv
VITE_APP_URL=http://localhost:5173
VITE_API_BASE_URL=/api/v1
API_PROXY_TARGET=http://127.0.0.1:8000
```

Both services read `VITE_APP_URL`; Vite binds its configured hostname and port and fails if that port is occupied instead of silently moving to another port. Restart both services after changing the shared URL. SMTP credentials stay in `backend/.env`. Full startup, verification, and isolated QA instructions are in [Local email verification](docs/LOCAL_EMAIL_VERIFICATION.md).

For a **new installation**, copy the repository-root `.env.example` to `.env` if that file does not exist, then use the setup below once. It is not needed to restart this existing workspace.

Use Python 3.11+, Node.js 22.12+, and npm 10+. From the project root, start the backend in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m alembic upgrade head
python -m scripts.bootstrap_admin --email admin@example.local --name "Local Administrator"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Copy the example only for a new setup; preserve an existing `backend/.env`. Before testing signup or password recovery, fill the six SMTP settings in `backend/.env` from your provider's documentation as described below. The bootstrap command prompts securely for a password of at least 12 characters when it creates an administrator. Repeating it for the same email makes no changes and does not prompt. It creates **no default password**. In local development, create a second named administrator with `python -m scripts.bootstrap_admin --email another@example.local --name "Another Administrator" --allow-additional-admin`. Recover an existing administrator through the secure prompt with `python -m scripts.bootstrap_admin --email admin@example.local --reset-password --confirm-email admin@example.local`; this clears lockout and revokes existing sessions. Additional administrator bootstrap is restricted to development/test, and a reset outside those environments additionally requires `--allow-production-reset`. An administrator can also add named accounts in **Settings**. In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open [the local application](http://localhost:5173/#/dashboard). The Vite `/api` proxy points to `http://127.0.0.1:8000` by default; [FastAPI documentation](http://127.0.0.1:8000/docs) lists the API. Set `BHUDRISHTI_AUTH_SECRET` to a secret of at least 32 characters outside local development. Local development otherwise keeps a signing key in the database so sessions survive API restarts. The browser stores its current session in `sessionStorage` and revalidates it with `/auth/me`.

The repository-root `.env.example` lists public frontend settings; `backend/.env.example` lists backend settings. Useful backend overrides are `BHUDRISHTI_DATABASE_URL`, `BHUDRISHTI_DOCUMENT_STORAGE_DIR`, `BHUDRISHTI_OCR_PROVIDER`, `BHUDRISHTI_TESSERACT_CMD`, and `BHUDRISHTI_OCR_LANGUAGE` (for example `eng` or `eng+hin` when both models are installed). For scanned documents, install Tesseract and the language data you need; searchable PDFs can use embedded text without Tesseract. The backend enforces upload size, page, and pixel caps, explicit CORS origins, score weights, and routing thresholds in `backend/app/config.py`. SQLite and local files are defaults; a PostgreSQL URL can be configured.

## Account email and manual verification

The application sends verification and password-reset mail through the SMTP server configured in `backend/.env` (or the backend process environment). Supply `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`, `SMTP_USER`, `SMTP_PASS`, and `SMTP_FROM` using the exact values documented by your provider. `SMTP_SECURE=true` selects implicit TLS; `false` requires STARTTLS. Set `VITE_APP_URL` in the repository-root `.env` to the frontend URL that recipients can open. The local value is `http://localhost:5173`, so verification links have the format `http://localhost:5173/#/verify-email?token=<TOKEN>`. For another device, use a reachable HTTPS URL. Keep SMTP credentials in the ignored `backend/.env`, and restart the backend after changing them. Restart both services after changing `VITE_APP_URL`. The legacy `BHUDRISHTI_PUBLIC_APP_URL` is a compatibility alias; use `VITE_APP_URL` for current setup. No SMTP provider values are bundled with the project. `/api/v1/health` reports `smtp.configured` and `smtp.connectionVerified`; its background TLS/authentication check sends no email and returns no credentials.

To check delivery with your own inbox:

1. Configure `backend/.env` with the provider's SMTP settings, run the migration, and start the backend with the commands above.
2. Start the frontend with the commands above and open [Sign up](http://localhost:5173/#/signup).
3. Register a new account with your full name, a unique username, your real email address, and a new password. Select Revenue Officer, Verifier, or Auditor to request that ordinary role. Selecting Administrator creates an approval request with restricted Auditor access after email verification; only an existing authorized administrator can grant ADMIN.
4. Check that inbox for the BhuDrishti AI verification email and open its link within 24 hours. The verification page should confirm activation.
5. Open [Sign in](http://localhost:5173/#/login), use the verified email and password, and confirm that the Command Center and Documents load. Sign out.
6. Open [Forgot password](http://localhost:5173/#/forgot-password), submit the same email, and check that inbox for the reset email.
7. Open the reset link within 30 minutes, choose a new password, and sign in with it. The previous password and previously issued sessions should no longer work.

Verification and reset links are single use. The application returns an email delivery error when required SMTP configuration is missing or signup mail fails. Password recovery uses a generic response so the API does not reveal whether an address has an account. Automated tests inject an isolated mail transport and do not send to the real provider; the local harness under `work/` is outside the application configuration.

## Work through a record

1. Sign in as an administrator or Revenue Officer. Open **Documents**, upload a PDF or image, and start processing.
2. Inspect the stored stages and source page. The backend chooses embedded text or Tesseract per page, extracts fields, and stores OCR/text, evidence, validation, and score results. Click a field to locate its source.
3. Open **Validation** to see missing fields, format and range checks, local-reference comparisons, the quality breakdown, and the route. A low score is a review signal, not a legal judgment.
4. Open the **Review Queue**. An officer reviews fields, enters corrections with reasons, and resolves or acknowledges issues. Approval is blocked while required values or current field validation remain invalid.
5. After approval, inspect the final record and audit events. An administrator or Revenue Officer can attach a GeoJSON parcel boundary with a source reference. The GIS map draws that boundary at its supplied WGS84 coordinates and records the import in the audit trail. Without a sourced boundary the record remains unmapped. Importing geometry does not independently verify a cadastral survey or legal ownership.

The checked-in PDFs under `samples/` are **synthetic development fixtures**. They pass through the real upload and processing path, then their source notices classify them into the separate **Sample dataset** (`#/demo`). They do not appear in operational documents, review queues, records, metrics, search, notifications, or GIS. `samples/sample_land_record_demo.pdf` reproduces the reported two-column extraction defect: its text contains Owner `Ravi Kumar`, Survey/Khasra `123/4A`, and Area `2.50 Acres`, but **does not contain State**. A fresh upload extracts those present values and leaves State missing. Use an isolated test database when exercising officer decisions with fixtures; operational decisions require an actual source and corroboration of missing values.

### Label an isolated QA frontend

For the existing isolated QA database, use the two-terminal commands in [Local email verification](docs/LOCAL_EMAIL_VERIFICATION.md#isolated-qa-on-port-5174). Set `VITE_APP_URL=http://localhost:5174` in **both** QA processes and `API_PROXY_TARGET=http://127.0.0.1:8001` in the QA frontend process. The backend must use the existing QA database and separate QA document storage. Open `http://localhost:5174`.

The QA frontend also sets `VITE_QA_WORKSPACE=true`. Its persistent notice, record page, GIS panel, and map popups label content as **synthetic/test data, not authoritative land records or parcel boundaries**. This development display flag does not create a database, grant permissions, classify documents, or bypass backend safeguards. Use fresh terminals for the normal application so QA environment overrides cannot carry over.

## Routes and authorization

Account routes are `#/signup`, `#/login`, `#/verify-email`, `#/forgot-password`, and `#/reset-password`. Authenticated routes are `#/dashboard`, `#/documents`, `#/processing`, `#/validation`, `#/review`, `#/records`, `#/gis`, `#/analytics`, `#/audit`, `#/settings`, and the read-only sample view `#/demo`. Review and record detail use `#/review/{recordId}` and `#/records/{recordId}`. Protected API groups under `/api/v1` include `/auth`, `/documents`, `/reviews`, `/records`, `/gis/parcels`, `/audit/events`, `/notifications`, `/analytics/summary`, and `/search`. Operational reads are the default; sample document and evidence reads require an explicit `dataset=sample` query.

An **Admin** provisions accounts and can perform all operations. A **Revenue Officer** uploads, processes, reviews, and makes final decisions. A **Verifier** inspects and recommends but cannot approve. An **Auditor** reads records, GIS, and audit history without changing decisions. Self-registration persists the selected Revenue Officer, Verifier, or Auditor role. An Administrator selection remains Auditor with a pending request until an authorized administrator approves it after email verification. The server reads roles from persisted users, never from a role supplied by the browser.

## Verification

From `backend/`:

```powershell
python -m pytest -q
python -m alembic check
python -m scripts.export_openapi
```

From `frontend/`:

```powershell
npm run generate:api
npm test
npm run lint
npm run typecheck
npm run build
```

The backend tests include real uploads of the two-column PDF and scanned PDF, persisted OCR/evidence, scoring, local-reference isolation, authentication/RBAC, review corrections, audit events, sourced GIS geometry, and sample dataset isolation. Frontend tests check stage history, score display, terminal polling, review routing, GIS coordinate handling, and document dataset scoping; browser checks cover upload through officer review, sourced parcel display, and the separated sample view.

## Boundaries

This is a local prototype. There is no official land registry connector, external identity provider, official cadastral geometry feed, durable worker queue, or tamper-proof external audit store. Officer-imported parcel boundaries retain their stated source but are not independently checked against an official cadastre. Tesseract recognition depends on installed language data and source quality; embedded PDF text has **unmeasured OCR confidence** rather than an invented percentage. Audit events are append-only through the application ORM, and source files are stored locally under opaque UUID paths. The [architecture guide](docs/architecture.md) describes the active implementation. Earlier phase documents remain as historical design and verification records; their demo routes and walkthroughs are retired.
