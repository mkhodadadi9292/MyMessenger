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
| [07-responsive-ui.md](07-responsive-ui.md) | Responsive frontend: mobile single-pane + desktop two-pane |

## Phases at a glance

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold + test infra (pytest, folders, DB session, Alembic, DI, settings, health) | done |
| 1 | Auth (OTP register/login) + user profiles + search + avatar | done |
| 2 | Contacts + blocking | done |
| 3 | Private chats + messages + replies | done |
| 4 | Groups (private/public), invites (button + temp link), roles | done |
| 5 | Artifacts: image / video / audio upload & serving | done |
| 6 | Frontend: React + Vite, Telegram-like UI | done |
| 7 | Playwright e2e for the frontend | done |
| 8 | Nginx + Docker + docs finalization | done |

**Status:** all phases implemented. Backend suite: 230 tests green (unit + integration + e2e, isolated in-memory test DB). Frontend: 7/7 Playwright e2e journeys green. Docker compose stack verified end to end (register → chat → upload → media served by Nginx).

**Test-first rule:** every phase writes its tests (unit / integration / e2e) in the `tests/` tree, in the same phase as the feature — starting with Phase 0 which creates the test infrastructure itself.

Realtime delivery is implemented via **WebSocket** (`/ws` endpoint with per-chat subscriptions; REST stays as the send path and polling as an automatic fallback). Notifications/push remain out of scope for v1 — the message model and service APIs are designed so they can be added later without breaking changes.
