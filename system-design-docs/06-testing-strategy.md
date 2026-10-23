# 06 — Testing Strategy

## Test pyramid (backend)

```
        e2e/          full app through real HTTP — user journeys
      integration/    httpx ASGI + real test SQLite + tmp storage — API contracts, DB constraints
    unit/             pure python — entities, value objects, services with fake repos (no IO)
```

| Layer | What it proves | Tools | DB |
|---|---|---|---|
| unit | domain rules, invariants, permission matrices, state machines | pytest, fakes | none |
| integration | endpoints, auth flows, blocking, pagination, uploads, error mapping | pytest-asyncio + httpx ASGI transport | test SQLite file in tmp dir, created per test |
| e2e (backend) | multi-user journeys over HTTP | httpx against the ASGI app | isolated test DB + tmp media |

Isolation rules (per user policy):
- Test DB is **always** a fresh SQLite file in a tmp directory — never the dev/prod DB, never `media.db`.
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
| component | Vitest + Testing Library | notification SSE client, notification panel/badge |
| e2e | Playwright | full user journeys (Phase 7 specs + notifications spec) |

Playwright config starts the backend (test DB) and Vite dev server automatically; tests use the fake OTP sender route or read codes from logs.

## SSE notification stream testing

- **Backend e2e** (`tests/e2e/test_notifications.py`): the app runs under a real uvicorn
  server (`live_server` fixture); httpx `client.stream()` reads SSE frames
  (`event:`/`data:`/`retry:`/comment lines). The test module overrides
  `settings.sse_keepalive_seconds = 1` so "no event" assertions wait for a keepalive instead
  of 15 s. Streams must be opened (first `retry` frame consumed) **before** triggering the
  event source — the generator is lazy.
- **Frontend unit** (`sse.test.ts`): the global `EventSource` is stubbed (jsdom has none);
  tests drive `onopen`/`addEventListener` callbacks and assert URL/token construction and
  handler delivery.
- **Frontend e2e** (`notifications.spec.ts`): two browser contexts; the badge must appear
  without a reload (proves the SSE push); docker mode runs the same spec against the nginx
  stack (`PW_BASE_URL=http://localhost:8080`), proving `proxy_buffering off` works.

## Running

```bash
# backend
pytest tests/unit
pytest tests/integration
pytest tests/e2e

# frontend
cd frontend && npx vitest run
cd frontend && npx playwright test
```

## CI (`.gitlab-ci.yml`)

Jobs per user rules: `typecheck` / `lint` / `pyright` plus `pytest` and `playwright` stages — commands taken from the CI file when they exist; never run without explicit user approval.
