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

## Security

- Do not commit secrets, real emails, or production URLs. Use `.env.example` / docs for placeholders only.
- For sensitive vulnerability reports, prefer a private channel to maintainers if you publish one later (`SECURITY.md`); until then, open a confidential issue only if GitHub allows it for this repo.

## License

By contributing, you agree that your contributions are licensed under the same terms as the project — see [LICENSE](LICENSE).
