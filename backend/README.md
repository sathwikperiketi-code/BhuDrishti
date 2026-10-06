# BhuDrishti AI backend

FastAPI/Pydantic contracts are the API source of truth. The canonical
`LandRecord` schema includes typed evidence provenance per field and an explicit
`extensions` map. Unknown top-level fields are rejected. The SQLAlchemy model
stores searchable columns plus the full canonical payload. Alembic owns schema
migrations, and the database URL may point to SQLite or PostgreSQL.

## Run locally

For the existing Windows workspace, start the API in its own PowerShell terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use an ordinary Windows PowerShell terminal; the existing backend dependencies are installed in `.venv`, rather than the global Python installation. Start the frontend separately using [Local email verification](../docs/LOCAL_EMAIL_VERIFICATION.md). Vite on port 5173 proxies `/api` to this API on port 8000. Both processes read `VITE_APP_URL=http://localhost:5173` from the repository-root `.env`; private SMTP settings stay in `backend/.env`. Backend configuration file paths resolve from the project, not the shell's current directory. The commands below are one-time setup for a **new installation**.

Use Python 3.11 or newer. From this directory:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m alembic upgrade head
python -m scripts.bootstrap_admin --email admin@example.org --name "Initial Administrator"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/health`, `http://127.0.0.1:8000/api/v1/health`, or `http://127.0.0.1:8000/docs`. The default SQLite
database is `backend/bhudrishti.db` regardless of the process working
directory, so bootstrap and API use the same account store.
To use PostgreSQL, install `.[postgres]` and set
`BHUDRISHTI_DATABASE_URL=postgresql+psycopg://...`.

The bootstrap command prompts securely for a password of at least 12 characters
when it creates an account. Repeating it for the same email is a no-op and
does not prompt or overwrite the password. There are no built-in users or
default passwords. For controlled noninteractive setup, pass the password
through `BHUDRISHTI_BOOTSTRAP_PASSWORD` in the process environment. To add
another named administrator in local development, explicitly run:

```powershell
python -m scripts.bootstrap_admin --email another@example.org --name "Another Administrator" --allow-additional-admin
```

Preserve any existing `backend/.env`. For real signup and password-recovery
delivery, fill the SMTP settings in that ignored file with the provider's
documented values before starting the backend. No provider, mailbox, or SMTP
credential is configured by the example. Settings in the backend process
environment take precedence over dotenv values; remove any old local test
SMTP variables from that process before starting the real application.

Migration `0008_accounts` adds unique usernames, explicit account states, email
verification timestamps, and hashed single-use action-token storage to the
existing user table. Previously provisioned active accounts, including local
administrators, retain their password hashes and sessions and migrate to
`ACTIVE` with their existing creation time as the verification timestamp.
Previously inactive accounts migrate to `SUSPENDED`. The migration derives a
unique normalized username from each existing email; newly registered accounts
start `UNVERIFIED` and require actual email verification before access.

To recover an existing administrator, use an interactive password prompt and
confirm the exact email. The reset clears login lockout and revokes its sessions:

```powershell
python -m scripts.bootstrap_admin --email admin@example.org --reset-password --confirm-email admin@example.org
```

Additional administrator bootstrap is blocked outside development/test.
A reset outside those environments also requires `--allow-production-reset`.
Once signed in, an administrator creates officer, verifier, auditor, or
additional admin accounts through `POST /api/v1/auth/users` or the Settings
screen. The
server verifies the stored password hash and derives permissions from the
current database role on every request. `POST /api/v1/auth/logout` revokes
the bearer session.

For local development, the signing key is generated once and persisted in
the database so sessions survive API restarts. Set a unique secret of at
least 32 characters in `BHUDRISHTI_AUTH_SECRET` for deployments; it is
mandatory outside development/test environments. Set
`BHUDRISHTI_AUTH_SESSION_HOURS` to adjust the default eight-hour expiry.

The document pipeline uses PyMuPDF, Pillow, OpenCV, and
Tesseract. Install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
for raster images and scanned PDFs. The service finds it on `PATH` or at the
standard Windows installation path; set `BHUDRISHTI_TESSERACT_CMD` for a
custom location. Searchable PDFs can be read through their embedded text.
The default OCR language is `eng`; other installed Tesseract language packs
can be selected with `BHUDRISHTI_OCR_LANGUAGE`.

## API endpoints

- `GET /health` and `GET /api/v1/health` report service liveness.
- `POST /api/v1/auth/signup` accepts a full name, unique username, email,
  password, confirmation, and `requestedRole` (`REVENUE_OFFICER`, `VERIFIER`,
  `AUDITOR`, or `ADMIN`). It creates an `UNVERIFIED` account and sends a
  one-time verification link. The three ordinary roles become the stored role;
  an administrator request stores `AUDITOR` with `roleApprovalStatus=PENDING`.
  A request cannot grant `ADMIN` privileges.
