# План зрелости SaaS — статус по шагам

Легенда: **Done** — реализовано и покрыто тестами/доками где уместно; **Partial** — есть ядро, возможны расширения; **Planned** — в бэклоге / документировано, кода мало.

| # | Шаг | Статус |
|---|-----|--------|
| **Этап 1** | | |
| 1 | README: позиционирование production-style SaaS, async flow, без legacy MVP-формулировок | **Done** |
| 2 | Индекс документации (`docs/*`, навигация) | **Done** |
| **Этап 2** | | |
| 3 | Dev `docker-compose.yml` / prod overlay, внутренние DB/Redis/worker, без dev credentials в prod | **Done** |
| 4 | Startup fail-fast (`startup_checks`), unit tests | **Done** |
| **Этап 3** | | |
| 5 | Audit роутов и Celery (`docs/WORKSPACE_ROUTING.md`) | **Done** |
| 6 | Cross-workspace integration tests + unit ingestion `workspace_mismatch` | **Partial** (интеграция search по chunk isolation — опирается на `SearchService` + ручной прогон; worker покрыт unit) |
| **Этап 4** | | |
| 7 | Async ingestion production path; sync только dev (`ALLOW_SYNC_INGESTION_FOR_DEV`) | **Done** |
| 8 | Job/document статусы, API ingestion, `/jobs` UI, retry/backoff | **Done** |
| **Этап 5** | | |
| 9 | Quotas enforcement (upload, concurrent jobs, RAG, tokens, rerank) | **Done** |
| 10 | Usage ledger (`usage_events`, billing stubs) | **Done** |
| **Этап 6** | | |
| 11 | Refresh tokens, rotation, logout, reuse detection | **Done** |
| 12 | Email verification, password reset, revoke refresh on reset | **Partial** (есть токены и flow; e2e email зависит от провайдера) |
| 13 | Upload validation (MIME, sniffing, size, pages, encrypted PDF, double ext) | **Done** |
| 14 | Rate limits по группам (auth, upload, RAG), plan-aware | **Done** |
| **Этап 7** | | |
| 15 | Storage `local` \| `s3`, `storage_key`, presigned, tests | **Done** |
| 16 | Soft-delete, retention/dedup/AV policy points | **Partial** (soft-delete/dedup/AV hooks есть; расширенные cleanup jobs — по мере надобности) |
| **Этап 8** | | |
| 17 | Audit events + admin-safe API | **Done** |
| 18 | Observability: structured logs, request id, Sentry tags, `/metrics`, runbook | **Done** |
| **Этап 9** | | |
| 19 | Workspace UI: switcher, billing, role-aware nav, audit (admin) | **Partial** — см. [ниже](#19-frontend-saas-почему-partial) |
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

Уже есть: **workspace switcher** (`WorkspaceSwitcher`), страницы **документы / поиск / чат / billing / jobs**, клиент ходит с `X-Workspace-Id`, billing и jobs отражают multi-tenant сценарий.

Не доведено до «полного SaaS-шела»:

1. **Нет отдельной страницы Audit** — в `api-client` есть `listAuditLogs` / `listAuditLogsAdmin`, но в `frontend/src/app` нет маршрута вроде `/audit` и пункта в сайдбаре; админский просмотр логов не выведен в UI.
2. **Навигация не role-aware** — сайдбар одинаков для всех ролей; ограничения viewer (например upload) обрабатываются **на API (403)**, а не скрытием/дизейблом действий во фронте.
3. **Нет UI для team / members / invitations** — бэкенд workspace API сейчас минимален (список workspace); отдельных экранов приглашений, ролей участников, billing-организации как в классическом B2B SaaS нет.
4. **Нет e2e-покрытия** фронта (Playwright есть в зависимостях, сценарии multi-workspace можно расширять).

Итого: ядро tenant-aware UI есть, но **админский audit, управление командой и UX по ролям** — следующий слой; поэтому шаг 19 помечен **Partial**.
