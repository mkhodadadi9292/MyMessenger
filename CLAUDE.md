# CLAUDE.md

Telegram-like messenger: FastAPI REST backend (SQLite, → Postgres later) + React/Vite frontend. Full context in the plan docs under `system-design-docs/` (per-feature phased plans live in `plan/`, research notes in `knowledge/`).

## Docs index

| Topic | Doc |
|---|---|
| Feature requirements (FR/NFR) | `system-design-docs/01-requirements.md` |
| Architecture: three layers, SOLID, DI, folder layout | `system-design-docs/02-architecture.md` |
| Data model: tables, value objects, invariants | `system-design-docs/03-data-model.md` |
| API endpoint table (auth/users/contacts/blocking/chats/invites/messages/artifacts/notifications) | `system-design-docs/04-api-endpoints.md` |
| Phases 0–9 with per-phase deliverables and tests | `system-design-docs/05-phases.md` |
| Testing strategy: unit/integration/e2e pyramid, isolation rules | `system-design-docs/06-testing-strategy.md` |
| Responsive UI: mobile single-pane + desktop two-pane | `system-design-docs/07-responsive-ui.md` |
| Notifications: SSE stream, inbox table, endpoints, guarantees | `system-design-docs/08-notifications.md` |

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
npm test                                      # Vitest component/unit tests

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

## Architecture rules (details: `system-design-docs/02-architecture.md`)

- Layers: `app/api` (presentation) → `app/application` (use cases) → `app/domain` (pure python) → `app/infrastructure` (SQLAlchemy, JWT/OTP, storage).
- Domain never imports fastapi/sqlalchemy/pydantic; repositories are ABCs in `app/domain/repositories/`, implemented in `app/infrastructure/repositories/`.
- Services receive ports via constructor injection; wiring lives in `app/api/deps.py` (FastAPI `Depends`).
- One session per request (`get_db`), commit on success / rollback on error.
- Errors: services raise domain exceptions (`app/domain/exceptions.py`), mapped to HTTP in `app/api/errors.py` (400/401/403/404/409).

## Conventions

- **Test-first**: every feature ships unit + integration + e2e tests in the same change; a phase is done only when its tests pass (see `system-design-docs/05-phases.md`).
- **Privacy**: `phone` and `email` never appear in API responses; phone search is exact-match only (see `system-design-docs/01-requirements.md` FR-1.5).
- **Username policy** (single rule, both sides): 3–32 chars, must start with a lowercase letter, only `a-z 0-9 _`. Backend: `Username` VO in `app/domain/value_objects.py`. Frontend: `frontend/src/username.ts` (`validateUsername`) with inline error + disabled submit in `AuthScreen`. Keep both in sync when changing the policy.
- **Blocking** is enforced in the application layer: messaging, profile view, search results, contact add, invites (see `system-design-docs/01-requirements.md` FR-8).
- **Postgres in docker**: `db` service (Postgres 16, named volume `messenger-pgdata`); backend uses `postgresql+asyncpg`. Data migration/backup scripts live in `scripts/` (`migrate_sqlite_to_postgres.py`, `backup_db.sh`).
- **Commit-before-response**: FastAPI yield-dependency teardown commits AFTER the response is sent, which caused read-committed races on Postgres (e.g. register → immediate search returned nothing). Every write endpoint therefore calls `await db.commit()` before returning/broadcasting. Keep this pattern for new write endpoints.
- **Playwright dual mode**: `PW_BASE_URL`/`PW_BACKEND_URL` env vars run the specs against an already-running stack (e.g. `PW_BASE_URL=http://localhost:8080 PW_BACKEND_URL=http://localhost:8080 npx playwright test`); without them, local webServers start (SQLite e2e DB).
- **Test isolation** (see `system-design-docs/06-testing-strategy.md`): tests use a shared in-memory SQLite engine (StaticPool) swapped in by `tests/conftest.py` — file-backed DDL is ~150ms/statement on this machine, so do NOT switch tests back to file DBs. Real/dev DB (`data/messenger.db`, `media.db`) must never be touched by tests.
- **OTP in tests/e2e**: codes come from the capturing sender (`tests/fakes.py`) or the debug endpoint `GET /api/v1/auth/otp/dev/latest?identifier=...` (enabled only when `DEBUG=true`).
- **Playwright e2e DB**: the backend webServer command wipes and migrates `data/e2e-playwright.db` itself (webServers start before globalSetup, so wiping in globalSetup corrupts the running backend). Specs use per-run unique users (`uniqueUser()` in `frontend/e2e/helpers.ts`).
- **Responsive** (see `system-design-docs/07-responsive-ui.md`): breakpoint `max-width: 768px` — mobile is a single pane (list ↔ chat via `back-button`, pure CSS switching with `.chat-open`); desktop is two-pane. Mobile behavior is covered by `frontend/e2e/responsive.spec.ts` (390×844 viewport); keep that spec updated when changing layout behavior.