- `POST /api/v1/auth/verify-email` activates an account using the link token.
  `POST /api/v1/auth/resend-verification` requests a replacement link when
  eligible.
- `POST /api/v1/auth/forgot-password` requests a reset link using a generic
  response. `POST /api/v1/auth/reset-password` consumes that single-use token,
  replaces the password, and revokes prior sessions.
- `POST /api/v1/auth/login` signs in with `{email,password}` and returns a
  revocable bearer session plus the persisted user profile. Unverified and
  suspended accounts cannot sign in.
- `GET /api/v1/auth/me` resolves the current database-backed identity and
  role; `POST /api/v1/auth/logout` revokes it.
- `GET/POST /api/v1/auth/users` are administrator-only account provisioning
  endpoints.
- `GET /api/v1/auth/admin-requests` lists administrator access requests for
  existing administrators. `POST /api/v1/auth/admin-requests/{user_id}/approve`
  grants `ADMIN` only after email verification. `POST .../{user_id}/reject`
  leaves the account at `AUDITOR`. Each decision records the reviewing
  administrator and time. Login and `/auth/me` always return the actual
  database role, including for sessions issued before an approval.
- `POST /api/v1/documents/upload` accepts multipart `file` (PDF, JPG/JPEG,
  PNG, TIFF). It verifies filename, extension, content signature, page count,
  and bounded file size before storing under a server-generated UUID.
- `GET /api/v1/documents` returns `{items,total}` with pagination via `limit`
  and `offset`. Both summaries and details include `reviewStatus`, derived
  from the latest persisted review case; document processing `status` remains
  independent.
- `GET /api/v1/documents/{id}` returns metadata, page URLs, OCR evidence,
  extraction, validation, score breakdown, warnings, and stage history.
- `POST /api/v1/documents/{id}/process` starts processing or retries a failed
  result and returns HTTP 202 with the current stage.
- `GET /api/v1/documents/{id}/processing-status` provides durable state for
  polling (`uploaded`, `processing`, `completed`, `failed`).
- `GET /api/v1/documents/{id}/pages/{pageNumber}/image` returns the page image
  used for evidence overlays. Add `?original=true` for the raw rendered page.

Product endpoints retain the `/api/v1` version prefix; `/health` is an additional liveness alias. Processing steps are
persisted as `upload`, `preprocessing`, `ocr`, `field_extraction`,
`normalization`, `validation`, `quality_score`, and `final_routing`. OCR regions
and field evidence use normalized `[x,y,width,height]` coordinates in the
range `0..1`; the image endpoint selects the matching page rendition.

Uploaded bytes are processed by embedded PDF text extraction or local OCR.
Synthetic fixture documents are allowed for local tests and development, but
they use the same upload, extraction, validation, review, and persistence path
as other files. No demo scenario routes are mounted in the product API.

The pipeline performs AI-assisted extraction and validation. Its quality route
is a prototype signal; human officers remain responsible for final
verification and approval.

## Configuration

### Real application SMTP

Set these values in `backend/.env` (or in the backend process environment)
using your provider's exact SMTP settings:

```dotenv
SMTP_HOST=
SMTP_PORT=
SMTP_SECURE=
SMTP_USER=
SMTP_PASS=
SMTP_FROM=
```

`SMTP_SECURE=true` uses implicit TLS; `false` requires STARTTLS before login
or delivery. `SMTP_USER` and `SMTP_PASS` must be configured together for an
authenticated server. `SMTP_FROM` is used for both verification and reset
messages; use a sender allowed by the provider. The settings may also use
`BHUDRISHTI_SMTP_*` names, but the plain names above are the documented
configuration. Set `VITE_APP_URL` in the repository-root `.env` to the
recipient-accessible frontend URL. Both the API and Vite use that same value.
The default is `http://localhost:5173`; the verification link format is
`http://localhost:5173/#/verify-email?token=<TOKEN>`. The legacy
`BHUDRISHTI_PUBLIC_APP_URL` remains a compatibility alias. Use `VITE_APP_URL`
for new configuration. Restart both services after changing the shared URL;
restart the backend after changing private SMTP settings. A missing or unreachable SMTP server never causes the app to
pretend that signup mail was delivered. The app does not provide a local SMTP
fallback.

`GET /api/v1/health` reports only whether SMTP is configured and whether its
background TLS/authentication connection check succeeded. The check sends no
email; `connectionVerified` is initially null while the first check is pending.

