# Contributing

## Setup

- **Backend:** Python 3.12+, `cd backend && pip install -r requirements.txt`, copy/configure `.env` (see `backend/.env.example` if present). Run migrations: `alembic upgrade head`. Start API: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
- **Frontend:** Node 20+, `cd frontend && npm install && npm run dev`.
- **Docker (full stack):** from repo root, `docker compose up -d --build`. Migrations run in the one-shot `migrate` service; `api` and `worker` start after it completes successfully.

## Pull requests

- Keep changes focused; avoid unrelated refactors in the same PR.
- Match existing style (imports, typing, logging).
- If you change API behavior or env vars, update relevant docs (`README.md`, `docs/`).

## Tests

- Backend: `cd backend && pytest tests/ -q` (with test DB/Redis as in CI or `docker compose` with `db_test` profile if applicable).
- Run linters/formatters your team uses before pushing.

## Commits

- Clear, imperative subject line; body optional for non-obvious rationale.
