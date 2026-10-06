# Local email verification fix — 2026-09-27

## Root cause and correction

The original Vite process listened on `::1:5173` (IPv6 localhost), while account emails linked to `127.0.0.1:5173` (IPv4). There was no frontend listener at that IPv4 address. The backend at `127.0.0.1:8000` was healthy. This failed before token verification could run.

The shared repository-root `.env` now contains `VITE_APP_URL=http://localhost:5173`. Vite and backend settings read this same file using paths anchored to the project. Vite binds the configured host/port with `strictPort`; its `/api` proxy targets `http://127.0.0.1:8000`. A second Vite start correctly fails with `Port 5173 is already in use` instead of silently moving to 5174. Both original processes were stopped and fresh processes started independently.

Verification URL format:

```text
http://localhost:5173/#/verify-email?token=<TOKEN>
```

The existing backend constructs signup, resend, and password-reset URLs from the shared setting. The obsolete local backend URL setting was removed. SMTP entries were compared before/after and preserved. No database schema, role definitions, auth/session design, mail transport, or RBAC implementation was replaced.

The verification page reads the hash token, calls the existing backend POST endpoint, displays loading/success/error states, offers **Go to Sign In** or resend as appropriate, and removes the token from the address bar after the attempt. It deduplicates only in-flight requests, ignores stale navigation results, and rechecks reopened links against the backend. Success animation respects reduced-motion preferences.

## Automated checks

| Gate | Result | Evidence |
| --- | --- | --- |
| Backend tests | PASS | 110 passed; 16 deprecation warnings; final run 95.66 seconds. |
| Frontend tests | PASS | 40 passed. |
| Lint | PASS | `npm run lint`, no warnings. |
| Typecheck | PASS | `npm run typecheck`. |
| Production build | PASS | `npm run build`, 2938 modules. |
| Database migrations | PASS | `alembic check`: no new upgrade operations; current and head both `0012_role_approval`. |
| Settings independence | PASS | Fresh settings resolve localhost from both backend directory and Windows user directory. |

Regression coverage includes invalid, expired, reused, and wrong-purpose tokens; atomic consumption and activation; duplicate signup; unverified login; verified login; requested-role persistence; pending Administrator signup; administrator-only approval; role refresh after approval; generic error handling; secret-free logs; canonical email URLs; environment precedence; hash parsing; effect replay; and stale response suppression.

## Live local checks

### Follow-up: clean, unconsumed email test

At the user's request, a single fresh signup was sent on **September 27, 2026 at 23:33 IST** to `sathwikperiket+bd-clean-20260927233321@gmail.com`. The live Vite-proxied signup returned HTTP202. No verification POST was made for this account and its URL was not opened.

A read-only inspection of the exact message in the sender's Gmail Sent folder established:

- HTML and plain-text links contain the same token.
- The emailed token's SHA-256 digest matches the correct account's stored verification token.
- The actual frontend hash-parser function extracts that exact token unchanged (checked in isolation, without a network verification call).
- URL origin is `http://localhost:5173`, hash route is `/verify-email`, and the existing frontend POST route remains `/api/v1/auth/verify-email` through Vite to API8000.
- Account is `UNVERIFIED`, verification timestamp is absent, token `used_at` is NULL, and token is unexpired.
- Creation is `2026-09-27 18:03:22 UTC`; expiry is `2026-09-28 18:03:22 UTC`, exactly 24 hours (September 28 at 23:33 IST).
- Requested and persisted role are both Revenue Officer.

The previous real signup's email was also checked read-only: its token matches the database and remains unused/unexpired. Earlier automated error-page checks intentionally used `qa-invalid-token-not-issued`; they were not attempts to verify the real emailed token. No evidence establishes a rejection of that real token.

The new isolated regression `test_signup_emails_exact_persisted_token_without_consuming_it` passed. It checks committed/unused token state during transport delivery and after202, exact digest matching, identical HTML/plain links and24-hour expiry. It calls signup only. No production authentication or SMTP changes were needed in this follow-up.

