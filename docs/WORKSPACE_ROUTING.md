# Workspace routing inventory

Все workspace-scoped операции должны фильтровать по `workspace_id` из контекста (`WorkspaceReadAccess` / `WorkspaceWriteAccess` из `deps.py`) или из поля `IngestionJob.workspace_id` / `Document.workspace_id` в фоновых задачах. `owner_id` на моделях — метаданные/аудит, не путь авторизации.

## HTTP routers (`backend/app/api/routers/`)

| Router | Scope | Примечание |
|--------|-------|------------|
| `auth.py` | user | Без workspace; refresh/logout с audit |
| `workspaces.py` | user | Список workspace пользователя |
| `documents.py` | `ws.workspace.id` | `get_document`, upload, delete, summary, download, ingestion sub-resource — через `DocumentIngestionService` с `workspace_id` |
| `ingestion.py` | `IngestionJob.workspace_id` | Список jobs только текущего workspace |
| `search.py` | `ws.workspace.id` | `SearchService.search(workspace_id=...)` |
| `chat.py` | `ChatSession.workspace_id` | Сессии и сообщения по `workspace_id` |
| `billing.py` | `ws.workspace.id` | Usage/ledger |
| `audit.py` | `AuditLog.workspace_id` | Логи workspace; admin route с лимитом |

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
