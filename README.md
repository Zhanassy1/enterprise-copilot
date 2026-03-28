# Enterprise Copilot

Enterprise Copilot — это AI-ассистент для бизнеса, который помогает работать с корпоративными документами быстрее и удобнее.

[![CI](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Zhanassy1/enterprise-copilot/actions/workflows/ci.yml)

## Документация

- [docs/deployment.md](docs/deployment.md) — Docker Compose (dev vs prod), TLS, миграции
- [docs/security.md](docs/security.md) — секреты, reverse proxy, CORS, rate limits
- [docs/quotas.md](docs/quotas.md) — планы и лимиты usage
- [docs/runbook.md](docs/runbook.md) — 503 БД, Celery, метрики
- [docs/observability.md](docs/observability.md) — логи, Sentry, `/metrics`
- [docs/storage-lifecycle.md](docs/storage-lifecycle.md) — local vs S3, дедуп, AV

Шаблон env для продакшена (только плейсхолдеры): [.env.production.example](.env.production.example)

## Быстрый старт (Docker)

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

## Текущее состояние MVP

- **Auth**: `/api/v1/auth/register`, `/api/v1/auth/login` (JWT bearer)
- **Documents**: список + upload + delete
- **Search**: `/api/v1/search` (pgvector cosine)

### `embedding_vector` и ingestion

**Upload** сохраняет файл в storage, создаёт запись `documents` со статусом `queued` и (при `INGESTION_ASYNC_ENABLED=1`) ставит задачу Celery. **Парсинг, chunking и запись `embedding_vector`** выполняются в **worker**, а не в HTTP-обработчике upload.

Размерность эмбеддингов **384** (тот же эмбеддер, что и для поиска).

Если остались **старые** chunks с `embedding_vector IS NULL`, вызови (с JWT и заголовком `X-Workspace-Id` для workspace):

```http
POST /api/v1/documents/reindex-embeddings
```

При async ingestion задача уходит в очередь; в синхронном режиме (`INGESTION_ASYNC_ENABLED=0`) ответ содержит `updated` сразу.

Нужны **PostgreSQL + pgvector**, **Redis** (для Celery) и миграции: `alembic upgrade head`.

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
Функции, которые не входят в MVP, но планируются в следующих версиях:

- OCR для сканированных документов
- Извлечение сущностей (даты, суммы, компании, номера контрактов)
- Сравнение документов
- Сбор пользовательского feedback
- Мониторинг и аналитика
- Поддержка рабочих пространств и ролей пользователей

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
1. Пользователь загружает документ
2. Backend извлекает текст из документа
3. Текст разбивается на фрагменты (chunks)
4. Для каждого фрагмента создаются embeddings
5. Фрагменты сохраняются в векторное хранилище
6. Пользователь выполняет поиск или задает вопрос
7. Система находит наиболее релевантные фрагменты
8. LLM формирует ответ на основе найденного контекста
9. Пользователь получает ответ с указанием источников

## Архитектура
Проект состоит из следующих основных частей:

### Frontend
- Страница регистрации и входа
- Страница загрузки документов
- Страница списка документов
- Страница поиска
- Страница чата

### Backend
- Auth API
- API загрузки документов
- Сервис парсинга документов
- Сервис разбиения текста на chunks
- Сервис embeddings
- Сервис семантического поиска
- RAG pipeline
- Сервис генерации summary

### База данных
- Пользователи
- Документы
- Фрагменты документов
- Сессии чата
- Сообщения чата

## Основной сценарий использования
1. Пользователь входит в систему
2. Загружает один или несколько документов
3. Система обрабатывает документы
4. Пользователь ищет нужную информацию
5. Пользователь задает вопрос по документам
6. Система возвращает ответ и показывает источники

## Структура проекта
```text
enterprise-copilot/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── docs/
│   └── architecture.md
│
├── README.md
└── .gitignore


Первый крупный шаг — multi-tenant core. Я бы добавил таблицы:

workspaces
workspace_members
workspace_invitations
roles

После этого все сущности должны привязываться не к owner_id, а к workspace_id. Пользователь может принадлежать нескольким workspace. Роли минимум: owner, admin, member, viewer. Это самое важное архитектурное изменение. Без него это не SaaS, а personal productivity app.

Второй шаг — async ingestion pipeline. Загрузка должна только:

принять файл,
сохранить его в object storage,
создать запись document(status='queued'),
отправить job в очередь.

А уже worker отдельно делает parsing → chunking → embeddings → indexing → status update. Тогда у тебя появится нормальный UX и отказоустойчивость.

Третий шаг — document lifecycle model. Я бы добавил:

status: queued / processing / ready / failed
error_message
file_size_bytes
sha256
page_count
language
parser_version
indexed_at

Это сильно поднимает maturity проекта.

Четвертый шаг — object storage abstraction. Сделай интерфейс StorageService и две реализации:

local filesystem storage
S3-compatible storage

Тогда локально все продолжит работать, а в “production mode” ты сможешь перейти на MinIO/S3 без рефакторинга роутов.

Пятый шаг — RAG quality layer. Я бы внес:

BM25/keyword retrieval alongside vector retrieval
reranker
deduplication near-identical chunks
citations с page/paragraph anchors
отдельные prompt templates
offline eval set из 30–50 бизнес-вопросов

Сейчас у тебя уже есть decision logic с answer_threshold, clarify_threshold, retrieval_min_score, и это хорошая база. Но дальше нужна именно проверяемая retrieval quality, а не только heuristics.

Шестой шаг — usage/billing readiness. Даже если платежей пока нет, я бы добавил:

usage_events
учет числа документов
учет search/chat запросов
приблизительный token accounting
лимиты по планам

Это нужно не только для монетизации, но и чтобы понимать себестоимость пользователя.

Седьмой шаг — security hardening. Минимум:

refresh tokens
password reset flow
email verification
stricter upload validation
MIME sniffing, а не только extension/content-type
per-user and per-IP rate limiting
CSRF strategy if later появятся cookie sessions
audit logs для удаления документов и входов

Восьмой шаг — observability. Сейчас есть debug_log, что уже полезно, и есть готовность к operational handling. Но для SaaS я бы добавил structured JSON logs, request IDs, latency metrics, tracing, error reporting и dashboards по jobs/search/chat.

Девятый шаг — test maturity. У тебя уже есть unit и integration CI — это отличный знак. Дальше я бы наращивал:

permission tests
ingestion retry tests
search relevance regression tests
contract tests для API
migration smoke tests
e2e UI tests

Наличие CI сейчас — плюс. Но полноценный SaaS обычно живет на более широком наборе автопроверок.

Что бы я конкретно поменял в коде прямо сейчас.

Я бы убрал прямое обновление embedding_vector через raw SQL inside request handler и вынес indexing в сервис/worker. Это сейчас рабочее решение, но оно смешивает upload orchestration, ML, persistence и indexing в одном endpoint.

Я бы ввел service layer типа:

DocumentIngestionService
DocumentIndexingService
SearchService
ChatService

Сейчас роуты уже не ужасные, но логики в них все еще многовато, особенно в documents/chat/search.

Я бы разделил DocumentChunk.embedding и реальное embedding_vector более аккуратно. Сейчас по модели видно временную конструкцию: текстовое поле как placeholder и реальный vector-column через migration/raw SQL. Для MVP допустимо, но дальше это надо сделать чище, чтобы ORM и schema лучше совпадали.

Я бы поменял security default values и сделал fail-fast для production. Например, если environment=production и secret_key остался дефолтным — приложение должно не стартовать. То же касается пустого LLM key, если включен режим summary/chat через внешний LLM.

Я бы расширил модели чата. Сейчас сессии и сообщения есть, это хорошо, но дальше полезно добавить:

model used
retrieval metadata
latency
token usage
feedback on answer
answer provenance version

Это сильно поможет анализировать качество.