A JSON signup HTTP 503 with an email detail comes from the backend after reaching the email stage. It does not by itself prove an API proxy failure. The inspected local failure was Windows socket error 10013 from outbound network restrictions in the backend's sandbox; the existing Gmail configuration passed TLS and authentication from ordinary Windows PowerShell. Use the startup command above rather than changing the working SMTP values. An email failure can leave an `UNVERIFIED` account, so request **Resend verification email** instead of repeating signup for the same address. Safe response details distinguish missing email configuration, SMTP authentication failure, SMTP connection failure, and delivery failure; server logs identify the error category without credentials or action tokens.

For manual confirmation, open `http://localhost:5173/#/signup` after starting
the backend and frontend, register a new address you control, open the
verification link in that real inbox within 24 hours, then sign in. Sign out,
request a reset at `http://localhost:5173/#/forgot-password`, open the reset
link in that inbox within 30 minutes, set a new password, and sign in again.
The former password and sessions should fail. The recipient must be able to
reach `VITE_APP_URL`; the default loopback URL works only on the
same computer. Do not place SMTP credentials, account passwords, or action
tokens in documentation or logs.

Automated tests inject a separate in-memory `MailTransport` into the API and
do not contact the configured SMTP provider. The disposable harness in
`work/` is only for isolated development checks and is not part of normal
application startup or delivery.

### Consistent account email behavior

Signup, resend verification and password recovery use the same TLS-only SMTP
service. Signup confirms submission only after the provider accepts the email.
Resend and recovery return conditional HTTP 202 responses for unknown,
ineligible or cooldown requests; this protects account privacy and does not
assert that a message was sent. Recovery requires a verified, active account.
Wait at least one minute between replacement-link requests.

Recovery verifies the provider connection before account lookup. Configuration,
authentication, TLS and connection failures return the same safe HTTP 503 for
known and unknown accounts. Actual submission failures also return HTTP 503;
failed tokens are retired without changing account status or passwords. A
recipient-specific rejection can still differ by HTTP status after a successful
connection check. Deployed public authentication routes need infrastructure
rate limiting, including limits on recovery's SMTP connection probes.

The `.env.example` files list names without values. Fill required entries and
remove optional entries you are not configuring; blank numeric/JSON settings
are not defaults. Preserve the existing private SMTP configuration when
updating application code. Outside development/tests, `VITE_APP_URL` must be a
reachable HTTPS frontend URL, and `BHUDRISHTI_AUTH_SECRET` is required. Vite's
API proxy is development-only; the deployed web server must route `/api` to
the backend, or a public API base and matching explicit CORS origins must be
configured. See [the complete email audit](../docs/EMAIL_AUTH_AUDIT.md).

### Isolated QA

The existing QA workspace uses `http://localhost:5174` with API
`http://127.0.0.1:8001`. Set `VITE_APP_URL=http://localhost:5174` in both
processes, set the frontend's `API_PROXY_TARGET=http://127.0.0.1:8001`, and
keep the QA backend's database and document storage separate. The exact
PowerShell commands are in [Local email verification](../docs/LOCAL_EMAIL_VERIFICATION.md#isolated-qa-on-port-5174).
These process overrides reuse the real SMTP implementation and do not grant
roles, activate accounts, or change the normal application's configuration.

### Processing and storage

`BHUDRISHTI_DOCUMENT_STORAGE_DIR` defaults to `./document_storage` (outside
the frontend webroot), `BHUDRISHTI_UPLOAD_MAX_BYTES` to 20 MiB, and
`BHUDRISHTI_UPLOAD_MAX_PAGES` to 25. Rendered page pixels are capped at 40
million per page and 80 million per document by default.
`BHUDRISHTI_OCR_PROVIDER` accepts `auto`,
`tesseract`, or `pdf_text`; `auto` uses embedded PDF text when present and
Tesseract otherwise. `BHUDRISHTI_RENDER_DPI` controls PDF preview resolution.
`BHUDRISHTI_PREPROCESS_GRAYSCALE`, `..._DENOISE`, `..._CONTRAST`,
`..._DESKEW`, and `..._CROP` toggle image steps. OCR and processing errors
are returned as stable `{code,message}` objects and may be retried.

## Contract export and tests

```powershell
python -m scripts.export_openapi
python -m pytest
```

The script writes `openapi.v1.json`, ready for frontend type generation. Re-run
it after changing route or Pydantic contracts. The processing pipeline now
applies field, record, and supplied-reference checks plus the configured
50/30/20 weights and routing thresholds.

## Package boundaries

```text
app/api/         FastAPI composition and routes
app/contracts/   Pydantic canonical record and processing contracts
app/services/    validation, review, GIS, and scoring boundaries
app/services/documents/    upload storage, page preprocessing, local OCR, persisted pipeline
app/services/intelligence/    evidence-based extraction, validation, scoring
app/db/          SQLAlchemy base, model, and session primitives
migrations/      Alembic versioned schema
scripts/         administrator bootstrap and OpenAPI export
tests/           actual upload, extraction, review, RBAC, and relationship checks
```
