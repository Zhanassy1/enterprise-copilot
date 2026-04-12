# Workspace routing inventory

Все workspace-scoped операции должны фильтровать по `workspace_id` из контекста (`WorkspaceReadAccess` / `WorkspaceWriteAccess` из `deps.py`) или из поля `IngestionJob.workspace_id` / `Document.workspace_id` в фоновых задачах. `owner_id` на моделях — метаданные/аудит, не путь авторизации.

## Slug и публичные URL

- У каждого `Workspace` есть уникальный **`slug`** (нижний регистр, индекс в БД): человекочитаемый идентификатор для путей API и UI. **Slug не является секретом** — доступ по-прежнему через JWT и проверку членства.
- Заголовок **`X-Workspace-Id`** по-прежнему передаёт **UUID** workspace (клиент знает его из `GET /workspaces`); это не требует дополнительного lookup на каждый запрос.
- Path-параметр **`/workspaces/{workspace_ref}/…`** принимает **либо UUID**, либо **slug** (`resolve_workspace_ref_to_id` в `deps.py` + `app/core/workspace_slug.py`). Админские маршруты `/admin/workspaces/{workspace_id}/…` остаются на UUID для однозначности.
- **Фронтенд (Next.js):** основные экраны приложения живут под **`/w/{slug}/…`** (документы, команда, чат и т.д.); устаревшие пути без сегмента (`/documents`, …) редиректят на slug-версию после загрузки workspace.
- **Stripe Checkout:** клиент передаёт в `POST /billing/checkout` абсолютные `success_url` / `cancel_url` с путём вида `/w/{slug}/billing/success` и `/w/{slug}/billing?checkout=cancel`, чтобы после оплаты открывался нужный workspace. Дефолт бэкенда (`{APP_BASE_URL}/billing?…`) оставлен для обратной совместимости без slug.

В **production** синхронная индексация в процессе API отключена: `document_ingestion.py` (upload), `documents.reindex_embeddings` (sync-ветка), плюс `startup_checks` — `ALLOW_SYNC_INGESTION_FOR_DEV` не может быть `true` при `ENVIRONMENT=production`.

Async upload: после `flush` строк `Document` + `IngestionJob` выполняется **`commit` до `apply_async`**, чтобы worker (отдельное соединение к БД) и Celery eager в тестах видели строки. Забор job в Celery и в poller-воркере делается **атомарным claim** в PostgreSQL (`UPDATE … RETURNING` / `FOR UPDATE SKIP LOCKED`), чтобы параллельные воркеры не обрабатывали одну и ту же задачу.

## HTTP routers (`backend/app/api/routers/`)

| Router | Scope | Примечание |
|--------|-------|------------|
| `auth.py` | user | Без workspace; refresh/logout с audit |
| `workspaces.py` | user | Список workspace пользователя |
| `workspace_members.py` | path `workspace_ref` (UUID или slug) | Ростер участников; смена роли / kick — admin+ (`WorkspaceInviteAdmin`) |
| `documents.py` | `ws.workspace.id` | `get_document`, upload, delete, summary, download, ingestion sub-resource — через `DocumentIngestionService` с `workspace_id` |
| `ingestion.py` | `IngestionJob.workspace_id` | Список jobs только текущего workspace |
| `search.py` | `ws.workspace.id` | `SearchService.search(workspace_id=...)` |
| `chat.py` | `ChatSession.workspace_id` | Сессии и сообщения по `workspace_id` |
| `billing.py` | `ws.workspace.id` | Usage/ledger |
| `audit.py` | `AuditLog.workspace_id` | Логи workspace; admin route с лимитом |

### Endpoints → workspace_id / permission

| Файл | Метод | Путь (prefix `/api/v1`) | `workspace_id` | Проверка |
|------|-------|-------------------------|----------------|----------|
| `auth.py` | POST | `/auth/login` | — | N/A (audit `auth.login` / `auth.login_failed`) |
| `auth.py` | POST | `/auth/register` … | — | — |
| `auth.py` | POST | `/auth/refresh`, `/logout`, `/logout-all` | — | refresh rotation + reuse |
| `workspaces.py` | GET | `/workspaces` | — | только членства пользователя |
| `workspace_members.py` | GET | `/workspaces/{workspace_ref}/members` | `WorkspaceReadAccessForRef` | все роли workspace |
| `workspace_members.py` | PATCH | `/workspaces/{workspace_ref}/members/{user_id}` | `WorkspaceInviteAdmin` | смена роли (не owner) |
| `workspace_members.py` | DELETE | `/workspaces/{workspace_ref}/members/{user_id}` | `WorkspaceInviteAdmin` | исключение участника |
| `invitations.py` | POST/GET/… | `/workspaces/{workspace_ref}/invitations…` | `WorkspaceInviteAdmin` | приглашения по workspace |
| `documents.py` | GET | `/documents` | `CurrentWorkspace` | read roles |
| `documents.py` | POST | `/documents/upload` | `WorkspaceWriteAccess` | member+ |
| `documents.py` | `GET/DELETE/…` | `/documents/{id}/*` | сервис + `Document.workspace_id == ws.id` | не по `owner_id` |
| `ingestion.py` | GET | `/ingestion/jobs` | фильтр `IngestionJob.workspace_id` | read |
| `search.py` | POST | `/search` | `SearchService.search(workspace_id=…)` | `vector_search`: SQL `d.workspace_id` |
| `chat.py` | * | `/chat/sessions*` | `ChatSession.workspace_id` | read / write |
| `billing.py` | GET | `/billing/usage`, `/billing/ledger` | quota workspace | read |
| `audit.py` | GET | `/audit/logs`, `/audit/admin/logs` | `AuditLog.workspace_id` | admin для расширенного лимита |

## Background tasks (`backend/app/tasks/`)

| Task | Проверка |
|------|----------|
| `ingestion.ingest_document_task` | `document.workspace_id` должен совпадать с `workspace_id` из kwargs; иначе `workspace_mismatch` и fail job |
| `ingestion.reindex_workspace_embeddings_task` | `workspace_id` в kwargs |
| `maintenance.purge_soft_deleted_documents` | Глобальный maintenance; удаление по `deleted_at`, не cross-tenant read |

## Зависимости

- `get_workspace_context` + `require_roles`: viewer не проходит write-gate.
- `workspace.access_denied` audit при 403 из-за отсутствия membership.

См. тесты: `tests/test_cross_workspace_access.py`, `tests/test_workspace_permissions.py`, `tests/test_ingestion_task_unit.py`.

Общий статус дорожной карты: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
