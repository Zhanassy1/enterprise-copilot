# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-05

### Added

- Multi-tenant AI workspace: semantic search and RAG chat over PDF/DOCX/TXT with workspace isolation (`X-Workspace-Id`).
- FastAPI backend, Next.js frontend, PostgreSQL + pgvector, Celery workers, Redis.
- Async document ingestion jobs (queued → processing → ready/failed).
- Plans and usage quotas; Stripe billing (Checkout, Customer Portal, webhooks).
- Team invitations and workspace roles (owner, admin, member, viewer).
- Docker Compose quick start; API docs at `/docs`.
- Audit logging and optional platform admin tooling.

[0.1.0]: https://github.com/Zhanassy1/enterprise-copilot/releases/tag/v0.1.0
