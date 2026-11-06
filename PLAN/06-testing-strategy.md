# 06 — Testing Strategy

## Test pyramid (backend)

```
        e2e/          full app through real HTTP — user journeys
      integration/    httpx ASGI + test DB (in-memory SQLite or TEST_DB=postgres) + tmp storage
    unit/             pure python — entities, value objects, services with fake repos (no IO)
```

| Layer | What it proves | Tools | DB |
|---|---|---|---|
| unit | domain rules, invariants, permission matrices, state machines | pytest, fakes | none |
| integration | endpoints, auth flows, blocking, pagination, upload tickets, upload attach, error mapping | pytest-asyncio + httpx ASGI transport | shared in-memory SQLite per test (default) or one testcontainers Postgres per session with TRUNCATE between tests (`TEST_DB=postgres`) |
| postgres | migrations up/down (incl. existing rows), concurrent idempotent attach | testcontainers Postgres, disposable database per test | always Postgres |
| streams | publish/consume, ack after commit, XAUTOCLAIM, duplicates, dead letters | testcontainers Redis, FLUSHDB per test | in-memory SQLite |
| e2e (backend) | multi-user journeys over HTTP | httpx against the ASGI app | isolated test DB + tmp media |

Isolation rules (per user policy):
- Test DB is **always** disposable: in-memory SQLite, or a testcontainers Postgres database created and dropped by the fixtures — never the dev/prod DB or a compose volume.
- Tests that need Docker (Postgres/Redis containers) **fail** with a clear message when Docker is missing instead of being skipped; `TEST_POSTGRES_URL` / `TEST_REDIS_URL` may point at disposable CI services instead.
- Media/storage in tests points at a tmp directory, wiped between tests.
- OTP codes in tests are read from a fake `OtpSender` (captures codes) instead of server logs.
- Fixtures seed users via the API (not direct SQL) wherever practical.

## Fixtures (tests/conftest.py)

- `app` — `create_app(settings)` with test settings (tmp DB, tmp media, fake OTP sender).
- `client` — httpx `AsyncClient` with ASGI transport.
- `auth_user` / `other_user` — registered users with token headers.
- `otp_sender` — fake sender capturing generated codes.

## Frontend tests

| Layer | Tool | Scope |
|---|---|---|
| component | Vitest + Testing Library | message bubble, reply preview, chat list item, OTP form |
| e2e | Playwright | full user journeys (Phase 7 specs) |

Playwright config starts the backend (test DB) and Vite dev server automatically; tests use the fake OTP sender route or read codes from logs.

## Running

```bash
# backend
pytest tests/unit
pytest tests/integration
pytest tests/e2e

# frontend
cd frontend && npx vitest run
cd frontend && npx playwright test

# backend on Postgres
TEST_DB=postgres uv run pytest

# side services
cd file-service && uv run pytest
cd file-cleaner && uv run pytest
```

## CI (`.gitlab-ci.yml`)

Jobs per user rules: `typecheck` / `lint` / `pyright` plus `pytest` and `playwright` stages — commands taken from the CI file when they exist; never run without explicit user approval.
