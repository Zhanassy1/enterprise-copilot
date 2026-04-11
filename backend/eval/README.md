# Offline retrieval evaluation

## Что **можно** хранить в Git

| Тип | Описание |
|-----|----------|
| **Код оценщика** | `app/eval/*.py`, `app/services/retrieval_metrics.py`, пайплайн в `vector_search` / `retrieval/` |
| **Скрипт запуска** | `scripts/eval_retrieval.py` |
| **Конфиг** | `retrieval_eval.config.json` — пути к gold/baseline (относительно `backend/`), опционально `ranked_baseline_relative`, `k_list`, `regression_epsilon` |
| **Dummy / synthetic gold** | Короткий JSONL с **выдуманными** формулировками запросов и фиксированными `chunk_id` из `app/eval/seed_corpus.py` (например `retrieval_gold.jsonl`, `retrieval_gold_smoke.jsonl`) |
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

Быстрая проверка на одной строке gold: `--gold eval/retrieval_gold_smoke.jsonl`.

Обновление baseline после осознанного улучшения качества: зафиксировать новые числа в `baseline_metrics.json` и при необходимости в `baseline_metrics_ranked.json` отдельным коммитом.

## Интеграционные тесты (pytest)

- Маркер `retrieval_regression`: `tests/test_retrieval_eval_integration.py` (нужны `RUN_INTEGRATION_TESTS=1`, Postgres+pgvector).
- Быстрый smoke на одной строке gold: `RUN_RETRIEVAL_SMOKE=1` (тот же модуль).
- Нагрузочные сценарии (`tests/test_perf_load.py`, маркер `perf`): `RUN_PERF_TESTS=1`; для сценариев с HTTP+БД дополнительно `RUN_INTEGRATION_TESTS=1`. Пример:

```text
set RUN_PERF_TESTS=1
set RUN_INTEGRATION_TESTS=1
pytest tests/test_perf_load.py -v -m perf
```
