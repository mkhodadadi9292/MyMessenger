# 02 — Architecture

## Layering (tech-agnostic, DDD-lite)

```
┌─────────────────────────────────────────────────┐
│  Presentation  (api/)                            │   FastAPI routers, Pydantic schemas,
│  HTTP, auth headers, status codes, Depends()     │   DI wiring, exception→HTTP mapping
├─────────────────────────────────────────────────┤
│  Application   (application/)                    │   Use-case services, orchestration,
│  business workflows, transactions                │   depends ONLY on domain ports (ABCs)
├─────────────────────────────────────────────────┤
│  Domain        (domain/)                         │   Entities, value objects, enums,
│  pure python, no framework imports               │   domain exceptions, repository ABCs
├─────────────────────────────────────────────────┤
│  Infrastructure (infrastructure/)                │   SQLAlchemy models + repos, JWT/OTP,
│  implements domain ports                         │   file storage, DB session
└─────────────────────────────────────────────────┘
```

Dependency rule: **presentation → application → domain**, and everything depends on domain *interfaces*, never on infrastructure. Infrastructure implements domain port ABCs. Wiring happens only in composition root (`api/deps.py`, `main.py`).

## SOLID mapping

- **S** — one router/service/repo per aggregate; schemas only shape I/O.
- **O** — repository ABCs let us add Postgres/file/S3 implementations without touching services.
- **L** — in-memory fake repos (tests) are substitutable for SQLAlchemy repos.
- **I** — small port interfaces (`UserRepository`, `ChatRepository`, …), no god-interfaces.
- **D** — services receive ports via constructor injection; FastAPI `Depends` is the composition root.

## Technology decisions

| Concern | Choice | Why |
|---|---|---|
| Web framework | FastAPI | REST, async, Pydantic v2, OpenAPI docs |
| DB | PostgreSQL via **async** SQLAlchemy 2.0 (`asyncpg`); one server, one database + non-superuser role per service | `aiosqlite` only for the fast default test mode |
| Migrations | Alembic (async template) | required; Postgres-safe DDL |
| Auth | OTP (6-digit, printed in server log) → JWT access + refresh (refresh stored hashed in DB, revocable) | dev-simple, swappable email sender behind `OtpSender` port |
| DI | FastAPI `Depends` | idiomatic, no extra container dependency |
| Settings | pydantic-settings, `.env` | typed config, per-env overrides |
| Storage | local disk `data/media/`; URLs served by Nginx in prod | simple, S3-ready behind `FileStorage` port |
| Tests | pytest + pytest-asyncio + httpx ASGI + testcontainers | unit (no IO), integration (in-memory SQLite or `TEST_DB=postgres`), e2e (full app); real Postgres/Redis containers for migrations, concurrency and streams |
| Messaging between services | Redis Streams (`redis` async client), consumer groups, ack after commit, XAUTOCLAIM, dead letters | replaces Kafka from the original file-service/file-cleaner |
| Frontend | React + Vite + TypeScript | Telegram-like SPA |
| FE tests | Playwright | e2e incl. UI flows |
| Reverse proxy | Nginx | static/media files + proxy to uvicorn |

## Backend folder layout

```
app/
├── main.py                    # create_app() factory, routers, exception handlers
├── config.py                  # Settings (pydantic-settings)
├── api/                       # ── presentation layer
│   ├── deps.py                # get_db, get_current_user, service providers (DI)
│   ├── errors.py              # domain exception → HTTP handler
│   ├── schemas/               # request/response DTOs (Pydantic)
│   └── routers/               # auth, users, contacts, blocked, chats, messages, invites, artifacts
├── application/               # ── application layer (use cases)
│   ├── auth_service.py        # OTP request/verify, register, login, refresh, logout
│   ├── user_service.py        # profile, search, avatar
│   ├── contact_service.py
│   ├── block_service.py
│   ├── chat_service.py        # private chats, groups, members, roles, join/leave
│   ├── invite_service.py      # button invites + temporary links
│   ├── message_service.py     # send/edit/delete/reply, history
│   └── artifact_service.py    # upload/download, kinds
├── domain/                    # ── domain layer (pure python, no framework)
│   ├── entities.py            # User, Chat, ChatMember, Message, Artifact, Contact, Invite
│   ├── value_objects.py       # Username, Phone, ChatType, MemberRole, InviteStatus, ArtifactKind
│   ├── exceptions.py          # DomainError hierarchy
│   └── repositories/          # port ABCs: UserRepository, ChatRepository, ...
│       ├── base.py            # AbstractRepository, CRUD helpers
│       └── ...
└── infrastructure/            # ── infrastructure layer
    ├── db/
    │   ├── session.py         # async engine/session factory
    │   ├── base.py            # DeclarativeBase
    │   └── models/            # SQLAlchemy ORM models (one file per aggregate)
    ├── repositories/          # SQLAlchemy implementations of domain ports
    ├── auth/                  # jwt.py, otp.py (generator + LogOtpSender)
    └── storage/               # local file storage (FileStorage port impl)
alembic/                       # migrations
tests/
├── unit/                      # domain + services with fake/mock repos
├── integration/               # httpx ASGI + test DB (SQLite or TEST_DB=postgres) + tmp storage
├── e2e/                       # full-app flows through HTTP (backend e2e)
└── conftest.py                # fixtures: app, db, auth users, storage
frontend/                      # React + Vite (Phase 6)
deploy/                        # nginx.conf, docker-compose.yml (Phase 8)
```

## Key design rules

1. Domain code never imports `fastapi`, `sqlalchemy`, or `pydantic`.
2. Repositories are ABCs in `domain/repositories/`; SQLAlchemy impls live in `infrastructure/repositories/`.
3. Services never touch ORM objects — they work with domain entities; repositories map ORM ↔ entity.
4. Transactions: one session per request (`get_db`), commit on success, rollback on error.
5. Errors: services raise domain exceptions; `api/errors.py` maps them to 400/401/403/404/409 with a uniform body `{detail: ...}`.
6. Auth: `get_current_user` dependency validates JWT, loads user via repository, enforces active status.
7. Privacy rule enforced in application layer: user DTOs **never** include `phone`; phone search is exact-match only.
8. Blocking enforced in application layer (message sending, inviting, profile access, contact add, upload tickets and upload attachment).
9. Services never build other services or repositories; `app/api/composition.py` is the single factory used by `deps.py`, `ws.py` and the Redis Streams consumer.
10. Side services (`file-service/`, `file-cleaner/`) follow the same layering in their own packages and never touch the backend's database (and vice versa).
