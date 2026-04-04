# Email flows (verification / password reset) — test and local strategies

**Продуктовый контекст:** подтверждение email и сброс пароля — часть auth lifecycle; в production нужен реальный SMTP или эквивалент.

Production sends mail via **SMTP** (`smtp_host`, `smtp_port`, …). For automated tests and local dev without a real SMTP relay, use one of the options below.

**Product context:** [README.md](../README.md) (Storage / Security / Testing).

## 1. In-memory capture (`EMAIL_CAPTURE_MODE`)

When `EMAIL_CAPTURE_MODE=1` (or `true`), the app **does not** open SMTP; outbound messages are appended to an in-memory buffer exposed by `app.services.email_service`:

- `clear_captured_emails()`
- `get_captured_emails()` → `list[{"to", "subject", "body"}]`

**Constraints:** `startup_checks` **rejects** `EMAIL_CAPTURE_MODE` when `ENVIRONMENT=production`. Use only in local/test.

**Unit tests:** `backend/tests/test_email_capture.py` patches `settings.email_capture_mode` and asserts tokens appear in the captured body.

**Full HTTP e2e (PostgreSQL):** `backend/tests/test_email_e2e_flow.py` — `RUN_INTEGRATION_TESTS=1`, patches `email_capture_mode`, runs:

1. `POST /auth/register` → capture verification mail → parse `token=` → `POST /auth/verify-email` → `{"ok": true}`
2. `POST /auth/request-password-reset` → capture → `POST /auth/reset-password` → old password rejected, new password login succeeds

Same env/DB setup as `test_api_integration.py` (see README Tests).

## 2. Fake SMTP sink (Mailpit / MailHog)

Run a dev SMTP server that accepts messages and shows them in a browser:

- **Mailpit** (recommended): `docker run -p 1025:1025 -p 8025:8025 axllent/mailpit`
- Point **SMTP** to `localhost:1025` (often no TLS/auth), set `smtp_from_email` to a placeholder address.

Then exercise the real `send_email()` path (no capture mode) and verify delivery in the UI (`http://localhost:8025` for Mailpit).

## 3. Test plan (full e2e)

| Step | Check |
|------|--------|
| Register | `POST /auth/register` → row in `email_verification_tokens` |
| Capture | Mail body contains `token=` or parseable token |
| Verify | `POST /auth/verify-email` with token → `email_verified` |
| Password reset | `POST /auth/request-password-reset` → capture token → `POST /auth/reset-password` |

**Hooks:** `send_verification_email` / `send_password_reset_email` in `app/services/email_service.py`; audit events in `app/api/routers/auth.py`.

## 4. CI

CI does **not** require SMTP. Integration job runs `unittest discover` with `RUN_INTEGRATION_TESTS=1`; the e2e module above is included when that env is set.

## 5. Pool mode for tests

See **[docs/testing-database.md](testing-database.md)** for `SQLALCHEMY_USE_NULLPOOL` (why integration CI sets it, and when `ResourceWarning` without it is expected).

## 6. Production: SendGrid / Mailgun / Postmark

**SMTP relay (simplest):** Most providers expose SMTP on port 587 with STARTTLS. Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL` (sender must be allowed in the provider dashboard). Same code path as local Mailpit — no extra dependencies.

**SendGrid REST:** Set `SENDGRID_API_KEY` (and `SMTP_FROM_EMAIL` for the `from` address). When the key is present, the app uses HTTPS to `api.sendgrid.com` instead of SMTP. Handy if you prefer API keys over SMTP credentials.

**Invite links** use `APP_BASE_URL` + `/invite/{token}` (see `send_workspace_invite_email`). **`EMAIL_CAPTURE_MODE`** still stores full bodies for tests; never enable capture in production.
