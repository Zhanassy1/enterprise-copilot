# Enterprise Copilot

**Multi-tenant AI copilot для бизнес-документов:** семантический поиск, RAG-чат и краткие summary по PDF/DOCX/TXT с **изоляцией по рабочим пространствам (workspace)**, **фоновой индексацией** (Celery + PostgreSQL/pgvector), **планом и квотами** и **журналом аудита**.

Репозиторий: [github.com/Zhanassy1/enterprise-copilot](https://github.com/Zhanassy1/enterprise-copilot)

[![CI](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml)

**Это SaaS?** Да, в смысле **многоарендного B2B-продукта**: отдельные **рабочие пространства (workspace)** с ролями и квотами, веб-приложение и API. Развёртывание — под ваш контроль (Docker / облако), не обязательно публичный мультитенант-хостинг. Термины: **[docs/product-glossary.md](docs/product-glossary.md)**.

---

## Что это и для кого

| | |
|--|--|
| **Продукт** | Платформа для команд, которым нужно быстро находить факты в договорах, политиках и отчётах, не читая сотни страниц вручную. |
| **Для кого** | Компании и продуктовые команды, которые готовы к self-hosted или облачному развёртыванию с контролем данных и лимитов. |
| **Проблемы** | Долгий поиск в документах, разрозненные файлы, риск «галлюцинаций» без источников — закрываются RAG с цитатами, workspace scope и статусами обработки. |

### Ключевые возможности

- **Multi-tenant AI copilot** — данные и векторный индекс разделены по **рабочим пространствам (workspace)**; роли: **владелец / администратор / участник / наблюдатель** (в API: owner / admin / member / viewer). См. [глоссарий](docs/product-glossary.md).
- **Асинхронная индексация** — после загрузки создаётся **задача индексации** (ingestion job); обработка в **worker**, не в HTTP-запросе. Статусы: **queued → processing / retrying → ready | failed** у документа и задачи.
- **Изоляция** — API и worker привязаны к `workspace_id`; клиент передаёт **`X-Workspace-Id`**.
- **План и квоты** — лимиты запросов, токенов LLM, загрузок, параллельных задач индексации и страниц PDF по тарифу **free / pro / team**; см. [docs/quotas.md](docs/quotas.md).
- **Auth / security lifecycle** — JWT, refresh rotation, logout / logout-all, password reset с revoke refresh, failed-login audit, production **startup_checks**.
- **Observability / runbook** — структурные логи, `X-Request-Id`, `/metrics`, опционально Sentry; операции — [docs/runbook.md](docs/runbook.md), [docs/observability.md](docs/observability.md).

### Платформенный блок (одним абзацем)

Продукт позиционируется как **почти полноценный SaaS-фундамент**: не только API, но и **веб-UI** (landing, документы, поиск, чат, план и лимиты, очередь обработки, аудит). Внешний биллинг (Stripe и т.д.) — в roadmap; планы и usage отражаются через API и UI.

---

<a id="evaluator-five-minutes"></a>

## Быстрая оценка за 5 минут (evaluator guide)

1. `docker compose up --build` — открыть UI **http://localhost:3000** (landing), **Регистрация** → **Вход**.
2. Убедиться, что выбран **workspace** (переключатель в боковой панели); при первом входе подставляется доступный workspace.
3. **Документы** → загрузить PDF/DOCX; открыть **Очередь обработки** — увидеть job в статусе «В очереди» / «Индексация», затем «Готово».
4. **Поиск** или **Чат** — задать вопрос по содержимому; проверить источники в ответе.
5. **План и лимиты** — план workspace и счётчики месяца; **Аудит** — события (при наличии действий); при необходимости сравнить лимиты с [docs/quotas.md](docs/quotas.md).

---

<a id="product-flow"></a>

## Демо-сценарий (сквозной flow)

| Шаг | Действие |
|-----|----------|
| 1 | Регистрация и вход |
| 2 | Выбор **рабочего пространства** (список из API; самостоятельное создание новых — в roadmap) |
| 3 | Загрузка документа |
| 4 | **Асинхронная обработка** — job в UI и статус на карточке документа |
| 5 | Поиск, чат, summary по документу |
| 6 | Квоты и безопасность — лимиты на странице плана; аудит; ops — логи и метрики по [docs/observability.md](docs/observability.md) |

---

## Скриншоты

Готовые скриншоты в репозиторий не вшиты (зависят от окружения). План размещения и имена файлов: **[docs/assets/SCREENSHOTS.md](docs/assets/SCREENSHOTS.md)**. После съёмки добавьте изображения в `docs/assets/screenshots/` и обновите README ссылками.

---

## Текущие возможности и ограничения

| Состояние | Что имеется в виду |
|-----------|---------------------|
| **Работает** | Auth, workspace scope, upload, async ingestion, поиск и чат с источниками, summary, квоты, rate limits по плану, audit API + UI, billing usage API + UI (без live-провайдера оплаты). |
| **Почти production-ready** | Compose overlay, startup checks, метрики, runbook, S3 storage path — при правильных секретах и worker. |
| **Ограничения** | Нет полноценного **Stripe/инвойсов**; нет UI приглашений и полного team management; **роль viewer** ограничивается API (403), не всеми дизейблами во фронте. Подробнее: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md). |

### Roadmap (кратко)

| Горизонт | Направления |
|----------|-------------|
| **Near-term** | Внешний биллинг, приглашения в workspace, role-aware UX (кнопки по ролям), e2e Playwright. |
| **Long-term** | SSO, расширенный admin tenant, сравнение документов, расширенная аналитика. |

Детализация по шагам зрелости: **[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)**.

---

## Архитектура (кратко)

| Слой | Технологии |
|------|------------|
| API | FastAPI, JWT, workspace dependencies |
| Worker | Celery, очередь `ingestion`, retry/backoff |
| DB | PostgreSQL + **pgvector** |
| Queue | Redis (broker Celery) |
| Storage | `local` (dev) или **S3** / MinIO |
| Frontend | Next.js (landing + приложение) |

**Асинхронный ingestion:** `POST /api/v1/documents/upload` сохраняет файл, создаёт `Document` и `IngestionJob`, **коммитит**, затем `ingest_document_task.apply_async` ([`document_ingestion.py`](backend/app/services/document_ingestion.py)). Векторы пишет worker ([`document_indexing.py`](backend/app/services/document_indexing.py), [`tasks/ingestion.py`](backend/app/tasks/ingestion.py)). В **production** синхронная индексация в HTTP запрещена (`startup_checks`).

Инвентарь tenant-scope: **[docs/WORKSPACE_ROUTING.md](docs/WORKSPACE_ROUTING.md)**. Обзор компонентов: **[docs/architecture.md](docs/architecture.md)**.

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

`docker-compose.yml` **публикует** порты Postgres (5433) и Redis (6380) на хост для разработки — **не** как модель публичного production.

---

## Production setup

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Подробности: **[docs/deployment.md](docs/deployment.md)**. Шаблон: **[.env.production.example](.env.production.example)**.

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

## Документация

| Документ | Содержание |
|----------|------------|
| [docs/deployment.md](docs/deployment.md) | Dev vs prod compose, TLS, S3/MinIO, миграции |
| [docs/security.md](docs/security.md) | Секреты, proxy, rate limits, audit |
| [docs/quotas.md](docs/quotas.md) | Планы free/pro/team, enforcement, 429 |
| [docs/observability.md](docs/observability.md) | Логи, Sentry, `/metrics` |
| [docs/runbook.md](docs/runbook.md) | Инциденты, backup, очередь |
| [docs/storage-lifecycle.md](docs/storage-lifecycle.md) | Объекты, retention, дедуп |
| [docs/email-testing.md](docs/email-testing.md) | SMTP, capture, e2e |
| [docs/testing-database.md](docs/testing-database.md) | NullPool, интеграционные тесты |
| [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) | Зрелость и roadmap |
| [docs/product-glossary.md](docs/product-glossary.md) | Workspace, роли, план, задача индексации |
| [docs/assets/SCREENSHOTS.md](docs/assets/SCREENSHOTS.md) | План скриншотов для README |
| [docs/WORKSPACE_ROUTING.md](docs/WORKSPACE_ROUTING.md) | API / Celery по workspace |

Шаблоны env: [.env.example](.env.example), [env/.env.example](env/.env.example), [backend/.env.example](backend/.env.example), [.env.production.example](.env.production.example).

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

## Структура репозитория

```text
enterprise-copilot/
├── backend/           # FastAPI, Celery, Alembic, tests
├── frontend/          # Next.js (landing + app)
├── docs/
├── docker-compose.yml
├── docker-compose.prod.yml
└── README.md
```

`docker compose down` — остановка dev-стека.
