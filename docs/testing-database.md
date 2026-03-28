# Database connections in tests

**See also:** [README.md](../README.md) section **Testing** (CI jobs and when to set this variable).

## SQLALCHEMY_USE_NULLPOOL (`test-safety` mode)

When `SQLALCHEMY_USE_NULLPOOL=1`, `backend/app/db/session.py` builds the engine with **`NullPool`**: each `Session` checks out a connection and **returns it to the driver on `session.close()`** instead of keeping it in SQLAlchemy’s `QueuePool`.

### Why CI and local integration use it

1. **Predictable teardown** — integration tests open many short-lived sessions (HTTP `get_db`, `SessionLocal()` in seeds, Celery tasks in the same process). With a pooled engine, connections are **returned to the pool** while the underlying `psycopg` connection object may still participate in GC cycles; **Python 3.14+** can emit `ResourceWarning: Connection ... deleted while still open` when the pool and GC order interact badly, even if no logical leak is left in application code.
2. **Same-process Celery + HTTP** — async smoke runs the ingestion task in-process; two session lifecycles overlap with the pool. `NullPool` removes cross-test reuse of pooled connections and makes warnings disappear in practice.

### What we do **without** relying on NullPool

- `ingest_document_task` only opens `SessionLocal()` **after** UUID validation; `finally: db.close()` always runs.
- `TestClient` is closed in `tearDownClass` where integration tests use a long-lived client.
- `get_db()` always closes the session in `finally`.
- `main.py` `/metrics` and `_plan_slug_for_workspace_header` use `try`/`finally: db.close()`.

### When warnings may still appear **without** NullPool

If you run integration tests **without** `SQLALCHEMY_USE_NULLPOOL=1`, you may see at process shutdown (often after all tests **ok**):

`ResourceWarning: ... psycopg ... Connection ... deleted while still open` from `Connection.__del__`

That reflects **GC finalizing a pooled connection** while the pool still holds state — not necessarily an unfixed `Session` leak in application code. `-W error::ResourceWarning` may still exit 0 while stderr shows the message, because some warnings are emitted from `__del__` after the test runner has finished.

**Mitigation for strict CI:** set `SQLALCHEMY_USE_NULLPOOL=1` for integration/smoke jobs (as in `.github/workflows/ci.yml`).

**Production** uses the default `QueuePool` (unless you override); do **not** set `SQLALCHEMY_USE_NULLPOOL` in production.
