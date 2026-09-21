# 05 — Phased Implementation Plan

Test-first: each phase ships its tests in the same phase. A phase is "done" when all its tests pass.

---

## Phase 0 — Scaffold + test infrastructure

**Status: done.**

**Goal:** everything needed so later phases only add features.

Deliverables:
- `app/` three-layer skeleton (empty layers, `main.py` with `create_app()`), `/health` endpoint.
- `app/config.py` (pydantic-settings, `.env`: `DATABASE_URL`, `MEDIA_ROOT`, `JWT_SECRET`, `ACCESS_TOKEN_TTL`, `REFRESH_TOKEN_TTL`, `OTP_TTL`).
- `infrastructure/db/` — async engine, session factory, `DeclarativeBase`.
- Alembic initialized (async template), baseline migration.
- `domain/repositories/base.py` — `AbstractRepository` ABC with generic CRUD.
- `api/deps.py` — `get_db` (per-request session), service provider stubs.
- `api/errors.py` — domain-exception → HTTP mapping + uniform error shape.
- `tests/` tree: `unit/`, `integration/`, `e2e/`, shared `conftest.py` fixtures (isolated test DB in tmp path, tmp media storage, seeded users, auth headers).
- Dependency pinning in `pyproject.toml` (SQLAlchemy 2, alembic, pydantic-settings, pytest, pytest-asyncio, httpx, aiosqlite, python-jose or pyjwt, python-multipart).

Tests:
- unit: config defaults; base repository ABC contract via a fake implementation.
- integration: `/health` returns ok; app factory boots with test settings; exception mapping shape.
- e2e: boot full app on test DB → `/health` through HTTP.

---

## Phase 1 — Auth + users

**Status: done.**

Deliverables: OTP request/verify/register/login (A1–A5) with code printed in server log (`LogOtpSender` behind `OtpSender` port), JWT access + revocable refresh, profile endpoints (U1–U5), avatar upload, user search with phone privacy.

Tests:
- unit: `Username`/`Phone` value objects; OTP hashing/TTL logic; token encode/decode.
- integration: full register→login→refresh→logout flow; OTP reuse/expiry rejected; duplicate username/phone 409; profile update; search by username/phone; phone never in payloads.
- e2e: register → fetch own profile → search another user (HTTP journey).

---

## Phase 2 — Contacts + blocking

**Status: done.**

Deliverables: contact add/remove/list (C1–C3), block/unblock/list (B1–B3), blocking rules wired into profile view + contact add.

Tests:
- unit: blocking rule helper (can_interact) matrix.
- integration: add contact by username & by phone; duplicate 409; remove; blocked user cannot view profile / cannot be added.
- e2e: A blocks B → B gets 403 on A's profile.

---

## Phase 3 — Private chats + messages + replies

**Status: done.**

Deliverables: private chat open (CH2), chat list (CH1), send/list/edit/delete messages (M1–M4), replies via `reply_to_id`, soft delete marker, blocked-user send refusal.

Tests:
- unit: message entity invariants (reply must be same chat); pagination cursor math.
- integration: pair chat created once; non-members get 403; history pagination; edit/delete own message only; reply chain returned; blocked pair cannot message.
- e2e: two users open chat, exchange messages, reply, edit, delete (HTTP journey).

---

## Phase 4 — Groups + invites + roles

**Status: done.**

Deliverables: group create (CH3), chat info/update (CH4/CH5), members list (CH6), admin add/remove members (CH7/CH8), public join (CH9), leave (CH10), promote admin (CH11); button invites (I1, I5–I7); temporary invite links (I2–I4); private-group invite requires confirmation.

Tests:
- unit: role permission matrix (owner/admin/member actions); invite state machine.
- integration: private group — member cannot invite, admin invite → invitee accepts → member; decline keeps them out; link invite with expiry; public group — anyone joins, join blocked for members already in; owner promotes admin; admin cannot remove admin; last member leaving deletes group.
- e2e: create private group → invite via button → accept → send message; public group join via link.

---

## Phase 5 — Artifacts

**Status: done.**

Deliverables: artifact upload for image/video/audio (T1), download (T2), message-with-artifact + optional reply, MIME/size validation, media served from `MEDIA_ROOT`.

Tests:
- unit: kind/MIME validation rules; storage path scheme.
- integration: upload each kind; oversized file rejected; non-member download 403; artifact attached to correct message; reply-to works with artifact.
- e2e: upload image → download it back via member.

---

## Phase 6 — Frontend (React + Vite)

**Status: done.**

Deliverables: SPA with Telegram-like UI — auth screens (OTP request/verify/register), left sidebar (chat list, contacts, search), right pane (message bubbles, reply preview, input, attach menu), group creation (private/public), invite accept dialog, profile page, block button, dark theme.

Stack: Vite + React + TypeScript, react-router, TanStack Query (data fetching), CSS variables (Telegram-like palette).

Tests (this phase): component tests via Vitest + Testing Library for critical components (bubble, reply preview, chat list).

---

## Phase 7 — Playwright e2e

**Status: done.**

Deliverables: `frontend/e2e/` with Playwright config (dev servers started automatically), specs covering user journeys:
1. Register → land in empty chat list.
2. Add contact by username → open private chat → send message → reply → edit → delete.
3. Create private group → button-invite second user → second user accepts → both message.
4. Public group via invite link → join → send image artifact.
5. Block user → blocked user cannot message (error surfaced in UI).

---

## Phase 8 — Nginx + Docker + docs

**Status: done.**

Deliverables: `deploy/nginx.conf` (static frontend build, `/media/` alias, `/api` proxy to uvicorn), `docker-compose.yml` (backend + frontend build + nginx), README run instructions, final endpoint table refresh in [04-api-endpoints.md](04-api-endpoints.md).

---

## Definition of done (global)

**Status: done** — backend suite green (230/230: unit + integration + e2e), Playwright e2e green (7/7). Typecheck/lint/pyright jobs only exist in `.gitlab-ci.yml` when present; none configured in this repo yet.

- All phases' tests green: `pytest` (unit+integration+e2e) and `playwright test`.
- Full typing; mypy/pyright clean (per CI jobs in `.gitlab-ci.yml`).
- No real/persistent data touched by tests (isolated DB + tmp media).
