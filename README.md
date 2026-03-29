# Enterprise Copilot

**Multi-tenant AI copilot для бизнес-документов:** семантический поиск, RAG-чат и краткие summary по PDF/DOCX/TXT с **изоляцией по рабочим пространствам (workspace)**, **фоновой индексацией** (Celery + PostgreSQL/pgvector), **планом и квотами** и **журналом аудита**.

Репозиторий: [github.com/Zhanassy1/enterprise-copilot](https://github.com/Zhanassy1/enterprise-copilot)

[![CI](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml)

**Это SaaS?** Да, в смысле **многоарендного B2B-продукта**: отдельные **рабочие пространства (workspace)** с ролями и квотами, веб-приложение и API. Развёртывание — под ваш контроль (Docker / облако), не обязательно публичный мультитенант-хостинг. Термины: **[docs/product-glossary.md](docs/product-glossary.md)**.

<a id="demo-quick-1min"></a>

### Демо за 1 минуту

| Скорость | Что сделать |
|----------|-------------|
| **~20 сек** | Прокрутить [скриншоты](#screenshots) или открыть [docs/assets/SCREENSHOTS.md](docs/assets/SCREENSHOTS.md) — landing, `/pricing`, документы, jobs, billing, поиск, чат, аудит. |
| **~1 мин** | Поднять стек `docker compose up --build`, открыть **http://localhost:3000**, на маркетинговой главной — блок **«Демо за одну минуту»** (`/#demo-quick-1min`), затем **Регистрация** → приложение → **workspace** в переключателе → **Документы**. |
| **Видео** | Сценарий записи и таймкоды: **[docs/DEMO_MEDIA.md](docs/DEMO_MEDIA.md#demo-quick-1min)**; встроенный плеер на главной при `NEXT_PUBLIC_DEMO_VIDEO_EMBED_URL` — см. [#demo-video](#demo-video). |

Расширенный чек-лист: [#evaluator-five-minutes](#evaluator-five-minutes).

---

## Что это и для кого

| | |
|--|--|
| **Продукт** | Платформа для команд, которым нужно быстро находить факты в договорах, политиках и отчётах, не читая сотни страниц вручную. |
| **Для кого** | Компании и продуктовые команды, которые готовы к self-hosted или облачному развёртыванию с контролем данных и лимитов. |
| **Проблемы** | Долгий поиск в документах, разрозненные файлы, ответы без привязки к источнику — закрываются поиском и чатом с цитатами, границами workspace и статусами обработки. |

### Ключевые возможности

- **Multi-tenant AI copilot** — данные и векторный индекс разделены по **рабочим пространствам (workspace)**; роли: **владелец / администратор / участник / наблюдатель** (в API: owner / admin / member / viewer). См. [глоссарий](docs/product-glossary.md).
- **Асинхронная индексация** — после загрузки создаётся **задача индексации** (ingestion job); обработка в **worker**, не в HTTP-запросе. Статусы: **queued → processing / retrying → ready | failed** у документа и задачи.
- **Изоляция** — API и worker привязаны к `workspace_id`; клиент передаёт **`X-Workspace-Id`**.
- **План и квоты** — лимиты запросов, токенов LLM, загрузок, параллельных задач индексации и страниц PDF по тарифу **free / pro / team**; см. [docs/quotas.md](docs/quotas.md).
- **Auth / security lifecycle** — JWT, refresh rotation, logout / logout-all, password reset с revoke refresh, failed-login audit, production **startup_checks**.
- **Эксплуатация** — логи, идентификатор запроса, метрики, опционально Sentry; памятка для операторов — [docs/runbook.md](docs/runbook.md), [docs/observability.md](docs/observability.md).

### Платформенный блок (одним абзацем)

Продукт — это **веб-приложение с multi-tenant контуром**: не только HTTP API, но и **UI** — маркетинговая главная и `/pricing`, затем приложение с **переключателем рабочего пространства (workspace)** и бейджем роли, страницей **«Команда и доступ»** (матрица ролей и честные плейсхолдеры до API участников и приглашений), каталог **документов**, **поиск**, **чат**, **план и лимиты** (`/billing`), **очередь задач индексации** и **журнал аудита**. Онлайн-оплата и смена плана «в один клик» — в roadmap; фактический тариф и usage — через API и UI ([docs/quotas.md](docs/quotas.md)).

---

<a id="evaluator-five-minutes"></a>

## Быстрая оценка за 5 минут (evaluator guide)

1. `docker compose up --build` — открыть **http://localhost:3000** (главная для гостей), при желании пролистать **http://localhost:3000/pricing**; затем **Регистрация** → **Вход**.
2. Убедиться, что выбрано **рабочее пространство** (переключатель в боковой панели); при первом входе подставляется доступное пространство из API.
3. **Документы** → загрузить PDF/DOCX; открыть **Очередь обработки** — увидеть задачу индексации в статусе «В очереди» / «Индексация», затем «Готово».
4. **Поиск** или **Чат** — задать вопрос по содержимому; проверить источники в ответе.
5. **План и лимиты** — план рабочего пространства и счётчики месяца; **Аудит** — события (при наличии действий); при необходимости сравнить лимиты с [docs/quotas.md](docs/quotas.md).

| Дальше | Ссылка |
|--------|--------|
| Скриншоты UI (без запуска) | [#screenshots](#screenshots) · [docs/assets/SCREENSHOTS.md](docs/assets/SCREENSHOTS.md) |
| Демо за 1 минуту | [#demo-quick-1min](#demo-quick-1min) · маркетинговая главная `/#demo-quick-1min` |
| Запись / спикер | [docs/DEMO_MEDIA.md](docs/DEMO_MEDIA.md) (блок 1 мин и ~4 мин) |

**Визуально по шагам:** готовые кадры в [docs/assets/screenshots/](docs/assets/screenshots/). Развёрнутый голосовой сценарий: [docs/DEMO_MEDIA.md#demo-script-4min](docs/DEMO_MEDIA.md#demo-script-4min). Тот же порядок шагов в доке: [Оценка за 5 минут в DEMO_MEDIA](docs/DEMO_MEDIA.md#evaluator-walkthrough).

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

<a id="demo-video"></a>

## Демо-видео

- Сценарий записи и таймкоды: **[docs/DEMO_MEDIA.md](docs/DEMO_MEDIA.md)**.
- **Локальный UI:** задайте **`NEXT_PUBLIC_DEMO_VIDEO_EMBED_URL`** (URL для iframe, напр. YouTube embed) — на главной появится плеер в блоке «Видео-демо».
- Пока ролика нет — ниже можно вставить тот же embed вручную (замените `src`):

```html
<!-- Demo video embed placeholder — замените VIDEO_ID -->
<iframe width="560" height="315" src="https://www.youtube.com/embed/VIDEO_ID" title="Enterprise Copilot demo" allow="fullscreen" allowfullscreen></iframe>
```

<a id="screenshots"></a>

## Скриншоты

Снято Playwright-спекой `frontend/e2e/demo-screenshots.spec.ts` → **`docs/assets/screenshots/`** (подробности: **[docs/assets/SCREENSHOTS.md](docs/assets/SCREENSHOTS.md)**). Команда: `cd frontend && npm run demo:screenshots` (нужны UI + API; для кадра **summary** и документа в статусе «Готово» см. `DEMO_SCREENSHOTS_WITH_INGEST=1` и worker в SCREENSHOTS).

| Landing | Pricing | Documents |
|:-------:|:-------:|:---------:|
| ![Landing](docs/assets/screenshots/landing.png) | ![Pricing](docs/assets/screenshots/pricing.png) | ![Documents](docs/assets/screenshots/documents.png) |

| Jobs | Billing | Search |
|:----:|:-------:|:------:|
| ![Jobs](docs/assets/screenshots/jobs.png) | ![Billing](docs/assets/screenshots/billing.png) | ![Search](docs/assets/screenshots/search.png) |

| Chat | Audit |
|:----:|:-----:|
| ![Chat](docs/assets/screenshots/chat.png) | ![Audit](docs/assets/screenshots/audit.png) |

<a id="demo-script"></a>

## Демо (сценарий 3–5 минут)

Коротко (1 мин): **[docs/DEMO_MEDIA.md#demo-quick-1min](docs/DEMO_MEDIA.md#demo-quick-1min)**. Развёрнутый сценарий записи: **[docs/DEMO_MEDIA.md — ~4 мин](docs/DEMO_MEDIA.md#demo-script-4min)** (login → workspace → upload → очередь → поиск → чат → summary → план/usage → аудит). Таблица «Демо-сценарий» выше — краткая версия того же flow.

---

## Текущие возможности и ограничения

| Состояние | Что имеется в виду |
|-----------|---------------------|
| **Работает** | Auth, workspace scope, upload, async ingestion, поиск и чат с источниками, summary, квоты, rate limits по плану, audit API + UI, billing usage API + UI (без live-провайдера оплаты). |
| **Почти production-ready** | Compose overlay, startup checks, метрики, runbook, S3 storage path — при правильных секретах и worker. |
| **Ограничения** | Нет полноценного **Stripe/инвойсов**; нет живого API **приглашений** — на странице «Команда» честный placeholder и неактивная кнопка до backend. **Роль viewer:** загрузка/удаление документов, новые диалоги и отправка в чате **отключены в UI** + плашки на ключевых экранах; остальные отказы — по ответам API. Подробнее: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md). |

### Roadmap (кратко)

| Горизонт | Направления |
|----------|-------------|
| **Near-term** | Внешний биллинг, API и UI **приглашений** в workspace, расширение e2e Playwright. |
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
| [docs/DEMO_MEDIA.md](docs/DEMO_MEDIA.md) | Видео-демо и материалы презентации |
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
