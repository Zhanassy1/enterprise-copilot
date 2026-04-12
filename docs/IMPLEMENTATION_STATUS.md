# План зрелости SaaS — статус по шагам

Легенда: **Done** — реализовано и покрыто тестами/доками где уместно; **Partial** — есть ядро, возможны расширения; **Planned** — в бэклоге / документировано, кода мало.

**Продуктовый** обзор возможностей, таблица «что работает / ограничения» и краткий roadmap (near/long-term): [README.md](../README.md). Здесь — **нумерованный чеклист** зрелости; формулировки согласованы с README, без дублирования продуктового текста там.

| # | Шаг | Статус |
|---|-----|--------|
| **Этап 1** | | |
| 1 | README: product entrypoint, async ingestion, docs index, roadmap | **Done** |
| 2 | Индекс документации (`docs/*`, навигация) | **Done** |
| **Этап 2** | | |
| 3 | Dev `docker-compose.yml`; prod overlay **minimal** (`docker-compose.prod.yml`); опционально третий файл **`docker-compose.prod.hardened.yml`** и профиль **hardened** — [hardened-deploy.md](hardened-deploy.md); внутренние DB/Redis/worker, без dev credentials в prod | **Done** |
| 4 | Startup fail-fast (`startup_checks`), unit tests | **Done** |
| **Этап 3** | | |
| 5 | Audit роутов и Celery (`docs/WORKSPACE_ROUTING.md`) | **Done** |
| 6 | Cross-workspace integration tests + unit ingestion `workspace_mismatch` | **Done** — `tests/test_cross_workspace_access.py` + `test_ingestion_task_unit.py` (локально/CI: `RUN_INTEGRATION_TESTS=1`, `docker compose --profile test up db_test`, см. README Tests) |
| **Этап 4** | | |
| 7 | Async ingestion production path; sync только dev (`ALLOW_SYNC_INGESTION_FOR_DEV`) | **Done** |
| 8 | Job/document статусы, API ingestion, `/jobs` UI, retry/backoff, CI async smoke (`backend-async-smoke`, commit до enqueue) | **Done** |
| **Этап 5** | | |
| 9 | Quotas enforcement (upload, concurrent jobs, RAG, tokens, rerank) | **Done** |
| 10 | Usage ledger: **`usage_events`**, очередь намерений **`usage_outbox`** → идемпотентная проекция (см. [quotas.md](quotas.md), `usage_metering` / maintenance drain) | **Done** |
| **Этап 6** | | |
| 11 | Refresh tokens, rotation, logout, reuse detection | **Done** |
| 12 | Email verification, password reset, revoke refresh on reset | **Done** (HTTP e2e с capture) — `tests/test_email_e2e_flow.py` + `test_email_capture.py`; production SMTP/Mailpit — см. `docs/email-testing.md` |
| 13 | Upload validation (MIME, sniffing, size, pages, encrypted PDF, double ext) | **Done** |
| 14 | Rate limits по группам (auth, upload, RAG), plan-aware | **Done** |
| **Этап 7** | | |
| 15 | Storage `local` \| `s3`, `storage_key`, presigned, tests | **Done** |
| 16 | Soft-delete, retention/dedup/AV policy points | **Partial** (soft-delete/dedup/AV hooks есть; расширенные cleanup jobs — по мере надобности) |
| **Этап 8** | | |
| 17 | Audit events + admin-safe API | **Done** |
| 18 | Observability: structured logs, request id, Sentry tags, `/metrics`, runbook | **Done** |
| **Этап 9** | | |
| 19 | Workspace UI: switcher, billing, role-aware nav, audit (admin) | **Partial** — см. [ниже](#19-frontend-saas-почему-partial); audit UI — **Done** |
| 20 | Jobs UI: список, статусы, ошибки | **Done** |
| **Этап 10** | | |
| 21 | Billing-ready: usage summary, plan, quotas API; опционально **Stripe** (Checkout, Customer Portal, webhooks, grace) — [billing.md](billing.md) | **Done** |
| **Этап 11** | | |
| 22 | Reverse proxy / TLS, профили **minimal** vs **hardened** ([deployment.md](deployment.md), [hardened-deploy.md](hardened-deploy.md), [security.md](security.md)) | **Done** |
| 23 | Security headers + tests (`test_production_headers.py`) | **Done** |
| **Этап 12** | | |
| 24 | Backup / restore / migration safety (`docs/runbook.md`) | **Done** |

Обновляйте этот файл при крупных изменениях архитектуры. Термины продукта: [product-glossary.md](product-glossary.md).

### 19 — Frontend SaaS: почему Partial

Уже есть: **workspace switcher** (карточка текущего **рабочего пространства**, бейдж роли — `workspace-switcher.tsx`), **NavRoleHint** в сайдбаре/моб. меню для **viewer**, **landing** с блоком «демо за 1 минуту», канонические страницы **`/w/:slug/...`** (документы, поиск, чат, команда, billing, jobs, audit), контекстные плашки workspace, **WorkspaceViewerBanner** на документах, поиске, jobs. **Команда (`/w/:slug/team`):** матрица ролей, список участников и приглашений из API, отправка / отзыв / повтор приглашения, смена ролей по правилам RBAC. Плоские маршруты (`/team`, `/billing`, …) редиректят на workspace-scoped URL.

Не доведено до «полного SaaS-шела»:

1. **Сайдбар** общий — пункты навигации не скрываются по роли; ограничения выражены дизейблами и плашками.
2. **E2E** — точечные сценарии (`workspace-evaluator`, invite flow); без полного регрессионного покрытия UI.

Итого: **multi-tenant контур команды и биллинга в UI** доведён (страница **План и лимиты** + опциональный Stripe при ключах; см. шаг 21); шаг 19 можно считать ближе к **Done** по продуктовым экранам, оставаясь **Partial** только там, где намеренно нет полного role-based nav.

### Roadmap (нарратив)

Near/long-term направления без дублирования таблицы выше — в [README.md](../README.md) (раздел *Roadmap* внизу файла).
