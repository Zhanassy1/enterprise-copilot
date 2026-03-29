# План зрелости SaaS — статус по шагам

Легенда: **Done** — реализовано и покрыто тестами/доками где уместно; **Partial** — есть ядро, возможны расширения; **Planned** — в бэклоге / документировано, кода мало.

| # | Шаг | Статус |
|---|-----|--------|
| **Этап 1** | | |
| 1 | README: product entrypoint, async ingestion, docs index, roadmap | **Done** |
| 2 | Индекс документации (`docs/*`, навигация) | **Done** |
| **Этап 2** | | |
| 3 | Dev `docker-compose.yml` / prod overlay, внутренние DB/Redis/worker, без dev credentials в prod | **Done** |
| 4 | Startup fail-fast (`startup_checks`), unit tests | **Done** |
| **Этап 3** | | |
| 5 | Audit роутов и Celery (`docs/WORKSPACE_ROUTING.md`) | **Done** |
| 6 | Cross-workspace integration tests + unit ingestion `workspace_mismatch` | **Done** — `tests/test_cross_workspace_access.py` + `test_ingestion_task_unit.py` (локально/CI: `RUN_INTEGRATION_TESTS=1`, `docker compose --profile test up db_test`, см. README Tests) |
| **Этап 4** | | |
| 7 | Async ingestion production path; sync только dev (`ALLOW_SYNC_INGESTION_FOR_DEV`) | **Done** |
| 8 | Job/document статусы, API ingestion, `/jobs` UI, retry/backoff, CI async smoke (`backend-async-smoke`, commit до enqueue) | **Done** |
| **Этап 5** | | |
| 9 | Quotas enforcement (upload, concurrent jobs, RAG, tokens, rerank) | **Done** |
| 10 | Usage ledger (`usage_events`, billing stubs) | **Done** |
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
| 21 | Billing-ready: usage summary, plan, quotas API | **Done** |
| **Этап 11** | | |
| 22 | Reverse proxy / TLS story (`docs/deployment.md`, `security.md`) | **Done** |
| 23 | Security headers + tests (`test_production_headers.py`) | **Done** |
| **Этап 12** | | |
| 24 | Backup / restore / migration safety (`docs/runbook.md`) | **Done** |

Обновляйте этот файл при крупных изменениях архитектуры.

### 19 — Frontend SaaS: почему Partial

Уже есть: **workspace switcher** (`frontend/src/components/layout/workspace-switcher.tsx`) с подписью ролей (владелец / администратор / участник / наблюдатель), **landing** (`frontend/src/components/landing/landing-page.tsx`, корень `/`), страницы **документы / поиск / чат / billing / jobs / audit** (`frontend/src/app/(app)/`), клиент ходит с `X-Workspace-Id`, billing и jobs отражают multi-tenant сценарий. **Audit:** маршрут `/audit`, список событий и вкладка расширенного просмотра для owner/admin (`frontend/src/app/(app)/audit/page.tsx`).

Не доведено до «полного SaaS-шела»:

1. **Навигация не полностью role-aware** — сайдбар общий для ролей; ограничения viewer (например upload) обрабатываются **на API (403)**, а не везде скрытием кнопок во фронте.
2. **Нет UI для team / members / invitations** — бэкенд workspace API минимален (список workspace); отдельных экранов приглашений и управления участниками нет.
3. **Нет широкого e2e-покрытия** фронта (Playwright в зависимостях; smoke — узкий сценарий).

Итого: **audit и product landing** закрывают часть gap; **team UX и role-aware действия** — следующий слой; шаг 19 остаётся **Partial**.
