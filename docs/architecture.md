# Архитектура Enterprise Copilot

Система для поиска и ответов по корпоративным документам с **изоляцией по workspace** и **асинхронной индексацией** в production.

## Поток данных (production)

1. Пользователь загружает файл через API (`POST /documents/upload`).
2. API сохраняет объект в storage, пишет строки `documents` и `ingestion_jobs`, **коммитит** транзакцию, ставит задачу Celery `ingest_document_task` (не индексирует в HTTP).
3. **Worker** извлекает текст, режет на chunks, считает embeddings, пишет в PostgreSQL (**pgvector**).
4. Поиск и чат обращаются к чанкам с фильтром `workspace_id`; применяются квоты и rate limits.

В **local dev** опционально доступна синхронная индексация в процессе API (флаги `ENVIRONMENT=local`, `ALLOW_SYNC_INGESTION_FOR_DEV`, `INGESTION_ASYNC_ENABLED=0`) — не используется в production.

## Компоненты

| Компонент | Роль |
|-----------|------|
| Frontend (Next.js) | Auth, документы, поиск, чат, billing/jobs UI |
| API (FastAPI) | JWT, workspace deps, upload metadata, RAG |
| Worker (Celery) | Ingestion, retry, опционально maintenance |
| PostgreSQL | Данные, pgvector |
| Redis | Broker Celery |
| Object storage | Local или S3/MinIO (`storage_key`) |

## Связанные документы

- [WORKSPACE_ROUTING.md](WORKSPACE_ROUTING.md) — маршруты и tenant scope  
- [deployment.md](deployment.md) — dev vs prod  
- [storage-lifecycle.md](storage-lifecycle.md) — хранение файлов  
