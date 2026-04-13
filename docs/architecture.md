# Архитектура Enterprise Copilot

**Продуктовый контекст:** то же позиционирование, что в [README.md](../README.md) — multi-tenant copilot с UI, квотами и аудитом.

Система для поиска и ответов по корпоративным документам с **изоляцией по workspace** и **асинхронной индексацией** в production.

## Поток данных (production)

1. Пользователь загружает файл через API (`POST /documents/upload`).
2. API сохраняет объект в storage, в **одном commit до постановки в брокер** пишет `documents`, `ingestion_jobs` и строки **`usage_events`** для учёта upload (идемпотентно по `idempotency_key`), затем ставит задачу Celery `ingest_document_task` (не индексирует в HTTP). Старые pending-строки **`usage_outbox`** (если остались от прежних версий) подхватывает задача **`maintenance.process_usage_outbox`** (beat: раз в минуту). Если enqueue в брокер падает после commit, doc/job помечаются failed и соответствующие **`usage_events`** для этого upload **удаляются** — без «тихого» расхождения doc vs metering.
3. **Worker** извлекает текст, режет на chunks, пишет строки чанков с `embedding_vector` = NULL, **коммитит**, затем считает embeddings **батчами** (`EMBEDDING_BATCH_SIZE`, коммит после каждого батча). При сбое повторная задача может **дозаполнить** только NULL-векторы без повторного PDF/OCR, если не менялись `CHUNK_SIZE`/`CHUNK_OVERLAP` (fingerprint в `documents.extraction_meta.indexing`). Пишет в PostgreSQL (**pgvector**).
4. Поиск и чат обращаются к чанкам с фильтром `workspace_id`; применяются квоты и rate limits.

PDF: эвристическая классификация (text vs scanned/mixed), опциональный **AWS Textract** для слабого native-текста, метрика **extraction coverage** в `documents.extraction_meta`. Подробности: [ingestion-pdf.md](ingestion-pdf.md).

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

## Retrieval (поиск по чанкам)

Слой **generic hybrid** (`app/services/retrieval/generic_hybrid.py`): dense pgvector + полнотекст (tsvector) + RRF. Поверх него **domain rules** (`app/services/retrieval/domain_rules.py`): эвристики по intent (цена / неустойка / расторжение и т.д.), порог `retrieval_min_score`, dedup почти дубликатов; веса вынесены в `RetrievalRuleWeights` (`app/core/settings/retrieval_rules.py`, поле `retrieval_domain_rules` в настройках). Далее общий пайплайн RAG в `rag_retrieval.py`: опциональный cross-encoder rerank (параметры инференса — device, batch, max length и таймаут predict — в `LLMSettings`; latency и таймауты в `/metrics`), compaction сниппетов, пост-правила для «цена договора» (`nlp.py`).

**Offline eval:** конфиг `backend/eval/retrieval_eval.config.json`, скрипт `backend/scripts/eval_retrieval.py`, синтетический gold (без ПДн) — политика и запуск: [backend/eval/README.md](../backend/eval/README.md). Регрессия: `pytest tests/test_retrieval_eval_integration.py` при `RUN_INTEGRATION_TESTS=1` (входит в CI job с Postgres).

## Связанные документы

- [product-glossary.md](product-glossary.md) — workspace, роли, план, задача индексации  
- [WORKSPACE_ROUTING.md](WORKSPACE_ROUTING.md) — маршруты и tenant scope  
- [deployment.md](deployment.md) — dev vs prod  
- [storage-lifecycle.md](storage-lifecycle.md) — хранение файлов  
