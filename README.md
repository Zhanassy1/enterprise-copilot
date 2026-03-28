# Enterprise Copilot

**Multi-tenant AI document platform** для корпоративных PDF/DOCX/TXT: семантический поиск, RAG-чат, summary, **асинхронная индексация** (Celery + PostgreSQL/pgvector), **workspaces и роли**, **квоты и usage metering**, **audit**, **наблюдаемость**, object storage (local / S3).

**Репозиторий:** [github.com/Zhanassy1/enterprise-copilot](https://github.com/Zhanassy1/enterprise-copilot)

[![CI](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml)

---

## Product overview

Продукт позиционируется как **SaaS-фундамент** для AI over documents: данные изолированы по **workspace**, доступ контролируется ролями (`owner` / `admin` / `member` / `viewer`), лимиты применяются на уровне плана, а тяжёлая обработка документов вынесена из HTTP в **worker**.

**Текущие возможности (backend + UI):**

| Область | Что есть |
|---------|----------|
| Tenancy | Заголовок `X-Workspace-Id`, членство в workspace, изоляция в API и в Celery (`workspace_id`) |
| Документы | Upload → storage → статусы `queued` → … → `ready` / `failed`; список, скачивание, summary, ingestion API |
| Индексация | Async path в production: **commit строк document/job до постановки в Celery** (`document_ingestion.py`), парсинг/chunking/embeddings в worker |
| Поиск и чат | Гибридный retrieval, квоты, rate limits по плану |
| Безопасность | JWT, refresh rotation, logout / logout-all, reuse detection, password reset + revoke refresh; fail-fast `startup_checks` в production |
| Квоты | Upload, страницы PDF, concurrent jobs, search/chat, rerank, tokens — см. [docs/quotas.md](docs/quotas.md) |
| Наблюдаемость | Структурные логи, `X-Request-Id`, `/metrics`, опционально Sentry |

**Ограничения production (честно):**

- Нет полноценного биллинга провайдера (Stripe и т.д.) — есть usage/plan stubs и API usage.
- Frontend: нет отдельного экрана Audit, нет invitations/team management — см. [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) §19.
- Email в бою требует реальный SMTP или Mailpit; для тестов есть capture — [docs/email-testing.md](docs/email-testing.md).

**Roadmap / зрелость:** таблица шагов и partial-зоны — **[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)**.

---

## Architecture

| Слой | Технологии |
|------|------------|
| API | FastAPI, JWT, workspace dependencies |
| Worker | Celery, очередь `ingestion`, retry/backoff |
| DB | PostgreSQL + **pgvector** |
| Queue | Redis (broker для Celery) |
| Storage | `local` (dev) или **S3** / MinIO |
| Frontend | Next.js |

**Асинхронный ingestion (как в коде):**

1. `POST /api/v1/documents/upload` сохраняет файл, создаёт `Document` (`queued`) и `IngestionJob` (`queued`), **коммитит** их в БД, затем вызывает `ingest_document_task.apply_async` ([`document_ingestion.py`](backend/app/services/document_ingestion.py)).
2. В том же HTTP-запросе **нет** записи векторов: эмбеддинги и chunking выполняет worker ([`document_indexing.py`](backend/app/services/document_indexing.py), [`tasks/ingestion.py`](backend/app/tasks/ingestion.py)).
3. Статусы: `queued` → `processing` / `retrying` → `ready` или `failed` (и у документа, и у job).
4. **Только dev:** синхронная индексация в процессе API при `ENVIRONMENT=local`, `INGESTION_ASYNC_ENABLED=0`, `ALLOW_SYNC_INGESTION_FOR_DEV=1` — в production запрещено `startup_checks`.

Инвентарь tenant-scope: **[docs/WORKSPACE_ROUTING.md](docs/WORKSPACE_ROUTING.md)**.

---

## Dev setup

```bash
docker compose up --build
```

| Сервис | URL |
|--------|-----|
| UI | http://localhost:3000 |
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |
| Health | http://localhost:8000/healthz |

Шаблоны env: [env/.env.example](env/.env.example) → `backend/.env`; для контейнеров: [backend/.env.docker](backend/.env.docker).

**Без Docker:** в `backend/` — venv, `pip install -r requirements.txt`, `alembic upgrade head`, `uvicorn app.main:app --reload`; в `frontend/` — `npm install`, `npm run dev`.

`docker-compose.yml` **публикует** порты Postgres (5433) и Redis (6380) на хост — удобно для dev, **не** как модель публичного production.

---

## Production setup

**Основной путь:** overlay без открытых портов БД/Redis наружу:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Подробности переменных, TLS, MinIO: **[docs/deployment.md](docs/deployment.md)**. Шаблон: **[.env.production.example](.env.production.example)**.

Старт с `ENVIRONMENT=production` и небезопасным конфигом **блокируется** ([`startup_checks.py`](backend/app/core/startup_checks.py)).

### Production checklist

| Область | Действие |
|---------|----------|
| Secrets | `SECRET_KEY` (не default), креды БД/Redis/S3 из secrets manager |
| Database | `DATABASE_URL` с TLS при необходимости; не `localhost` / не `postgres:postgres` в prod |
| Redis | Пароль в URL или `rediss://`; см. startup checks |
| Storage | Для SaaS: `STORAGE_BACKEND=s3` при `PRODUCTION_REQUIRE_S3_BACKEND=1` |
| Reverse proxy | TLS termination; `USE_FORWARDED_HEADERS` + `TRUSTED_PROXY_IPS` |
| Health | `/healthz`, `/readyz` за балансировщиком |
| Migrations | `alembic upgrade head` до или при старте API/worker |
| Worker | Celery worker с той же `REDIS_URL` и очередью `ingestion` |
| Sentry / metrics | `SENTRY_DSN` опционально; `/metrics` при `observability_metrics_enabled` |

---

## Security

Секреты, proxy, rate limits, заголовки, audit: **[docs/security.md](docs/security.md)**.

---

## Quotas

Планы, enforcement, 429: **[docs/quotas.md](docs/quotas.md)**.

---

## Observability

Логи, request id, метрики, Sentry: **[docs/observability.md](docs/observability.md)**. Операции: **[docs/runbook.md](docs/runbook.md)**.

---

## Storage lifecycle

Local vs S3, дедуп, soft-delete: **[docs/storage-lifecycle.md](docs/storage-lifecycle.md)**.

---

## Testing

| Режим | Команда / условие |
|-------|-------------------|
| Unit (без Postgres) | `cd backend && python -m unittest discover -s tests -v` — интеграционные тесты *skipped* |
| Integration | `RUN_INTEGRATION_TESTS=1` + `DATABASE_URL` на Postgres; опционально `SQLALCHEMY_USE_NULLPOOL=1` — см. [docs/testing-database.md](docs/testing-database.md) |
| Async smoke | Job **backend-async-smoke** в [.github/workflows/ci.yml](.github/workflows/ci.yml); локально `RUN_ASYNC_PIPELINE_SMOKE=1` |
| Email HTTP e2e | `tests/test_email_e2e_flow.py` при `RUN_INTEGRATION_TESTS=1` — [docs/email-testing.md](docs/email-testing.md) |

Windows: [scripts/test-integration.ps1](scripts/test-integration.ps1).

При `RUN_INTEGRATION_TESTS=1` отключаются in-memory rate limits для auth в middleware ([`main.py`](backend/app/main.py)).

```bash
cd frontend && npm run lint && npm run build
```

---

## Documentation index

| Документ | Содержание |
|----------|------------|
| [docs/deployment.md](docs/deployment.md) | Dev vs prod compose, TLS, S3/MinIO, миграции, checklist |
| [docs/security.md](docs/security.md) | Секреты, proxy, rate limits, audit |
| [docs/quotas.md](docs/quotas.md) | Планы, лимиты, enforcement |
| [docs/observability.md](docs/observability.md) | Логи, Sentry, `/metrics` |
| [docs/runbook.md](docs/runbook.md) | Инциденты, backup, очередь |
| [docs/storage-lifecycle.md](docs/storage-lifecycle.md) | Объекты, retention, AV |
| [docs/WORKSPACE_ROUTING.md](docs/WORKSPACE_ROUTING.md) | Инвентарь API / Celery по workspace |
| [docs/architecture.md](docs/architecture.md) | Обзор компонентов |
| [docs/email-testing.md](docs/email-testing.md) | Capture, Mailpit, e2e тесты |
| [docs/testing-database.md](docs/testing-database.md) | NullPool, ResourceWarning в тестах |
| [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) | Дорожная карта SaaS |

Шаблоны env: [.env.example](.env.example), [env/.env.example](env/.env.example), [backend/.env.example](backend/.env.example), [.env.production.example](.env.production.example).

---

## Repository layout

```text
enterprise-copilot/
├── backend/           # FastAPI, Celery, Alembic, tests
├── frontend/          # Next.js
├── docs/
├── docker-compose.yml
├── docker-compose.prod.yml
└── README.md
```

`docker compose down` — остановка dev-стека.
