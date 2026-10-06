# Complete email and authentication audit

Audit date: 6 October 2026. Workspace:
`C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you`.

## Architecture and complete flow map

The active application is React/TypeScript/Vite in `frontend/` and
Python/FastAPI/Uvicorn in `backend/`. SQLAlchemy uses the existing SQLite
database locally; Alembic manages its schema. This is not a Node/Nodemailer or
Prisma application. Historical phase exports are not the running application.

The occurrence audit covered 861 eligible text files, 706 text entries in six
ZIP archives, and private QA scripts. Private environment values were checked
without printing them. Binary databases, uploads and dependency directories
are not application email implementations. Inventory:
`work/email_occurrence_inventory.json`.

| Flow | Frontend hash route | Actual backend endpoint | Central email operation |
| --- | --- | --- | --- |
| Signup | `#/signup` | POST `/api/v1/auth/signup` | `send_verification_email` |
| Resend | `#/verify-email` | POST `/api/v1/auth/resend-verification` | `send_verification_email` |
| Verify | `#/verify-email?token=…` | POST `/api/v1/auth/verify-email` | Consumes token; sends no email |
| Recovery | `#/forgot-password` | POST `/api/v1/auth/forgot-password` | `send_password_reset_email` |
| Reset | `#/reset-password?token=…` | POST `/api/v1/auth/reset-password` | Updates password; sends no email |
| Sign in / identity / sign out | `#/login`, `#/dashboard` | POST login/logout; GET me | Existing revocable sessions |

Frontend entry: `frontend/src/main.tsx` → `App.tsx`. Public hash routing and
parameters live in `features/auth/publicRoutes.ts` and `emailVerification.ts`.
`AccountPages.tsx` uses `accountApi.ts`; sign-in/session behavior remains in
`session.ts`. Vite reads the root public configuration and proxies `/api` to
the backend without rewriting the path.

Backend entry: `backend/app/main.py`. Auth routes are registered from
`app/api/routes/auth.py`. `app/config.py` loads anchored backend/root environment
files, with process environment overrides. `app/db/models.py` persists users,
action-token hashes and sessions; `app/db/session.py` provides request-scoped
database sessions. `services/auth/service.py` and the existing permission
dependencies enforce authentication/RBAC; `services/auth/lifecycle.py` owns
verification/reset tokens. All outgoing account email uses
`services/email/service.py` and its existing `SmtpMailTransport`.

No active OTP sender or alternate mail provider was found. Administrator
provisioning, bootstrap, in-app notifications and the document workflow do not
send email. Legacy `work/local_smtp` artifacts are dormant and have no active
application/startup references; none was used for this audit.

## Root causes and corrections

### Signup and resend

Earlier socket error 10013 came from an outbound-network restriction on the
backend process; it was not evidence of wrong Gmail credentials. The current
backend runs with network access, and both direct health and Vite proxy health
return 200. The existing SMTP configuration is unchanged.

No incorrect recipient routing was found for ordinary Gmail addresses. However,
the previous validation accepted header syntax such as display names/comments:
SMTP could reinterpret the stored account string as another mailbox. Shared
bare-mailbox validation now covers frontend, request contracts, direct/bootstrap
account creation and centralized SMTP recipients. Plus aliases remain valid.
Configured branded sender names still support one validated sender mailbox.

Provider acceptance and recipient refusal are checked before success is
reported. Resend send failures return safe 503; a failed token is retired,
without verifying the account or blocking immediate retry. Resend intentionally
sends nothing for unknown/already-verified accounts or requests within the
one-minute cooldown; its response is conditional, not a delivery receipt.

An additional confirmed code defect could reject a valid emailed token: a QUIT
or socket-cleanup error after successful SMTP acceptance was classified as send
failure. Acceptance-aware handling now preserves the successful submission and
token, logging only a safe cleanup warning. Pre-acceptance failures still fail.
There is no evidence that this edge case caused the earlier Gmail incident.

