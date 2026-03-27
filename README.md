# Enterprise Copilot

Enterprise Copilot — это AI-ассистент для бизнеса, который помогает работать с корпоративными документами быстрее и удобнее.

## Быстрый старт (Docker)

Требования: Docker Desktop.

```bash
docker compose up --build
```

После старта:
- Frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- Healthcheck API: `http://localhost:8000/healthz`

Сервисы поднимаются с healthchecks (`db`, `redis`, `api`), чтобы `api` и `frontend` не стартовали раньше зависимостей.

### Доступ с другого устройства в локальной сети

Frontend уже слушает `0.0.0.0` (Vite host mode), поэтому можно открывать:
- `http://<IP_твоего_ПК>:5173`

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

Открой `http://localhost:5173`.

## Тесты

### Backend unit tests

```bash
cd backend
C:\venvs\ec314\Scripts\python.exe -m unittest discover -s tests -v
```

### Backend integration test (auth -> upload -> search -> delete)

Скрипт сам поднимает `db_test` (Docker profile `test`) на `localhost:5433`, прогоняет миграции и запускает интеграционный тест.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-integration.ps1
```

## Текущее состояние MVP

- **Auth**: `/api/v1/auth/register`, `/api/v1/auth/login` (JWT bearer)
- **Documents**: список + upload + delete
- **Search**: `/api/v1/search` (pgvector cosine)

### `embedding_vector`

При **upload** документа backend сразу пишет `embedding_vector` для каждого chunk (размерность **384**, тот же эмбеддер, что и для запроса поиска).

Если у тебя остались **старые** строки без вектора (NULL), один раз вызови (с тем же JWT, что и для API):

```http
POST /api/v1/documents/reindex-embeddings
```

Ответ: `{"updated": <число обновлённых chunks>}`.

Нужны работающий **PostgreSQL + расширение pgvector** и применённые миграции (`alembic upgrade head`).

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
