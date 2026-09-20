# Messenger — Master Plan

Telegram-like messenger. Backend: Python + FastAPI (REST). Frontend: React + Vite. SQLite (→ Postgres later), Alembic migrations, Nginx for static files.

## Plan documents

| Doc | Content |
|---|---|
| [01-requirements.md](01-requirements.md) | Feature requirements broken down |
| [02-architecture.md](02-architecture.md) | Three-layer architecture, SOLID/DDD-lite, DI, folder layout |
| [03-data-model.md](03-data-model.md) | Entities, tables, value objects |
| [04-api-endpoints.md](04-api-endpoints.md) | Full endpoint table |
| [05-phases.md](05-phases.md) | Phased implementation plan with deliverables |
| [06-testing-strategy.md](06-testing-strategy.md) | Unit / integration / e2e strategy, tools |

## Phases at a glance

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold + test infra (pytest, folders, DB session, Alembic, DI, settings, health) | done |
| 1 | Auth (OTP register/login) + user profiles + search + avatar | todo |
| 2 | Contacts + blocking | todo |
| 3 | Private chats + messages + replies | todo |
| 4 | Groups (private/public), invites (button + temp link), roles | todo |
| 5 | Artifacts: image / video / audio upload & serving | todo |
| 6 | Frontend: React + Vite, Telegram-like UI | todo |
| 7 | Playwright e2e for the frontend | todo |
| 8 | Nginx + Docker + docs finalization | todo |

**Test-first rule:** every phase writes its tests (unit / integration / e2e) in the `tests/` tree, in the same phase as the feature — starting with Phase 0 which creates the test infrastructure itself.

**Status:** test suite for Phases 1–5 written (TDD red phase) — 138 tests: 8 pass (Phase 0), 123 fail against not-yet-implemented endpoints, 7 unit modules await implementation (`value_objects`, `entities`, `permissions`, `blocking`, `pagination`, `infrastructure.auth.otp`, `infrastructure.auth.jwt`).

Notifications are explicitly out of scope for v1, but the message model and service APIs are designed so notifications can be added later without breaking changes.
