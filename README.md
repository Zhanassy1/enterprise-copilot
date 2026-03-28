# Enterprise Copilot

Enterprise Copilot — это AI-ассистент для бизнеса, который помогает работать с корпоративными документами быстрее и удобнее.

[![CI](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml)

## Содержание README

| Раздел | Что внутри |
|--------|------------|
| [Документация](#документация) | Индекс `docs/*` (security, quotas, runbook, …) |
| [Режимы dev/prod](#режимы-разработка-vs-продакшен) | Compose, `ENVIRONMENT`, секреты |
| [Локальная разработка](#локальная-разработка-docker-dev-стек) | `docker compose up`, порты |
| [Deploy (prod)](#deploy-production-style) | overlay `docker-compose.prod.yml` |
| [Тесты](#тесты) | unit + integration |
| [Архитектура](#архитектура-кратко) | upload → queue → worker; multi-tenant |

## Документация

- [docs/deployment.md](docs/deployment.md) — Docker Compose (dev vs prod), TLS, миграции
- [docs/security.md](docs/security.md) — секреты, reverse proxy, CORS, rate limits
- [docs/quotas.md](docs/quotas.md) — планы и лимиты usage
- [docs/runbook.md](docs/runbook.md) — 503 БД, Celery, метрики
- [docs/observability.md](docs/observability.md) — логи, Sentry, `/metrics`
- [docs/storage-lifecycle.md](docs/storage-lifecycle.md) — local vs S3, дедуп, AV

Шаблон env для продакшена (только плейсхолдеры): [.env.production.example](.env.production.example)

### Режимы: разработка vs продакшен

| | Локальная разработка | Продакшен (baseline) |
|--|----------------------|----------------------|
| **Compose** | `docker compose up --build` | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` |
| **Сеть БД/Redis** | Порты проброшены на хост (`5433`, `6380`) | Порты БД/Redis **не** публикуются (overlay) |
| **ENVIRONMENT** | `local` (в [backend/.env.docker](backend/.env.docker)) | `production` задаётся в [docker-compose.prod.yml](docker-compose.prod.yml) для `api`/`worker` |
| **Секреты** | dev-значения в `.env.docker` / override | только из секрет-хранилища, см. [.env.production.example](.env.production.example) |

Не используйте один только `docker compose up -d --build` без prod-overlay как схему для публичного интернета.

## Локальная разработка (Docker, dev-стек)

Требования: Docker Desktop.

```bash
docker compose up --build
```

После старта:
- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- Healthcheck API: `http://localhost:8000/healthz`

Сервисы поднимаются с healthchecks (`db`, `redis`, `api`), чтобы `api` и `frontend` не стартовали раньше зависимостей.

### Доступ с другого устройства в локальной сети

Frontend доступен с другого устройства по:
- `http://<IP_твоего_ПК>:3000`

Если открываешь frontend с другого устройства, задай API хост явно:

```bash
VITE_API_BASE=http://<IP_твоего_ПК>:8000/api/v1 docker compose up --build
```

### Первый запуск (миграции)
Контейнер `api` при старте делает `alembic upgrade head` автоматически.

## Быстрый старт (локально, без Docker)

### Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# подними Postgres с pgvector и выставь DATABASE_URL в backend/.env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host
```

Открой `http://localhost:3000`.

## Deploy (production-style)

Базовый `docker compose up` из корня репозитория **публикует порты Postgres и Redis на хост** — это удобно для локальной разработки, но не годится как единственная схема для публичного интернета. Для продакшена используйте overlay без публикации БД/Redis и задайте секреты через окружение или секрет-хранилище:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Секреты и переменные: [.env.production.example](.env.production.example). TLS — на reverse proxy; для корректного client IP за прокси задайте `USE_FORWARDED_HEADERS` и `TRUSTED_PROXY_IPS` (см. [docs/security.md](docs/security.md)).

Проверка после деплоя:
- `http://localhost:3000` — frontend
- `http://localhost:8000/healthz` — API health
- `docker compose ps` — статус контейнеров

Остановка:

```bash
docker compose down
```

## Тесты

### Backend unit tests

```bash
cd backend
C:\venvs\ec314\Scripts\python.exe -m unittest discover -s tests -v
```

Если есть `py` launcher:

```bash
py -3 -m unittest discover -s tests -v
```

### Backend integration test (auth -> upload -> search -> delete)

Скрипт сам поднимает `db_test` (Docker profile `test`) на `localhost:5433`, прогоняет миграции и запускает интеграционный тест.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-integration.ps1
```

### Frontend lint/build

```bash
cd frontend
npm run lint
npm run build
```

## Архитектура (кратко)

- **Multi-tenant:** данные scoped по `workspace_id` (заголовок `X-Workspace-Id`); см. [docs/security.md](docs/security.md).
- **Ingestion:** HTTP **upload** только сохраняет файл (storage), создаёт строку `documents` (`queued` / …) и ставит задачу Celery. **Парсинг, chunking, эмбеддинги и запись векторов в pgvector** выполняются в **worker**, не в обработчике upload.
- **Размерность эмбеддингов:** 384 (тот же эмбеддер, что и для поиска).
- **Production:** `INGESTION_ASYNC_ENABLED=1` обязателен (fail-fast в `startup_checks`). Синхронная индексация на upload — только `ENVIRONMENT=local` + `ALLOW_SYNC_INGESTION_FOR_DEV=1` + `INGESTION_ASYNC_ENABLED=0` (например тесты без worker).
- **Backfill embeddings:** `POST /api/v1/documents/reindex-embeddings` (JWT + `X-Workspace-Id`), если нужно дозаполнить `embedding_vector`.
- **Статусы ingestion / UI:** API `GET /documents/{id}/ingestion`, `GET /ingestion/jobs`, страница `/jobs` (фильтры по статусам).

### Индекс документации (SaaS-слой)

| Документ | Содержание |
|----------|------------|
| [docs/deployment.md](docs/deployment.md) | Compose dev vs prod, TLS, MinIO/S3, миграции |
| [docs/security.md](docs/security.md) | Секреты, CORS, rate limits, proxy, заголовки |
| [docs/quotas.md](docs/quotas.md) | Планы free/pro/team, usage, enforcement |
| [docs/runbook.md](docs/runbook.md) | 503 БД, очередь, 429, backup/restore |
| [docs/observability.md](docs/observability.md) | Логи, Sentry, `/metrics` |
| [docs/storage-lifecycle.md](docs/storage-lifecycle.md) | `storage_key`, S3, дедуп, soft-delete, AV |

## Описание проекта
Во многих компаниях сотрудники тратят много времени на:
- поиск нужной информации в документах,
- чтение длинных PDF и DOCX файлов,
- подготовку кратких выжимок,
- поиск конкретных условий, дат, сумм и названий компаний.

Этот проект решает данную проблему с помощью AI. Пользователь загружает документы в систему и может:
- выполнять семантический поиск,
- задавать вопросы по документам,
- получать ответы с указанием источников,
- получать краткое содержание документа.

## Цель проекта
Цель проекта — создать production-style AI Copilot для анализа бизнес-документов.

## MVP-функции
Первая версия системы включает:

- Регистрация и вход в систему
- Загрузка PDF и DOCX файлов
- Просмотр списка загруженных документов
- Семантический поиск по документам
- Чат с документами на основе RAG
- Ответы с указанием источников
- Генерация краткого summary документа

## Что будет добавлено позже

- OCR, извлечение сущностей, сравнение документов, feedback, расширенная аналитика

## Технологический стек
### Backend
- FastAPI
- PostgreSQL

### Frontend
- React

### ML / NLP
- sentence-transformers
- RAG
- LLM API

### Хранение и инфраструктура
- pgvector или Qdrant
- Redis
- Docker

## Как работает система

1. Пользователь входит и выбирает workspace (`X-Workspace-Id`).
2. **Upload:** файл → storage + запись документа + постановка задачи Celery (в prod).
3. **Worker:** извлечение текста → chunks → эмбеддинги → pgvector → статусы `queued` → … → `ready` / `failed`.
4. **Search / chat:** RAG по векторам в рамках workspace; LLM для ответа; учёт квот и rate limits ([docs/quotas.md](docs/quotas.md)).

## Структура репозитория

```text
enterprise-copilot/
├── backend/          # FastAPI, Celery worker, Alembic
├── frontend/         # Next.js
├── docs/             # deployment, security, quotas, runbook, observability, storage
├── docker-compose.yml
├── docker-compose.prod.yml
└── README.md
```

Подробнее об обзоре системы: [docs/architecture.md](docs/architecture.md).
