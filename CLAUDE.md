# CLAUDE.md

Telegram-like messenger: FastAPI REST backend (PostgreSQL) + React/Vite frontend, plus two side services: `file-service/` (resumable chunked uploads) and `file-cleaner/` (safe purging of unreferenced uploads). They talk to the backend over Redis Streams. Full context in the plan docs under `PLAN/`.

## Docs index

| Topic | Doc |
|---|---|
| Feature requirements (FR/NFR) | `PLAN/01-requirements.md` |
| Architecture: three layers, SOLID, DI, folder layout | `PLAN/02-architecture.md` |
| Data model: tables, value objects, invariants | `PLAN/03-data-model.md` |
| API endpoint table (auth/users/contacts/blocking/chats/invites/messages/artifacts) | `PLAN/04-api-endpoints.md` |
| Phases 0–9 with per-phase deliverables and tests | `PLAN/05-phases.md` |
| Testing strategy: unit/integration/e2e pyramid, isolation rules | `PLAN/06-testing-strategy.md` |
| Responsive UI: mobile single-pane + desktop two-pane | `PLAN/07-responsive-ui.md` |
| Chunked uploads, file-service, file-cleaner, Redis Streams | `PLAN/08-chunked-upload.md` |
| What each file-service / file-cleaner test guarantees | `file-service/TESTING.md`, `file-cleaner/TESTING.md` |

## Commands

