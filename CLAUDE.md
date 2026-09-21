# CLAUDE.md

Telegram-like messenger: FastAPI REST backend (SQLite, → Postgres later) + React/Vite frontend. Full context in the plan docs under `PLAN/`.

## Docs index

| Topic | Doc |
|---|---|
| Feature requirements (FR/NFR) | `PLAN/01-requirements.md` |
| Architecture: three layers, SOLID, DI, folder layout | `PLAN/02-architecture.md` |
| Data model: tables, value objects, invariants | `PLAN/03-data-model.md` |
| API endpoint table (auth/users/contacts/blocking/chats/invites/messages/artifacts) | `PLAN/04-api-endpoints.md` |
| Phases 0–8 with per-phase deliverables and tests | `PLAN/05-phases.md` |
| Testing strategy: unit/integration/e2e pyramid, isolation rules | `PLAN/06-testing-strategy.md` |
| Responsive UI: mobile single-pane + desktop two-pane | `PLAN/07-responsive-ui.md` |

## Commands

```bash
# backend
uv sync                       # install deps
uv run alembic upgrade head   # migrate dev DB (data/messenger.db)
uv run uvicorn main:app --reload   # http://localhost:8000

# tests (backend): unit / integration / e2e — isolated in-memory test DB
uv run pytest                 # all
uv run pytest tests/unit tests/integration tests/e2e

# frontend
cd frontend && npm install && npm run dev    # http://localhost:5173
npm run build                                 # type-check + build

# frontend e2e (Playwright)
cd frontend && npx playwright test
# NOTE: run from frontend/ with the local binary (./node_modules/.bin/playwright);
# npx from the repo root fetches a second Playwright copy and breaks collection.
# Uses system Google Chrome via channel: 'chrome'.

# docker (end to end)
docker compose up --build      # http://localhost:8080
docker compose logs backend    # OTP codes are printed here
docker compose down -v         # reset data
```

## Architecture rules (details: `PLAN/02-architecture.md`)

- Layers: `app/api` (presentation) → `app/application` (use cases) → `app/domain` (pure python) → `app/infrastructure` (SQLAlchemy, JWT/OTP, storage).
- Domain never imports fastapi/sqlalchemy/pydantic; repositories are ABCs in `app/domain/repositories/`, implemented in `app/infrastructure/repositories/`.
- Services receive ports via constructor injection; wiring lives in `app/api/deps.py` (FastAPI `Depends`).
- One session per request (`get_db`), commit on success / rollback on error.
- Errors: services raise domain exceptions (`app/domain/exceptions.py`), mapped to HTTP in `app/api/errors.py` (400/401/403/404/409).

## Conventions

- **Test-first**: every feature ships unit + integration + e2e tests in the same change; a phase is done only when its tests pass (see `PLAN/05-phases.md`).
- **Privacy**: `phone` and `email` never appear in API responses; phone search is exact-match only (see `PLAN/01-requirements.md` FR-1.5).
- **Blocking** is enforced in the application layer: messaging, profile view, search results, contact add, invites (see `PLAN/01-requirements.md` FR-8).
- **Test isolation** (see `PLAN/06-testing-strategy.md`): tests use a shared in-memory SQLite engine (StaticPool) swapped in by `tests/conftest.py` — file-backed DDL is ~150ms/statement on this machine, so do NOT switch tests back to file DBs. Real/dev DB (`data/messenger.db`, `media.db`) must never be touched by tests.
- **OTP in tests/e2e**: codes come from the capturing sender (`tests/fakes.py`) or the debug endpoint `GET /api/v1/auth/otp/dev/latest?identifier=...` (enabled only when `DEBUG=true`).
- **Playwright e2e DB**: the backend webServer command wipes and migrates `data/e2e-playwright.db` itself (webServers start before globalSetup, so wiping in globalSetup corrupts the running backend). Specs use per-run unique users (`uniqueUser()` in `frontend/e2e/helpers.ts`).
- **Responsive** (see `PLAN/07-responsive-ui.md`): breakpoint `max-width: 768px` — mobile is a single pane (list ↔ chat via `back-button`, pure CSS switching with `.chat-open`); desktop is two-pane. Mobile behavior is covered by `frontend/e2e/responsive.spec.ts` (390×844 viewport); keep that spec updated when changing layout behavior.

## Not in scope for v1

Notifications/push — message model and service seams are ready for it (`PLAN/README.md`). Realtime delivery is currently short polling (messages 2s, chat list 3s).
