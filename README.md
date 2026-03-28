# Enterprise Copilot

**Production-style, multi-tenant** AI copilot для корпоративных документов: семантический поиск, RAG-чат, summary, **async ingestion** (Celery), **workspace + роли**, **квоты**, **audit**, **observability**, **S3-ready** storage.

[![CI](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml)

**Документация (индекс):** [deployment](docs/deployment.md) · [security](docs/security.md) · [quotas](docs/quotas.md) · [observability](docs/observability.md) · [runbook](docs/runbook.md) · [storage-lifecycle](docs/storage-lifecycle.md) · [WORKSPACE_ROUTING](docs/WORKSPACE_ROUTING.md) — полная таблица ниже в [Documentation](#documentation).

Статус реализации по дорожной карте: **[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)**

---

## Overview

Сервис изолирует данные по **workspace** (заголовок `X-Workspace-Id`). Пользователь входит по JWT, выбирает workspace, загружает PDF/DOCX/TXT, задаёт вопросы и получает ответы с опорой на фрагменты документов. В **production** тяжёлая обработка (парсинг, chunking, эмбеддинги, pgvector) выполняется **только в worker**, не в HTTP upload.

---

## Architecture

| Слой | Технологии |
|------|------------|
| API | FastAPI, JWT, workspace deps (`owner` / `admin` / `member` / `viewer`) |
| Worker | Celery, очередь `ingestion`, retry/backoff |
| DB | PostgreSQL + **pgvector** |
| Cache / queue | Redis |
| Storage | `local` (dev) или **S3** / MinIO (`storage_key`, presigned URLs) |
| Frontend | Next.js |

**Поток ingestion (фактический код):**

1. **HTTP** [`backend/app/api/routers/documents.py`](backend/app/api/routers/documents.py) → [`DocumentIngestionService.upload_document`](backend/app/services/document_ingestion.py): файл в storage (`storage_key`), строка `documents` со статусом **`queued`**, при `INGESTION_ASYNC_ENABLED=1` — строка **`IngestionJob`** (`queued`) и `ingest_document_task.apply_async` в Celery.
2. **В request-response нет** записи `embedding_vector` в БД: векторы пишутся в **worker** в [`DocumentIndexingService.run`](backend/app/services/document_indexing.py) (`UPDATE document_chunks ... embedding_vector`).
3. **Worker** [`backend/app/tasks/ingestion.py`](backend/app/tasks/ingestion.py) вызывает индексацию; статусы документа и job: `queued` → `processing` / `retrying` → `ready` или `failed`.
4. Синхронная индексация в том же процессе, что и upload — только **local dev**: `ENVIRONMENT=local`, `ALLOW_SYNC_INGESTION_FOR_DEV=1`, `INGESTION_ASYNC_ENABLED=0` (см. `document_ingestion.py`).

**Поток RAG:** search/chat фильтруют чанки по `workspace_id`; учитываются квоты и rate limits (см. [docs/quotas.md](docs/quotas.md)).

### Статусы document / job (API)

| Статус | Где задаётся | HTTP |
|--------|----------------|------|
| `queued`, `processing`, `retrying`, `ready`, `failed` | поле `documents.status`, `ingestion_jobs.status` ([`backend/app/models/document.py`](backend/app/models/document.py)) | `GET /api/v1/documents/{id}` — в ответе `DocumentOut.status`; `GET /api/v1/documents/{id}/ingestion` — последний [`IngestionJob`](backend/app/api/routers/documents.py) (`get_document_ingestion_job`); список задач: `GET /api/v1/ingestion/jobs` ([`backend/app/api/routers/ingestion.py`](backend/app/api/routers/ingestion.py), фильтр `?status=`). |

В production upload не выполняет индексацию в HTTP: только storage + запись строк + постановка Celery (см. выше и [`startup_checks.py`](backend/app/core/startup_checks.py)).

---

## Development setup

**Docker (рекомендуется):** Postgres и Redis с пробросом портов на хост, API, worker, frontend.

```bash
docker compose up --build
```

- UI: http://localhost:3000  
- API: http://localhost:8000 — [OpenAPI](http://localhost:8000/docs), [healthz](http://localhost:8000/healthz)  

Шаблон env для локальной разработки: [env/.env.example](env/.env.example) → скопировать в `backend/.env`. Закоммиченный dev-контекст для контейнеров: [backend/.env.docker](backend/.env.docker).

**Без Docker:** `backend/` — venv, `pip install -r requirements.txt`, `alembic upgrade head`, `uvicorn app.main:app --reload`. `frontend/` — `npm install`, `npm run dev`.

**Доступ с другого устройства в LAN:** пересоберите frontend с API base вашей машины, например:

```bash
docker compose build --build-arg NEXT_PUBLIC_API_BASE=http://<IP_ПК>:8000/api/v1 frontend
docker compose up -d frontend
```

(или задайте переменные сборки в `docker-compose.yml` под ваш сценарий.)

---

## Production setup

Базовый `docker compose up` **публикует** порты БД/Redis — только для разработки. Для продакшена используйте overlay без внешних портов БД/Redis и **обязательные** секреты:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Требуются в окружении или `.env` рядом с compose: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` (хост `db`, те же креды), `REDIS_PASSWORD`, `REDIS_URL`, `SECRET_KEY`. Подробно: [docs/deployment.md](docs/deployment.md), шаблон: [.env.production.example](.env.production.example).

TLS и доверие к `X-Forwarded-*` — на reverse proxy; см. [docs/security.md](docs/security.md). Старт API в `ENVIRONMENT=production` с небезопасным конфигом **запрещён** (fail-fast в `startup_checks`).

---

## Security

Секреты, CORS, rate limits, proxy / `TRUSTED_PROXY_IPS`, заголовки в production — **[docs/security.md](docs/security.md)**. Refresh tokens, rotation, logout, audit событий входа — в коде и в security-доке.

---

## Quotas

Планы **free / pro / team**, лимиты на upload, concurrent jobs, запросы search/chat/rerank, токены — **[docs/quotas.md](docs/quotas.md)**. Enforcement в API и worker; превышение — ответы 429 и события audit.

---

## Observability

Структурированные логи, `X-Request-Id`, Sentry (опционально), `/metrics` — **[docs/observability.md](docs/observability.md)**. Операционные сценарии: **[docs/runbook.md](docs/runbook.md)**.

---

## Storage

`storage_key`, local vs S3/MinIO, дедуп, soft-delete, политика AV — **[docs/storage-lifecycle.md](docs/storage-lifecycle.md)**. В production при `PRODUCTION_REQUIRE_S3_BACKEND=1` требуется `STORAGE_BACKEND=s3` (см. `startup_checks`).

---

## Runbook

Инциденты (503 БД, очередь Celery, 429, бэкапы, миграции) — **[docs/runbook.md](docs/runbook.md)**.

---

## Documentation

| Документ | Содержание |
|----------|------------|
| [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) | Статус шагов дорожной карты (SaaS maturity) |
| [docs/deployment.md](docs/deployment.md) | Compose dev/prod, TLS, MinIO/S3, миграции |
| [docs/security.md](docs/security.md) | Секреты, proxy, rate limits, заголовки |
| [docs/quotas.md](docs/quotas.md) | Планы, лимиты, enforcement |
| [docs/observability.md](docs/observability.md) | Логи, Sentry, метрики |
| [docs/runbook.md](docs/runbook.md) | Операции, backup/restore, алерты |
| [docs/storage-lifecycle.md](docs/storage-lifecycle.md) | Объекты, S3, дедуп, retention |
| [docs/WORKSPACE_ROUTING.md](docs/WORKSPACE_ROUTING.md) | Инвентарь API и Celery: tenant scope |
| [docs/architecture.md](docs/architecture.md) | Обзор системы |
| [docs/email-testing.md](docs/email-testing.md) | Тестовый SMTP / capture / Mailpit, план e2e для verify/reset |

Шаблоны env: [.env.example](.env.example) (указатель), [env/.env.example](env/.env.example), [backend/.env.example](backend/.env.example), [.env.production.example](.env.production.example).

---

## Tests

**Unit (без Postgres):** из `backend/` — `py -3 -m unittest discover -s tests -v` — интеграционные классы будут *skipped*.

**Integration (PostgreSQL):** поднять тестовую БД и прогнать весь suite (cross-workspace и API flow **не** skipped):

```bash
# из корня репозитория — контейнер db_test, порт хоста 5434 (см. docker-compose.yml profile test)
docker compose --profile test up -d db_test

# из backend/
set DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5434/enterprise_copilot_test
set RUN_INTEGRATION_TESTS=1
py -3 -m alembic upgrade head
py -3 -m unittest discover -s tests -v
```

Windows: `scripts/test-integration.ps1` делает то же (alembic + полный discover). CI: job `backend-integration` в `.github/workflows/ci.yml` — сервис Postgres на `:5433`, `RUN_INTEGRATION_TESTS=1`, полный `unittest discover`.

При `RUN_INTEGRATION_TESTS=1` middleware **не применяет** in-memory rate limits (много логинов с одного IP в одном процессе) — см. `backend/app/main.py` (`_skip_rl_for_integration`).

Для прогона без `ResourceWarning` от пула psycopg в CI и локально: `SQLALCHEMY_USE_NULLPOOL=1` (см. `backend/app/db/session.py`) — уже выставлено в jobs `backend-integration` / `backend-async-smoke` и в `scripts/test-integration.ps1`.

**Async ingestion smoke** (Celery eager, документ доходит до `ready`/`failed`): job `backend-async-smoke` в `.github/workflows/ci.yml`; локально нужны Postgres + Redis и переменные:

```bash
docker compose --profile test up -d db_test
docker compose up -d redis
set DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5434/enterprise_copilot_test
set REDIS_URL=redis://127.0.0.1:6380/0
set RUN_ASYNC_PIPELINE_SMOKE=1
set RUN_INTEGRATION_TESTS=1
set INGESTION_ASYNC_ENABLED=1
py -3 -m alembic upgrade head
py -3 -m unittest tests.test_ingestion_async_pipeline -v
```

Почта без реального SMTP: `EMAIL_CAPTURE_MODE=1` (только non-production) — см. [docs/email-testing.md](docs/email-testing.md).

```bash
cd frontend
npm run lint && npm run build
```

---

## Repository layout

```text
enterprise-copilot/
├── backend/           # FastAPI, Celery worker, Alembic, tests
├── frontend/          # Next.js
├── docs/              # Deployment, security, quotas, runbook, …
├── env/               # Dev .env example
├── docker-compose.yml
├── docker-compose.prod.yml
└── README.md
```

Остановка Docker: `docker compose down`.
