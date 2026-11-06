# Messenger

Telegram-like messenger: FastAPI (REST) + PostgreSQL backend, React + Vite frontend, resumable chunked uploads through `file-service` (with `file-cleaner` purging unreferenced uploads) connected over Redis Streams, Playwright e2e tests, Docker deployment with Nginx.

Docs: [PLAN/README.md](PLAN/README.md) — requirements, architecture, data model, API endpoints, phases, testing strategy.

## Run with Docker (end to end)

```bash
docker compose up --build
# frontend: http://localhost:8080
```

- Services: `postgres` (one server, databases `messenger` and `file_service` with their own non-superuser roles), `db-init` (idempotent role/database setup, runs on every `up`), `redis` (Streams, AOF), `backend`, `file-service`, `file-cleaner`, `frontend` (Nginx).
- The backend and file-service run their migrations on startup (`alembic upgrade head`); this works on a fresh and on an existing volume.
- Nginx serves the React build, proxies `/api` to the backend and `/files/` (chunk uploads, 2 MB per request) to file-service, and serves uploaded media from the shared `messenger-media` volume.
- **OTP codes** are printed in the backend log (`docker compose logs backend`) and, while `DEBUG=true`, are also available at `GET /api/v1/auth/otp/dev/latest?identifier=<email>`.
- Data persists in named volumes (`messenger-pg`, `messenger-media`, `messenger-uploads`, `messenger-redis`). `docker compose down -v` resets everything.

## Run locally (dev)

Infrastructure (Postgres on 127.0.0.1:5432, Redis on 127.0.0.1:6379):

```bash
docker compose up -d postgres db-init redis
```

Backend:

```bash
uv sync
cp .env.example .env   # DATABASE_URL / REDIS_URL / UPLOAD_TICKET_SECRET for localhost
uv run alembic upgrade head
uv run uvicorn main:app --reload   # http://localhost:8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api, /media, /ws to :8000 and /files to :8001)
```

file-service and file-cleaner (separate uv projects; use the same `UPLOAD_TICKET_SECRET` as the backend, and `MEDIA_ROOT=../data/media` so both write the same media tree):

```bash
cd file-service
uv sync
DATABASE_URL=postgresql+asyncpg://file_service:file-service-dev-password@localhost:5432/file_service uv run alembic upgrade head
MEDIA_ROOT=../data/media CHUNKS_ROOT=../data/uploads uv run uvicorn main:app --port 8001

cd file-cleaner
uv sync
FILE_SERVICE_URL=http://localhost:8001 uv run python main.py
```

## Tests

Backend (unit / integration / e2e). Default: isolated in-memory SQLite. `tests/postgres` (migrations, concurrency) always uses a throwaway Postgres container and `tests/streams` a throwaway Redis container, so Docker must be running (or set `TEST_POSTGRES_URL` / `TEST_REDIS_URL` to disposable instances):

```bash
uv run pytest                    # all, SQLite mode
TEST_DB=postgres uv run pytest   # the whole suite on one testcontainers Postgres (TRUNCATE between tests)
uv run pytest tests/unit tests/integration tests/e2e
```

file-service and file-cleaner (see their `TESTING.md` for what each test guarantees):

```bash
cd file-service && uv run pytest
cd file-cleaner && uv run pytest
```

Frontend e2e (Playwright, uses system Google Chrome via `channel: 'chrome'`; starts its own backend + vite):

```bash
cd frontend
npm ci
./node_modules/.bin/playwright test
```

Playwright starts throwaway `mm-e2e-postgres` and `mm-e2e-redis` containers (removed afterwards), the backend on :8000, file-service on :8001 (256 KiB chunks) and Vite; media and chunks go to `data/e2e-media` / `data/e2e-uploads`. OTP codes are read through the debug endpoint — the real database is never touched by tests.

## API

Full endpoint table: [PLAN/04-api-endpoints.md](PLAN/04-api-endpoints.md). Interactive docs at `/docs` (Swagger UI). Upload protocol and Redis Streams events: [PLAN/08-chunked-upload.md](PLAN/08-chunked-upload.md).

## Configuration

Environment variables (see `.env.example`):

- backend: `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, `MEDIA_ROOT`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`, `OTP_TTL_SECONDS`, `OTP_LENGTH`, `MAX_ARTIFACT_SIZE_MB`, `DEBUG`, `REDIS_URL`, `UPLOAD_TICKET_SECRET` (must differ from `JWT_SECRET`), `UPLOAD_TICKET_TTL_SECONDS`, `UPLOAD_EVENT_MAX_AGE_SECONDS`, `CONSUMER_DB_POOL_SIZE`, `STREAM_MAX_DELIVERIES`, `STREAM_CLAIM_MIN_IDLE_MS`;
- compose / Postgres: `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD`, `POSTGRES_HOST_PORT`, `POSTGRES_MAX_CONNECTIONS`, `MESSENGER_DB_NAME/USER/PASSWORD`, `FILE_SERVICE_DB_NAME/USER/PASSWORD`, `REDIS_HOST_PORT`;
- file-service: `DATABASE_URL`, `REDIS_URL`, `MEDIA_ROOT`, `CHUNKS_ROOT`, `UPLOAD_CHUNK_SIZE_BYTES`, `MAX_UPLOAD_SIZE_BYTES`, `UPLOAD_TICKET_SECRET`, `INTERNAL_API_KEY` (compose: `FILE_SERVICE_INTERNAL_API_KEY`);
- file-cleaner: `FILE_SERVICE_URL`, `INTERNAL_API_KEY`, `UPLOAD_SESSION_TTL_SECONDS`, `ASSEMBLY_STUCK_TTL_SECONDS`, `ATTACH_GRACE_PERIOD_SECONDS`, `TERMINAL_PURGE_DELAY_SECONDS`, `ORPHAN_CHUNK_DIR_MIN_AGE_SECONDS`, `BACKEND_UPLOAD_EVENT_MAX_AGE_SECONDS` and one `*_INTERVAL_SECONDS` per rule.