The previously reported user account remained UNVERIFIED in the database at
this audit. A success page for a different QA account does not activate it.
Its fresh verification link is left for the account owner to open; it is not
consumed by the audit.

For `abhilashreddydhavu@gmail.com`, Gmail accepted the newest replacement at
**8:56:37 PM IST on 6 October 2026**. Its Sent copy has the correct recipient,
frontend origin and exact unused token hash. No related recent bounce was found.
This confirms submission, not receipt in that user's inbox. Open the newest
**Verify email address** button on this Windows PC, then sign in. Recovery is
available after that account's email has actually been verified.

### Forgot password and reset

The concrete recovery defect was `conceal_failure=True`: actual SMTP failures
were logged, the failed reset token was retired, and HTTP 202 was still returned.
That concealment has been removed. Recovery performs a connection/TLS/auth
preflight before looking up the account, so provider-wide failures produce the
same safe 503 for existing and unknown addresses. Actual submission failures
also propagate safe 503 and retire only the failed token.

Recovery intentionally requires an ACTIVE, verified, enabled account. Unknown,
unverified, suspended and cooldown requests receive the same conditional 202
without an email. The frontend now explains verification and cooldown generally,
and offers verification help for every user without disclosing eligibility.
The reported UNVERIFIED account is therefore not currently eligible for reset.

Reset still validates the purpose/hash/expiry, claims the token atomically,
hashes the new password, revokes existing sessions and retires other reset
tokens. Its safe error now names invalid, expired or already-used links.

### Frontend success and deployment URLs

The old account API helper accepted unrelated/empty successful responses. It now
requires the endpoint's expected status and JSON confirmation contract before
showing success, including the existing signup role fields. Existing design,
role selection, verification loading/success animation and navigation remain.

Local email links derive from the shared `VITE_APP_URL`, currently:

```text
http://localhost:5173/#/verify-email?token=<one-time-token>
http://localhost:5173/#/reset-password?token=<one-time-token>
```

These are formats, not usable tokens. Outside development/tests, configuration
now rejects insecure or loopback frontend URLs instead of emailing localhost
links from a deployed backend. Configuration validation hides private input.

## Security retained

- 32-byte cryptographically random action tokens; only SHA-256 digests persist.
- Verification expires after 24 hours; reset after 30 minutes, compared in UTC.
- Atomic one-time consumption; invalid/expired/reused tokens cannot activate or
  reset an account. Failed delivery never auto-verifies an account.
- Unverified login fails. Role remains persisted and server-controlled.
- Administrator signup remains AUDITOR/PENDING after email verification until
  an authorized existing administrator approves it.
- No schema, session, RBAC, provider or authentication framework replacement.
- Logs use fixed event labels, safe classes and numeric SMTP/OS codes; no raw
  server replies, action links, tokens, passwords or credential values.

## SMTP configuration and diagnostics

