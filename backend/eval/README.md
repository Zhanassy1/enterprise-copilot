# Offline retrieval evaluation

## Что **можно** хранить в Git

| Тип | Описание |
|-----|----------|
| **Код оценщика** | `app/eval/*.py`, `app/services/retrieval_metrics.py`, `app/eval/answer_metrics.py`, пайплайн в `vector_search` / `retrieval/` |
| **Скрипты запуска** | `scripts/eval_retrieval.py` (векторный этап + baseline), `scripts/eval_rag_quality.py` (сводный отчёт) |
| **Конфиг** | `retrieval_eval.config.json` — пути к gold/baseline (относительно `backend/`), `answer_gold_relative`, опционально `ranked_baseline_relative`, `k_list`, `regression_epsilon` |
| **Dummy / synthetic gold** | `retrieval_gold.jsonl` / `retrieval_gold_smoke.jsonl`; `answer_gold.jsonl` (обязательные подстроки в extractive-ответе, проверка top-K источников); фиксированные `chunk_id` из `app/eval/seed_corpus.py` |
| **Chunking fixture** | `eval/fixtures/chunking_golden.txt` + тест `tests/test_chunking_golden.py` (регрессия `chunk_text` без моков) |
| **Baseline метрик** | `baseline_metrics.json` — пороги для **векторного** этапа (`run_search_chunks_eval`); `baseline_metrics_ranked.json` — для полного пути `retrieve_ranked_hits` при выключенном cross-encoder (компактация сниппетов + правила contract-value) |

## Что **нельзя** коммитить

- Реальные документы из production, сканы, скриншоты, чеки, паспорта.
- Разметку с **ПДн** (имена, адреса, телефоны, реальные суммы из клиентских договоров).
- Большие выгрузки «как в проде» — только во внешнем защищённом хранилище с контролем доступа.

Для локальной разметки с чувствительными данными используйте файлы с суффиксом `*_local.jsonl` — они перечислены в `.gitignore` и не попадут в репозиторий.

## Запуск

Из каталога `backend/` (нужны миграции и `DATABASE_URL`):

```text
python scripts/eval_retrieval.py --seed
set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid из JSON>
python scripts/eval_retrieval.py
python scripts/eval_retrieval.py --compare-baseline
```

Единый отчёт (вектор, ranked rerank-off, answer metrics; опционально paired rerank gain):

```text
python scripts/eval_rag_quality.py --seed
set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid>
python scripts/eval_rag_quality.py
python scripts/eval_rag_quality.py --rerank-gain
```

`--seed` печатает JSON с `workspace_id` и `user_id` (владелец seeded workspace). Для чужого workspace можно задать `RETRIEVAL_EVAL_USER_ID` (иначе берётся `owner_user_id`).

**Rerank gain:** `run_rerank_gain_eval` сравнивает MRR / Recall@k / nDCG для `retrieve_ranked_hits` с `reranker_enabled` off vs on. В CI по умолчанию cross-encoder не грузится: `tests/test_rerank_gain_eval.py` с патчем `rerank_hits` проверяет, что paired-прогон не ломает wiring. Реальная модель: `RUN_RERANK_EVAL=1 pytest tests/test_rerank_gain_eval.py -m rerank_gain` (долго, загрузка весов).

Быстрая проверка на одной строке gold: `--gold eval/retrieval_gold_smoke.jsonl`.

Обновление baseline после осознанного улучшения качества: зафиксировать новые числа в `baseline_metrics.json` и при необходимости в `baseline_metrics_ranked.json` отдельным коммитом.

## Интеграционные тесты (pytest)

- Маркер `retrieval_regression`: `tests/test_retrieval_eval_integration.py`, `tests/test_answer_eval_integration.py`, `tests/test_rerank_gain_eval.py` (нужны `RUN_INTEGRATION_TESTS=1`, Postgres+pgvector).
- Быстрый smoke на одной строке gold: `RUN_RETRIEVAL_SMOKE=1` (тот же модуль).
- Юнит без БД: `tests/test_answer_metrics.py`, `tests/test_chunking_golden.py`.
- Нагрузочные сценарии (`tests/test_perf_load.py`, маркер `perf`): `RUN_PERF_TESTS=1`; для сценариев с HTTP+БД дополнительно `RUN_INTEGRATION_TESTS=1`. Пример:

```text
set RUN_PERF_TESTS=1
set RUN_INTEGRATION_TESTS=1
pytest tests/test_perf_load.py -v -m perf
```
