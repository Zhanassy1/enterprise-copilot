# Contributing to Enterprise Copilot

Thanks for your interest. This project follows the same checks as [CI](.github/workflows/ci.yml).

## Prerequisites

- **Docker (recommended):** see [README.md](README.md#dev-setup) — `docker compose up --build` for API, UI, Postgres, Redis, and Celery.
- **Local:** Python 3.12+ for `backend/`, Node 22+ for `frontend/` (versions match CI).

## Workflow

1. Fork the repository and create a branch from `main`.
2. Make focused changes; keep commits and PRs easy to review.
3. Open a pull request. Use [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) when applicable.

## What to run before pushing

**Backend** (`backend/`):

```bash
python -m ruff check app tests
python -m pytest tests/ -v
```

Integration tests that need Postgres are opt-in (`RUN_INTEGRATION_TESTS=1`, `DATABASE_URL=…`) — see [docs/testing-database.md](docs/testing-database.md) and the README **Testing** section.

**Frontend** (`frontend/`):

```bash
npm run lint
npm run build
```

**Demo screenshots** (updates `docs/assets/screenshots/`, including `team.png`):

```bash
cd frontend && npm run demo:screenshots
```

Requires UI + API (e.g. Compose). Optional: `DEMO_SCREENSHOTS_WITH_INGEST=1` with a running Celery worker for ingest-heavy frames.

**E2E smoke (marketing + auth, no API):** production build + Playwright — matches CI.

```bash
cd frontend
npm run build
npx playwright install chromium
npm run start &
# wait until http://127.0.0.1:3000 responds, then:
npm run test:e2e:smoke
```

**Workspace evaluator** (`frontend/e2e/workspace-evaluator.spec.ts`): full app shell after API registration — requires UI + API (e.g. Compose). Skips automatically if `GET /healthz` on the API origin fails.

```bash
cd frontend
set E2E_API_URL=http://127.0.0.1:8000/api/v1
set E2E_BASE_URL=http://127.0.0.1:3000
npm run test:e2e -- workspace-evaluator
```

**Invite flow e2e** (`frontend/e2e/invite-flow.spec.ts`): run against a stack where the backend has **`EMAIL_CAPTURE_MODE=1`** so `POST /api/v1/workspaces/…/invitations` includes `plain_token` in the JSON (tests/dev only). Without it, the test skips. Example:

```bash
cd frontend
set E2E_API_URL=http://127.0.0.1:8000/api/v1
set E2E_BASE_URL=http://127.0.0.1:3000
npm run test:e2e -- invite-flow
```

## Security

- Do not commit secrets, real emails, or production URLs. Use `.env.example` / docs for placeholders only.
- For sensitive vulnerability reports, prefer a private channel to maintainers if you publish one later (`SECURITY.md`); until then, open a confidential issue only if GitHub allows it for this repo.

## License

By contributing, you agree that your contributions are licensed under the same terms as the project — see [LICENSE](LICENSE).