Real Gmail SMTP: `smtp.gmail.com`, port 587, `SMTP_SECURE=false`, mandatory
STARTTLS with normal certificate validation, followed by existing authentication.
These settings agree with [Google's documented STARTTLS settings](https://support.google.com/mail/answer/7104828?hl=en).
No temporary SMTP service or console provider was used.

Startup logs configuration status; a background probe checks DNS, TCP, TLS and
authentication without sending a message. `/health` and `/api/v1/health` publish
only safe configuration/connection booleans. Recovery uses the same transport
for its preflight. Each real send logs provider acceptance only after successful
SMTP submission. A successful preflight is not proof of recipient inbox receipt.

Safe diagnostics distinguish missing configuration, SMTP authentication,
connection, TLS and delivery failures. Provider refusal retains only its fixed
exception category and numeric status. Raw SMTP responses are never logged.

## Actual local verification

Two isolated synthetic QA accounts used unique aliases of the configured,
controlled Gmail mailbox. Receipt was checked in the recipient **INBOX** with
read-only IMAP, not inferred solely from SMTP acceptance or a Sent copy. The
exact received link was matched to its unused stored token hash before opening.
Action links stayed in memory and were opened through a private loopback QA
bridge; this bridge is not an authentication endpoint or SMTP server.

| Check | Result / evidence |
| --- | --- |
| Browser signup | 202 contract confirmed; persisted AUDITOR/UNVERIFIED; actual verification email in INBOX |
| Signup link | Browser showed Email verified; database ACTIVE with verification timestamp |
| Duplicate signup | 409 |
| Unverified login | 401 |
| Verified identity/login | 200; backend identity AUDITOR; browser Auditor workspace |
| Unauthorized administrator endpoint | 403 |
| Browser resend | New message in INBOX; distinct unused token; browser activated second account |
| Previous verification link after activation | 400; old tokens consumed |
| Browser forgot password | 202 contract confirmed; actual reset email in INBOX |
| Reset link | Existing browser reset form opened; correct unused token hash and 30-minute lifetime |
| Password reset | Real API 200; password update persisted |
| Reused reset token | 400 |
| Old password / old session | 401 / 401 |
| New password | API 200 and real browser sign-in/dashboard |
| Invalid verification | API 400; browser clear error and resend option |
| Invalid reset | API 400 |
| Expired verification/reset | Rejected by isolated automated integration tests; live clocks/expiry were not altered |
| Already verified resend | Conditional 202; no new verification send |
| Unknown recovery | Conditional 202; no account-existence statement |
| Direct/proxied health | 200 / 200; SMTP configured and connection verified |

Browser password-change submission was not performed: the computer-use policy
requires the human to enter and submit a new password. The reset route/form was
checked in the browser, and the actual reset was completed/tested through the
existing API on a QA account. No real user's password was changed.

Safe live evidence: `work/auth_email_audit_evidence.json`. Screenshots:
`work/auth-audit-verified.png`, `work/auth-audit-reset-form.png`,
`work/auth-audit-new-password-dashboard.png`,
`work/auth-audit-invalid-verification.png`.

## Files changed

Backend application:

- `backend/app/api/routes/auth.py` — consistent failure propagation, recovery
  preflight, safe eligibility/send events and reset errors.
- `backend/app/services/email/service.py` — recipient validation, transport
  connection-check contract, acceptance-aware cleanup, matching template expiry.
- `backend/app/email_address.py` — shared bare-mailbox normalization.
- `backend/app/contracts/auth.py` — request validation.
- `backend/app/services/auth/service.py` — direct account-creation validation.
- `backend/app/config.py` — production public URL guard and safe validation errors.
- `backend/app/api/routes/health.py`, `backend/app/main.py` — visible safe startup
  configuration diagnostics.

Frontend application:

- `frontend/src/features/auth/accountValidation.ts` — recipient validation.
- `frontend/src/features/auth/accountApi.ts` — real response-contract checks.
- `frontend/src/features/auth/AccountPages.tsx` — verification/recovery/reset help.

Tests:

- `backend/tests/test_account_lifecycle.py`
- `backend/tests/test_email.py`
- `backend/tests/test_email_addresses.py`
- `backend/tests/test_bootstrap_admin.py`
- `frontend/tests/account-api.test.mjs`
- `frontend/tests/account-validation.test.mjs`

Documentation/config examples:

- `.env.example`, `backend/.env.example` — names only, no secret/example values.
- `backend/README.md`, `docs/EMAIL_AUTH_AUDIT.md`.

The ignored QA harness `work/auth_email_audit_e2e.py` and its safe evidence
artifacts were added for live verification. Private `.env` files were unchanged.

## Test gates

| Final gate | Result |
| --- | --- |
| Complete backend suite | **201 passed**, 16 existing dependency/migration deprecation warnings, 89.84 seconds |
| Complete frontend suite | **47 passed**, 0 failed |
| Frontend lint | PASS, exit 0 |
| Frontend typecheck | PASS, exit 0 |
| Production build | PASS, exit 0, Vite 8.3.1, 2,938 modules |
| Database migration check | PASS, no new upgrade operations; `0012_role_approval` at head |
| Backend and Vite proxy health | 200 / 200; real SMTP connection verified |
| Real local browser checks | Signup, verification, resend, recovery request, reset form, invalid verification, missing reset token, verified/new-password login and Auditor dashboard |

After adding signup diagnostics, the full gate caught nine assertions that
retained successful setup-email logs before testing a later failed send. Test
capture scopes were corrected; failure assertions were retained, and the final
complete suite above passes. No database schema migration is required. There
is no separate configured backend lint/typecheck command; the available lint
and typecheck gates are the frontend's existing scripts.

Exact backend test gate (from the backend directory):

```powershell
.\.venv\Scripts\python.exe -m pytest -o addopts='' -q -p no:cacheprovider --basetemp work/email-auth-release-20261006
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m alembic current
```

Existing frontend gates (from the frontend directory):

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

## Required environment names

Root public configuration:
`VITE_APP_URL`, `VITE_API_BASE_URL`, `API_PROXY_TARGET`.
Local values: frontend `http://localhost:5173`, API base `/api/v1`, development
proxy target `http://127.0.0.1:8000`.

Private backend SMTP configuration:
`SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`.
SMTP secrets must never be `VITE_*` variables or bundled into frontend assets.

Deployment configuration:
`BHUDRISHTI_ENVIRONMENT`, `BHUDRISHTI_AUTH_SECRET`,
`BHUDRISHTI_DATABASE_URL` when overriding local SQLite,
`BHUDRISHTI_CORS_ORIGINS` when using a separate API origin.
`BHUDRISHTI_PUBLIC_APP_URL` remains a supported legacy alias; use the same
canonical frontend URL everywhere rather than conflicting aliases.

Example files contain names only: fill required values and remove unused
optional entries before startup. Empty numeric/JSON entries are not defaults.

## Exact local startup

Backend, ordinary Windows PowerShell with outbound SMTP access:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, a second terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you\frontend'
npm.cmd run dev
```

Keep both terminals running. Restart the backend after changing its environment;
restart Vite after changing public/proxy configuration. Open
[Signup](http://localhost:5173/#/signup). Local email links must be opened on
this computer; localhost on a phone or another computer points to that device.

Manual test: register a controlled address, open the newest Verify email address
button within 24 hours, sign in, sign out, request recovery, open the newest
Reset password button within 30 minutes, submit a new password and sign in.
For an existing unverified signup, request a replacement verification link;
repeating signup intentionally returns a duplicate-account conflict.

## Deployment considerations and remaining limits

- Set a real reachable HTTPS frontend URL before starting a production backend.
  Production now fails closed for local/insecure action-link origins.
- Build frontend public configuration for that environment. Vite's dev proxy
  is not present in the production bundle: configure a deployed `/api` reverse
  proxy, or an explicit API origin with appropriate CORS.
- Supply private secrets through deployment environment/secret storage; apply
  migrations, persist the database/storage and keep clocks synchronized.
- Permit provider DNS and outbound authenticated TLS SMTP; confirm actual
  deployed SMTP/network behavior. Local verification does not test a deployment.
- Rate-limit public signup/resend/recovery at the infrastructure layer. Recovery
  probes the provider even for ineligible requests, to report outages uniformly.
- A recipient-specific SMTP rejection after a successful preflight can still
  produce a status difference for eligible requests. Messages never identify
  account existence; complete status/timing indistinguishability is not claimed.
- SMTP acceptance cannot guarantee inbox delivery at every recipient. This
  audit proves real delivery to the controlled QA Gmail inbox; another user's
  inbox/Spam filtering remains externally observable by that user.
- The affected account owner's fresh verification click remains their action;
  no account was auto-verified and no live token was consumed on their behalf.

No SMTP passwords, QA passwords, bearer tokens or real action tokens are included
in this report, evidence output or application diagnostic logs.
