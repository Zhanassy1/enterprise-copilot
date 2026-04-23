# Offline retrieval evaluation

## Что **можно** хранить в Git

| Тип | Описание |
|-----|----------|
| **Код оценщика** | `app/eval/*.py`, `app/services/retrieval_metrics.py`, `app/eval/answer_metrics.py`, пайплайн в `vector_search` / `retrieval/` |
| **Скрипты запуска** | `scripts/eval_retrieval.py` (векторный этап + baseline), `scripts/eval_rag_quality.py` (сводный отчёт), `scripts/eval_answer_synthesis.py` (ассерт gold + optional LLM-path / judge) |
| **Конфиг** | `retrieval_eval.config.json` — пути к gold/baseline (относительно `backend/`), `answer_gold_relative`, опционально `ranked_baseline_relative`, `k_list`, `regression_epsilon` |
| **Dummy / synthetic gold** | `retrieval_gold.jsonl` / `retrieval_gold_smoke.jsonl` — поля `query_id`, `query_text`, `gold_chunk_ids`; опционально **`query_type`** (строка сегмента для стратифицированных метрик) и/или **`tags`** (массив; если `query_type` нет, сегмент берётся по первому тегу в лексикографическом порядке). `answer_gold.jsonl` — см. [Answer quality eval: scope](#answer-quality-eval-scope) ниже; фиксированные `chunk_id` из `app/eval/seed_corpus.py` |
| **Chunking fixture** | `eval/fixtures/chunking_golden.txt` + тест `tests/test_chunking_golden.py` (регрессия `chunk_text` без моков) |
| **Baseline метрик** | `baseline_metrics.json` — пороги для **векторного** этапа (`run_search_chunks_eval`); `baseline_metrics_ranked.json` — для полного пути `retrieve_ranked_hits` при выключенном cross-encoder (компактация сниппетов + правила contract-value). Сегментные метрики (`mrr__<segment>`, …) в отчёте появляются при наличии `query_type` или `tags` в gold; **регрессия по baseline** сравнивает только ключи, явно перечисленные в JSON baseline. |

## Что **нельзя** коммитить

- Реальные документы из production, сканы, скриншоты, чеки, паспорта.
- Разметку с **ПДн** (имена, адреса, телефоны, реальные суммы из клиентских договоров).
- Большие выгрузки «как в проде» — только во внешнем защищённом хранилище с контролем доступа.

Для локальной разметки с чувствительными данными используйте файлы с суффиксом `*_local.jsonl` — они перечислены в `.gitignore` и не попадут в репозиторий.

## Answer quality eval: scope

`run_answer_quality_eval` ([`app/eval/answer_eval_runner.py`](../app/eval/answer_eval_runner.py)) по умолчанию **детерминированный** (`build_answer` с `extractive_only=True`, без LLM) и меряет:

- **Retrieval-часть:** все gold-чанки в top-K (поле `source_gold_all_in_top_k_rate` — фактически согласованность ранжирования с gold, а не «качество формулировки»);
- **Подстроки в ответе:** `must_appear_in_answer`;
- **Лексическое «заземление»:** `grounded_line_ratio` — пересечение непустых строк ответа с телами hit’ов, **не** entailment и **не** human/LLM faithfulness.

**Опциональные поля** в `answer_gold.jsonl` (пустые/отсутствующие = не участвуют в агрегате) задают: `must_cover` (полнота по подстрокам/темам), `forbidden_phrases` (все такие фразы должны **отсутствовать**), `reference_answer` (токенный F1 к эталону для дымовой согласованности), `required_evidence_chunk_ids` (все эти `chunk_id` должны войти в **provenance** — какие чанки реально использовал `build_answer_with_provenance`).

Этого **недостаточно** для публикации как «RAG faithfulness» в смысле research: для этого нужны отдельные разметка, LLM-judge/NLI, или [human eval] — см. [scripts/eval_answer_synthesis.py](scripts/eval_answer_synthesis.py) (`--llm-answer` при `RUN_ANSWER_LLM_EVAL=1` и с ключом API).

## Запуск

Из каталога `backend/` (нужны миграции и `DATABASE_URL`):

```text
python scripts/eval_retrieval.py --seed
set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid из JSON>
python scripts/eval_retrieval.py
python scripts/eval_retrieval.py --compare-baseline
```

**Ablation / tuning (патч настроек на один прогон):** файл JSON с полями вроде `retrieval_rrf_k`, `retrieval_candidate_multiplier` (см. `RetrievalEvalParamOverrides` в `app/eval/retrieval_eval_harness.py`):

```text
python scripts/eval_retrieval.py --overrides-json path/to/patch.json
```

**Grid search с train/holdout** по `query_id` (печать лучших параметров и holdout-метрик, baseline не пишет):

```text
python scripts/tune_retrieval.py --gold eval/retrieval_gold.jsonl --train-fraction 0.7 --random 30 --seed 1
```

Единый отчёт (вектор, ranked rerank-off, answer metrics; опционально paired rerank gain):

```text
python scripts/eval_rag_quality.py --seed
set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid>
python scripts/eval_rag_quality.py
python scripts/eval_rag_quality.py --rerank-gain
```

`--seed` печатает JSON с `workspace_id` и `user_id` (владелец seeded workspace). Для чужого workspace можно задать `RETRIEVAL_EVAL_USER_ID` (иначе берётся `owner_user_id`).

**Answer synthesis (расширенные метрики + опциональный LLM-путь):**

```text
python scripts/eval_answer_synthesis.py --seed
set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid>
python scripts/eval_answer_synthesis.py
python scripts/eval_answer_synthesis.py --llm-answer
set RUN_ANSWER_LLM_EVAL=1
python scripts/eval_answer_synthesis.py --llm-answer
python scripts/eval_answer_synthesis.py --llm-answer --judge
```

`--llm-answer` вызывает `build_answer` без `extractive_only` (нужен `llm_api_key`); `RUN_ANSWER_LLM_EVAL=1` — явное подтверждение. `--judge` добавляет оценку LLM-as-judge (доп. вызов API).

**Rerank gain:** `run_rerank_gain_eval` сравнивает MRR / Recall@k / nDCG для `retrieve_ranked_hits` с `reranker_enabled` off vs on. В CI по умолчанию cross-encoder не грузится: `tests/test_rerank_gain_eval.py` с патчем `rerank_hits` проверяет, что paired-прогон не ломает wiring. Реальная модель: `RUN_RERANK_EVAL=1 pytest tests/test_rerank_gain_eval.py -m rerank_gain` (долго, загрузка весов).

Быстрая проверка на одной строке gold: `--gold eval/retrieval_gold_smoke.jsonl`.

Обновление baseline после осознанного улучшения качества: зафиксировать новые числа в `baseline_metrics.json` и при необходимости в `baseline_metrics_ranked.json` отдельным коммитом.

## Интеграционные тесты (pytest)

- Маркер `retrieval_regression`: `tests/test_retrieval_eval_integration.py`, `tests/test_answer_eval_integration.py`, `tests/test_rerank_gain_eval.py` (нужны `RUN_INTEGRATION_TESTS=1`, Postgres+pgvector).
- Быстрый smoke на одной строке gold: `RUN_RETRIEVAL_SMOKE=1` (тот же модуль).
- Юнит без БД: `tests/test_answer_metrics.py`, `tests/test_chunking_golden.py`, `tests/test_build_answer_provenance.py`.
- Нагрузочные сценарии (`tests/test_perf_load.py`, маркер `perf`): `RUN_PERF_TESTS=1`; для сценариев с HTTP+БД дополнительно `RUN_INTEGRATION_TESTS=1`. Пример:

```text
set RUN_PERF_TESTS=1
set RUN_INTEGRATION_TESTS=1
pytest tests/test_perf_load.py -v -m perf
```
