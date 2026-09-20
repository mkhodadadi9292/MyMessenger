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
```

## CI (`.gitlab-ci.yml`)

Jobs per user rules: `typecheck` / `lint` / `pyright` plus `pytest` and `playwright` stages — commands taken from the CI file when they exist; never run without explicit user approval.
