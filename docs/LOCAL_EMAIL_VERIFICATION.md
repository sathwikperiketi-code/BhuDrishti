# Local email verification

This guide documents configuration and reproducible checks. It is not a claim that a new live email or browser test has passed.

## Cause of the reported connection failure

The inspected Vite process listened on IPv6 loopback `::1:5173`, reachable as `localhost`, while the backend generated email links to IPv4 `127.0.0.1:5173`. That address had no frontend listener, so opening the email could fail before the application or verification endpoint ran. The API listener at `127.0.0.1:8000` was separate and reachable. A successful signup response or SMTP delivery cannot make an unavailable frontend address load.

## Shared public URL

The canonical public configuration file is:

```text
C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\.env
```

Its local values are:

```dotenv
VITE_APP_URL=http://localhost:5173
VITE_API_BASE_URL=/api/v1
API_PROXY_TARGET=http://127.0.0.1:8000
```

Vite loads this directory through `envDir`; the backend loads the same root file alongside `backend/.env`. Vite derives its hostname, port and public origin from `VITE_APP_URL`. `strictPort` prevents an accidental fallback to another frontend port. Backend signup, resend and password-reset messages use the shared configured URL. Process environment settings can override dotenv values, so use fresh terminals when switching between normal and QA services. The old `BHUDRISHTI_PUBLIC_APP_URL` remains a backend compatibility alias; use `VITE_APP_URL` for the shared configuration.

Verification links now use this format:

```text
http://localhost:5173/#/verify-email?token=<TOKEN>
```

`<TOKEN>` denotes the securely generated, single-use email token. Do not copy actual tokens into documentation, tickets, screenshots or logs. The token is in the URL fragment; the frontend reads it and sends it in the verification POST body. Successful verification removes it from the address bar. Changing the configured hostname does not invalidate existing token values, but old emails retain their original hostname. Request a replacement link using **Resend verification email** when needed.

Keep `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`, `SMTP_USER`, `SMTP_PASS`, and `SMTP_FROM` private in:

```text
C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend\.env
```

The URL correction does not require changing those SMTP values. Never put SMTP credentials in `VITE_*` variables, which are public client configuration. Restart both services after changing the shared URL. Restart the backend after a private backend configuration change.

## Start the existing workspace

The following commands use the existing project virtual environment and npm installation on this Windows PC. Run each block in a separate ordinary Windows PowerShell terminal and keep both terminals open. Use a fresh terminal with no previous QA environment overrides. Stop an older instance through its own terminal with **Ctrl+C** before starting a replacement on the same port. The backend dependencies are installed in `backend/.venv`; the global Python installation alone does not provide the required packages.

Backend terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\frontend'
& 'C:\Program Files\nodejs\npm.cmd' run dev
```

Open [Sign up](http://localhost:5173/#/signup) or [Sign in](http://localhost:5173/#/login). The browser sends `/api/v1` requests to Vite, which proxies `/api` to `http://127.0.0.1:8000`.

Read-only connectivity checks from another PowerShell terminal:

```powershell
(Invoke-WebRequest -Uri 'http://localhost:5173/' -UseBasicParsing).StatusCode
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health'
Invoke-RestMethod -Uri 'http://localhost:5173/api/v1/health'
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 5173, 8000 } | Select-Object LocalAddress, LocalPort, OwningProcess
```

When Vite itself is stopped, no application page can render a helpful error at that unavailable address. Start the frontend with the command above, then reopen the email link. If Vite is available but the API is stopped, the verification UI reports the failed request; start the backend, then retry the link. Neither case requires disabling verification. Localhost links work only on this computer. A link opened on a phone points to the phone, so use the same Windows PC for local testing.

## Signup service errors

The existing API is FastAPI on port 8000. Vite's `/api` proxy already points to `http://127.0.0.1:8000`; it does not use port 3000. A JSON HTTP 503 response with an email-delivery detail means the request reached the backend and failed during email delivery. It differs from an unreachable API or an HTML/non-JSON proxy error, which the frontend reports as an unavailable account service.

The inspected email-delivery failure was an outbound socket `PermissionError` (Windows error 10013) when the backend ran inside a restricted sandbox. The same existing Gmail configuration passed TLS and SMTP authentication outside that sandbox. Start the backend in ordinary Windows PowerShell with the command above so that its Gmail connection is allowed. This does not require changing SMTP settings.