**Next user action:** open the newest received message addressed to the fresh alias above, subject **Verify your BhuDrishti AI email**, and click **Verify email address** once on this Windows PC. The token remains unused pending this click. A Sent copy confirms the sent content, not inbox receipt or completed verification.

Read-only evidence is saved in `work/clean_email_signup_evidence.json`; the local scripts `work/clean_email_signup.py` and `work/audit_sent_verification.py` never call the verification endpoint. The disposable QA password is stored encrypted with Windows DPAPI for a later authorized login check. No raw action token or SMTP password was saved in this report or diagnostic output.

### Earlier checks

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend | PASS | `http://localhost:5173/` returned HTTP 200; browser rendered real account pages. |
| API proxy | PASS | `http://localhost:5173/api/v1/health` returned healthy API8000 status. |
| Real SMTP connection | PASS | Health reported configured=true and connectionVerified=true after restart. |
| Signup and real SMTP send | PASS | Fresh QA Revenue Officer signup through the Vite proxy returned 202; existing real SMTP transport used. |
| Duplicate signup | PASS | Repeated request returned 409. |
| Unverified state/login | PASS | Database read showed UNVERIFIED, no verification timestamp, one unused token, requested/stored Revenue Officer role; login returned 401 and browser showed rejection. |
| Invalid verification | PASS | Live POST returned 400; browser displayed invalid/expired/already-used guidance and resend option; token removed from address bar. |
| Received email / successful browser verification | PENDING | User selected their own inbox and was asked to open the newest test email. SMTP acceptance is not treated as proof of inbox receipt. |
| Activated account / browser role dashboard | PENDING | Awaiting the user's legitimate email-link verification before sign-in checks. |

Expiry and consumed-token rejection are verified by automated endpoint tests using isolated data. No account was auto-verified and no verification timestamp or token was modified to force success.

Browser evidence of the real unverified-login rejection (password masked):

![Unverified QA login rejected](../work/local-verification-unverified-login.png)

## Exact application/configuration/documentation files changed

All paths below are relative to `C:\Users\Sathwik Sai\Documents\Codex\2026-09-24\files-pasted-by-the-user-you`:

- `.env` — local ignored shared public configuration (added).
- `.env.example` — shared configuration template (added).
- `backend/.env` — removed obsolete frontend URL only; SMTP entries preserved.
- `backend/.env.example` — points to shared frontend URL.
- `backend/app/config.py` — canonical URL alias, localhost default, anchored dotenv loading/precedence.
- `backend/app/api/routes/auth.py` — invalid/expired/used-link error wording.
- `backend/tests/test_email.py` — configuration regressions.
- `backend/tests/test_account_lifecycle.py` — URL/lifecycle/security assertions.
- `frontend/.env.example` — documents root configuration location.
- `frontend/vite.config.ts` — shared env, configured host/port, strict port, API proxy retained.
- `frontend/config/appLocation.ts` — URL validation and host/port/path derivation (added).
- `frontend/src/features/auth/AccountPages.tsx` — verification presentation, request/navigation handling.
- `frontend/src/features/auth/account-pages.css` — loading/success/error presentation and reduced motion.
- `frontend/src/features/auth/emailVerification.ts` — hash parsing and in-flight verification coordination (added).
- `frontend/tests/app-location.test.mjs` — URL/binding tests (added).
- `frontend/tests/email-verification.test.mjs` — request/hash/navigation tests (added).
- `frontend/tests/account-api.test.mjs` — unavailable-service error regression.
- `README.md` — local setup and role documentation corrections.
- `frontend/README.md` — shared config and localhost setup.
- `backend/README.md` — shared config and localhost setup.
- `docs/LOCAL_EMAIL_VERIFICATION.md` — exact Windows commands and troubleshooting (added).
- `docs/LOCAL_EMAIL_VERIFICATION_REPORT.md` — this evidence report (added).

Local ignored QA support: `work/local_verification_smoke.py` and `work/local_verification_smoke.json`. The script exercises the running API and reads account state; it does not edit verification state. Build outputs and test caches were regenerated by the required gates.

See [exact Windows start commands](LOCAL_EMAIL_VERIFICATION.md#start-the-existing-workspace). Both development servers are running at the time of this report.
