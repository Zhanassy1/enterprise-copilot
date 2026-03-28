# Email flows (verification / password reset) — test and local strategies

Production sends mail via **SMTP** (`smtp_host`, `smtp_port`, …). For automated tests and local dev without a real SMTP relay, use one of the options below.

## 1. In-memory capture (`EMAIL_CAPTURE_MODE`)

When `EMAIL_CAPTURE_MODE=1` (or `true`), the app **does not** open SMTP; outbound messages are appended to an in-memory buffer exposed by `app.services.email_service`:

- `clear_captured_emails()`
- `get_captured_emails()` → `list[{"to", "subject", "body"}]`

**Constraints:** `startup_checks` **rejects** `EMAIL_CAPTURE_MODE` when `ENVIRONMENT=production`. Use only in local/test.

**Unit tests:** `backend/tests/test_email_capture.py` patches `settings.email_capture_mode` and asserts tokens appear in the captured body.

**Integration idea:** register a user with capture on, read the verification link from `get_captured_emails()[0]["body"]`, then call `POST /api/v1/auth/verify-email` — optional extension when you add a dedicated test module.

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

CI does **not** require SMTP. Use `EMAIL_CAPTURE_MODE` in a test-only job or patch `settings` in unit tests (see `test_email_capture.py`).
