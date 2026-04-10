# Архитектура Enterprise Copilot

**Продуктовый контекст:** то же позиционирование, что в [README.md](../README.md) — multi-tenant copilot с UI, квотами и аудитом.

Система для поиска и ответов по корпоративным документам с **изоляцией по workspace** и **асинхронной индексацией** в production.

## Поток данных (production)

1. Пользователь загружает файл через API (`POST /documents/upload`).
2. API сохраняет объект в storage, пишет строки `documents` и `ingestion_jobs`, **коммитит** транзакцию, ставит задачу Celery `ingest_document_task` (не индексирует в HTTP).
3. **Worker** извлекает текст, режет на chunks, считает embeddings, пишет в PostgreSQL (**pgvector**).
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

Слой **generic hybrid** (`app/services/retrieval/generic_hybrid.py`): dense pgvector + полнотекст (tsvector) + RRF. Поверх него **domain rules** (`app/services/retrieval/domain_rules.py`): эвристики по intent (цена / неустойка / расторжение и т.д.), порог `retrieval_min_score`, dedup почти дубликатов; веса вынесены в `RetrievalRuleWeights` (`app/core/settings/retrieval_rules.py`, поле `retrieval_domain_rules` в настройках). Далее общий пайплайн RAG в `rag_retrieval.py`: опциональный cross-encoder rerank, compaction сниппетов, пост-правила для «цена договора» (`nlp.py`).

**Offline eval:** золотой набор `backend/eval/retrieval_gold.jsonl`, эталон метрик `backend/eval/baseline_metrics.json`, прогон `python scripts/eval_retrieval.py` (нужны `DATABASE_URL`, после `python scripts/eval_retrieval.py --seed` — `RETRIEVAL_EVAL_WORKSPACE_ID`). Регрессия: `pytest tests/test_retrieval_eval_integration.py` при `RUN_INTEGRATION_TESTS=1` (входит в CI job с Postgres).

## Связанные документы

- [product-glossary.md](product-glossary.md) — workspace, роли, план, задача индексации  
- [WORKSPACE_ROUTING.md](WORKSPACE_ROUTING.md) — маршруты и tenant scope  
- [deployment.md](deployment.md) — dev vs prod  
- [storage-lifecycle.md](storage-lifecycle.md) — хранение файлов  