A failed delivery may leave the newly created account `UNVERIFIED`; retrying signup with the same email can therefore return HTTP 409. Use **Resend verification email** for that account after the delivery problem is resolved, then open the newest link in the inbox. Signup and resend must not consume the link token. Only successful verification activates the account and consumes it.

## Signup through role dashboard

1. Open signup and enter a new address you control, a unique username, and a password. Select the intended role.
2. Confirm that signup returns HTTP 202 and the page asks you to check your inbox. The new account is `UNVERIFIED` and cannot log in.
3. Independently inspect the received message in that inbox. SMTP acceptance alone is not evidence of inbox arrival. Confirm the link origin is `http://localhost:5173` without exposing its token.
4. Open the link within 24 hours. The verification page calls `POST /api/v1/auth/verify-email`. Success sets `email_verified_at`, changes `UNVERIFIED` to `ACTIVE`, and consumes the verification tokens. The implementation represents a verified active account with these fields; it has no separate `VERIFIED` status enum.
5. Use **Go to Sign In**, enter the same email and password, and confirm `/auth/me` matches the account and role. The dashboard and navigation follow the persisted server role.
6. Revenue Officer, Verifier and Auditor selections persist as their corresponding ordinary roles. An Administrator selection initially stores `AUDITOR` with `roleApprovalStatus=PENDING`. Email verification activates login but does not grant ADMIN. Only an existing authorized administrator can approve that request and grant ADMIN.

Verification uses securely generated random tokens, stores only their digests, checks purpose and expiry, and claims a token once. It does not create a new session automatically or bypass role approval.

## Negative checks

| Check | Expected result |
| --- | --- |
| Invalid token | Verification POST returns 400; the page shows an error and offers resend. |
| Expired token | Verification POST returns 400; the account remains unverified. Use the isolated expiry test to avoid changing a real account's clock or token lifetime. |
| Used token | Reopening a successfully consumed link returns 400 and cannot verify again. |
| Duplicate signup | Reusing an existing username or email returns 409; no duplicate user is created. |
| Unverified login | Login returns 401 and creates no authenticated session. |
| Missing token | The verification page explains that a token is missing and offers a resend form. |
| API unavailable | The page reports the failed service request; no success is fabricated. |

Do not manually set verification timestamps or account status to pass these checks. Tests for expiry and replay use isolated test data and exercise the same backend endpoint.

## Isolated QA on port 5174

These commands use the existing QA database and its upload directory. They set process-local values in separate terminals and reuse the existing SMTP configuration. They do not create accounts or issue mail by themselves.

QA backend terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend'
$env:VITE_APP_URL = 'http://localhost:5174'
$env:BHUDRISHTI_DATABASE_URL = 'sqlite:///C:/Users/Sathwik Sai/Documents/Codex/2026-09-24/files-pasted-by-the-user-you/backend/work/role-smoke/qa.db'
$env:BHUDRISHTI_DOCUMENT_STORAGE_DIR = 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend\work\role-smoke\uploads'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

QA frontend terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\frontend'
$env:VITE_APP_URL = 'http://localhost:5174'
$env:API_PROXY_TARGET = 'http://127.0.0.1:8001'
$env:VITE_QA_WORKSPACE = 'true'
& 'C:\Program Files\nodejs\npm.cmd' run dev
```

Open [the isolated QA frontend](http://localhost:5174/). Both QA processes must use the same `VITE_APP_URL`; changing only the frontend port leaves emailed links pointing at another instance. Keep synthetic document and parcel data labeled as test data. The QA display flag grants no permissions and does not change backend dataset safeguards. Close these terminals when finished and use fresh terminals to restart the normal services.

## Automated gates

Backend tests and migration check:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend'
& '.\.venv\Scripts\python.exe' -m pytest -q
& '.\.venv\Scripts\python.exe' -m alembic check
```

Frontend tests, lint, typecheck and production build:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\frontend'
& 'C:\Program Files\nodejs\npm.cmd' test
& 'C:\Program Files\nodejs\npm.cmd' run lint
& 'C:\Program Files\nodejs\npm.cmd' run typecheck
& 'C:\Program Files\nodejs\npm.cmd' run build
```

Automated mail tests inject an isolated in-memory transport and do not establish delivery through Gmail. Report real SMTP acceptance, received inbox evidence, browser verification, and automated results separately.
