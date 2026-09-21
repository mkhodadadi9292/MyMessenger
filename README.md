# Messenger

Telegram-like messenger: FastAPI (REST) + SQLite backend, React + Vite frontend, Playwright e2e tests, Docker deployment with Nginx.

Docs: [PLAN/README.md](PLAN/README.md) — requirements, architecture, data model, API endpoints, phases, testing strategy.

## Run with Docker (end to end)

```bash
docker compose up --build
# frontend: http://localhost:8080
```

- The backend runs migrations on startup (`alembic upgrade head`) and listens on port 8000 (internal).
- Nginx serves the React build, proxies `/api` to the backend, and serves uploaded media from a shared volume.
- **OTP codes** are printed in the backend log (`docker compose logs backend`) and, while `DEBUG=true`, are also available at `GET /api/v1/auth/otp/dev/latest?identifier=<email>`.
- Data persists in named volumes (`messenger-db`, `messenger-media`). `docker compose down -v` resets.

## Run locally (dev)

Backend:

```bash
uv sync
cp .env.example .env   # optional
uv run alembic upgrade head
uv run uvicorn main:app --reload   # http://localhost:8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api and /media to :8000)
```

## Tests

Backend (unit / integration / e2e, isolated in-memory test DB):

```bash
uv run pytest            # all
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e
```

Frontend e2e (Playwright, uses system Google Chrome via `channel: 'chrome'`; starts its own backend + vite):

```bash
cd frontend
npx playwright test
```

The backend for Playwright uses `data/e2e-playwright.db` (wiped on each run) and `data/e2e-media`; OTP codes are read through the debug endpoint — the real database is never touched by tests.

## API

Full endpoint table: [PLAN/04-api-endpoints.md](PLAN/04-api-endpoints.md). Interactive docs at `/docs` (Swagger UI).

## Configuration

Environment variables (see `.env.example`): `DATABASE_URL`, `MEDIA_ROOT`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`, `OTP_TTL_SECONDS`, `OTP_LENGTH`, `MAX_ARTIFACT_SIZE_MB`, `DEBUG`.