## Realtime (WebSocket)

- `/ws?token=<access_token>` — one connection per user; client sends `subscribe/unsubscribe` per chat, `message.send` (text+reply) and `ping`.
- Server events: `message.new` (full message payload incl. reply preview), `chat.list_changed` (chat-list refresh signal), `message.sent`, `error`.
- REST endpoints still broadcast: sends/opens/joins notify via `app.state.realtime` (`ConnectionManager` in `app/infrastructure/realtime.py`, helpers in `app/api/realtime.py`).
- Frontend (`frontend/src/ws.ts`): auto-reconnect + resubscribe; **polling remains only as a fallback** while the socket is down.
- Proxies: Vite dev (`/ws` with `ws: true`) and `deploy/nginx.conf` (`Upgrade`/`Connection` headers).
- WS tests: `tests/e2e/test_websocket.py` (real server + `websockets` client).

## Notifications (SSE)

- Design: `system-design-docs/08-notifications.md`; alternatives: `knowledge/notification-system-architectures.md`.
- **Inbox table** `notifications` (one row per recipient per event, denormalized `chat_title`/`preview` snapshots); unread state survives disconnects. Migration: `a7e5f9c2d4b1`.
- **Stream**: `GET /api/v1/notifications/stream?token=<access_token>` — EventSource can't send headers, so the JWT goes in the query string (like `/ws`; the `Authorization` header is also accepted). Events: `event: notification.new` with `{notification, unread_count}`, `: keepalive` every `sse_keepalive_seconds` (15), `retry: 3000`.
- **Commit-before-notify**: inbox rows are inserted in the same transaction as the business change; SSE events are published only AFTER `db.commit()` (same rule as commit-before-broadcast). Helpers: `notify_new_message` / `notify_new_invite` in `app/api/notify.py` — every new write path that should notify (REST message, artifact upload, WS `message.send`, button invite) must call them after commit.
- **SseHub** (`app/infrastructure/sse.py`): per-user `asyncio.Queue` fan-out on `app.state.sse`; single-instance (Redis Pub/Sub is the multi-instance seam).
- **REST**: N1 list (cursor-paginated newest-first), N2 unread-count, N3 mark-read (`{chat_id}` or all).
- **Nginx**: dedicated `location = /api/v1/notifications/stream` with `proxy_buffering off` (buffering would hold events back); Vite dev proxy passes SSE as-is.
- **Frontend**: `frontend/src/sse.ts` (`NotificationClient`, EventSource auto-reconnect — no manual retry loop), `NotificationsPanel.tsx` (bell `notifications-button`, badge `notifications-badge`, panel `notifications-panel`), mark-read on chat open (`App.tsx`).
- **Tests**: backend `tests/unit|integration|e2e/test_notifications.py` (e2e overrides `sse_keepalive_seconds=1`; open the stream BEFORE triggering the event — the httpx stream generator is lazy). Frontend: Vitest `src/__tests__/sse.test.ts` + `notifications-panel.test.tsx` (jsdom has no EventSource — stub it), Playwright `e2e/notifications.spec.ts`.

## Not in scope for v1

Push notifications while the app is closed (FCM/APNs) and device tokens — the notification inbox leaves the seam ready (`system-design-docs/08-notifications.md`).