```bash
# dev infrastructure (Postgres on 127.0.0.1:5432 with roles messenger + file_service, Redis on 6379)
docker compose up -d postgres db-init redis

# backend
uv sync                       # install deps
uv run alembic upgrade head   # migrate dev DB (postgres database "messenger")
uv run uvicorn main:app --reload   # http://localhost:8000 (needs .env with DATABASE_URL / REDIS_URL)

# file-service / file-cleaner (separate uv projects)
cd file-service && uv sync && uv run alembic upgrade head && uv run uvicorn main:app --port 8001
cd file-cleaner && uv sync && uv run python main.py

# tests (backend): unit / integration / e2e — isolated in-memory SQLite by default
uv run pytest                 # all (tests/postgres and tests/streams use Docker containers)
TEST_DB=postgres uv run pytest   # whole suite on one disposable testcontainers Postgres
cd file-service && uv run pytest # needs Docker for tests/streams + tests/postgres
cd file-cleaner && uv run pytest

# frontend
cd frontend && npm install && npm run dev    # http://localhost:5173
npm run build                                 # type-check + build

# frontend e2e (Playwright)
cd frontend && npx playwright test
# NOTE: run from frontend/ with the local binary (./node_modules/.bin/playwright);
# npx from the repo root fetches a second Playwright copy and breaks collection.
# Uses system Google Chrome via channel: 'chrome'.

# docker (end to end): postgres, db-init, redis, backend, file-service, file-cleaner, frontend
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
- **Username policy** (single rule, both sides): 3–32 chars, must start with a lowercase letter, only `a-z 0-9 _`. Backend: `Username` VO in `app/domain/value_objects.py`. Frontend: `frontend/src/username.ts` (`validateUsername`) with inline error + disabled submit in `AuthScreen`. Keep both in sync when changing the policy.
- **Blocking** is enforced in the application layer: messaging, profile view, search results, contact add, invites (see `PLAN/01-requirements.md` FR-8).
- **Database**: PostgreSQL (asyncpg) for dev, Docker and Playwright. The backend owns database `messenger` (role `messenger`); file-service owns `file_service` (role `file_service`). Neither role is a superuser and CONNECT is revoked across databases (`deploy/postgres/init-databases.sh`, run by the `db-init` compose job on every `up`). Never share tables or roles between services. Code stays dialect-portable (no Postgres-only SQL) so the fast SQLite test mode keeps working.
- **Migrations**: every schema change is an Alembic migration on top of the single head, with a working downgrade; never edit existing migrations. file-service has its own Alembic history in `file-service/alembic/`.
- **Test isolation** (see `PLAN/06-testing-strategy.md`): by default tests use a shared in-memory SQLite engine (StaticPool) swapped in by `tests/conftest.py` — file-backed DDL is ~150ms/statement on this machine, so do NOT switch tests back to file DBs. `TEST_DB=postgres` runs the same suite on one testcontainers Postgres per session (migrated once, TRUNCATE between tests). `tests/postgres/` (migrations, concurrent idempotency) always runs on Postgres and `tests/streams/` on a real Redis container; without Docker they fail with a clear message (or set `TEST_POSTGRES_URL` / `TEST_REDIS_URL` to disposable instances). The dev database and compose volumes must never be touched by tests.
- **OTP in tests/e2e**: codes come from the capturing sender (`tests/fakes.py`) or the debug endpoint `GET /api/v1/auth/otp/dev/latest?identifier=...` (enabled only when `DEBUG=true`).
- **Playwright e2e**: the backend webServer command starts throwaway `mm-e2e-postgres` (tmpfs) and `mm-e2e-redis` containers and migrates before uvicorn; file-service runs as a second webServer on :8001 with 256 KiB chunks; globalTeardown removes the containers (webServers start before globalSetup, so never wipe databases in globalSetup). Media/chunks live in `data/e2e-media` / `data/e2e-uploads`. Specs use per-run unique users (`uniqueUser()` in `frontend/e2e/helpers.ts`). Playwright needs Docker.
- **Responsive** (see `PLAN/07-responsive-ui.md`): breakpoint `max-width: 768px` — mobile is a single pane (list ↔ chat via `back-button`, pure CSS switching with `.chat-open`); desktop is two-pane. Mobile behavior is covered by `frontend/e2e/responsive.spec.ts` (390×844 viewport); keep that spec updated when changing layout behavior.

## Uploads (chunked, see `PLAN/08-chunked-upload.md`)

- The backend is the authority: `POST /api/v1/chats/{chat_id}/uploads` checks membership, blocking, kind/MIME, size, sha256 format and reply target, then returns an HS256 upload ticket signed with `UPLOAD_TICKET_SECRET` (must differ from `JWT_SECRET`). file-service knows nothing about chats.
- file-service (`/files/v1/uploads`): init → `PUT .../chunks/{index}` (idempotent, any order, streamed to disk) → `GET` (resume) → `POST .../complete` (streaming assembly, verifies size + sha256 + MIME) → `DELETE` (abort). Final files go to `MEDIA_ROOT/artifacts/<hex><ext>` (served as `/media/...`), chunks to `CHUNKS_ROOT` (never served).
- Redis Streams: `upload.completed` (file-service → group `messenger-backend`) and `upload.outcome` (`upload.attached` / `upload.rejected` → group `file-service`); dead letters in `<stream>.dead`. Ack only after the DB commit, XAUTOCLAIM for stuck entries, `STREAM_MAX_DELIVERIES`. Contract: `contracts/upload-events.v1.json` (tested by both sides).
- The backend consumer (`app/api/upload_events.py`, started in the app lifespan when `REDIS_URL` is set) re-checks membership/blocking, creates message + artifact (unique `artifacts.upload_id`), commits, broadcasts `message.new` via `broadcast_new_message`, then publishes the outcome. Wiring for it, `deps.py` and `ws.py` lives in `app/api/composition.py`.
- file-cleaner only calls file-service's internal API (`/internal/v1/cleanup/{rule}`, `X-Internal-Key`, never proxied by nginx); attached files are never purged.
- Frontend: `frontend/src/upload.ts` (incremental sha256 via `@noble/hashes`, 3 parallel chunks, retry/backoff, resume, cancel); progress UI in `ChatWindow`.

## Realtime (WebSocket)

- `/ws?token=<access_token>` — one connection per user; client sends `subscribe/unsubscribe` per chat, `message.send` (text+reply) and `ping`.
- Server events: `message.new` (full message payload incl. reply preview), `chat.list_changed` (chat-list refresh signal), `message.sent`, `error`.
- REST endpoints still broadcast: sends/opens/joins notify via `app.state.realtime` (`ConnectionManager` in `app/infrastructure/realtime.py`, helpers in `app/api/realtime.py`).
- Frontend (`frontend/src/ws.ts`): auto-reconnect + resubscribe; **polling remains only as a fallback** while the socket is down.
- Proxies: Vite dev (`/ws` with `ws: true`, `/files` → :8001) and `deploy/nginx.conf` (`Upgrade`/`Connection` headers; `/files/` → file-service with 2m bodies; `/api/` 25m).
- `ChatWindow` also reloads (merging by id) on `chat.list_changed`, so a `message.new` sent before its chat subscription registered is not lost.
- WS tests: `tests/e2e/test_websocket.py` (real server + `websockets` client).

## Not in scope for v1

Notifications/push — message model and service seams are ready for it (`PLAN/README.md`).
