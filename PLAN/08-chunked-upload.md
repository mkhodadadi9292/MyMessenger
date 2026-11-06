# 08 — Chunked uploads via file-service + Redis Streams

Status: **approved** — decisions D1–D10 answered (see §9: all recommendations accepted, D1=b, D2=a).

Goal: large artifacts are uploaded in resumable chunks to `file-service`. When the file is assembled and verified, file-service tells the backend over Redis Streams. The backend creates the message + artifact and broadcasts `message.new` exactly as today. `file-cleaner` removes only files that are provably unreferenced. Kafka is removed.

Section 9 lists the decisions I need from you. Several sections show two variants that depend on those answers.

---

## 1. What exists today

### 1.1 file-service (copied in, untracked)

| Aspect | Current state |
|---|---|
| Stack | FastAPI, SQLAlchemy async + `asyncpg`, `redis` async, `pydantic-settings`, `cryptography`, `pillow`, `mutagen` (declared but never imported). `requires-python >=3.14`. |
| Layout | `core/{entities,interfaces,use_cases,errors}`, `infrastructure/{data,redis,security,file_processing,di,migrations}`, `routers/`, `schemas/`. Interfaces are a mix of ABCs and plain classes. DI is module-level globals in `infrastructure/di/providers.py`. |
| Settings | Pydantic v1-style `class Config`, a module-level `settings = Settings()` singleton. Required: `database_url`, `redis_url`, `storage_path`, `cleanup_api_key`. |
| Auth | Reads the user's `access_token` **cookie** and validates a hand-parsed Ed25519-signed JWT with a committed public key (`infrastructure/key/public_key.pem`). Uses the `public_id` claim. Two different public keys are committed (`key/` and `file-key/`). |
| Upload protocol | `POST /upload/start` returns `session_id` (Redis key, 6 h TTL, then 600 s sliding). `POST /upload/chunk` is multipart and **strictly sequential** (`chunk_number == last + 1`), appends to `{storage_path}/files/{session_id}`, and reads each chunk fully into memory. There is no resume query, no abort, no size/MIME limits and no idempotency (re-sending a chunk fails). |
| Hashing | A **hash chain**, `sha256(prev_digest_bytes + chunk)`, not the SHA-256 of the file. It cannot be checked against a client-side file checksum. For resized images it hashes the whole file at the end (streamed, 1 MiB reads). |
| Other features | Content dedup by hash with `usage_count` refcounts, thumbnails (Pillow/ffmpeg), image crop/resize, chunked download with Ed25519 "signature" for private files, `protected_count`, Redis metadata cache, `/metadata` batch, `/commit/{lookup_key}`. |
| DB | Postgres tables `files` and `uploading_files`, created with `Base.metadata.create_all` at startup. The Alembic folder is broken: `env.py` imports `data.models.user_model` (does not exist), and there is no `alembic.ini` and no versions. |
| Storage | `{storage_path}/files/{id}` (no extension) and `{storage_path}/thumbnails/{id}.jpg`. Partial files sit in the same directory as finished ones. |
| Broker | **Redis Streams already**: consumers on `file.delete.requests` and `file.protect.requests`. `XREADGROUP` uses `block=0`, and `XACK` runs in `finally`, so failed messages are acked and lost. No `XAUTOCLAIM`, no retry limit, no DLQ. Also Redis **keyspace notifications** (`__keyevent@1__:expired`) delete partial files when a session key expires. This needs `notify-keyspace-events Ex` on DB 1, and the listener reuses one long-lived DB session. **No Kafka.** |
| Errors | Every exception becomes HTTP 500. |
| Docker | `FROM a_base_python:latest` (not available here). `.dockerignore` excludes `pyproject.toml` and `uv.lock`, then the Dockerfile runs `uv add ...`, so the build cannot be reproduced. CORS is `*` with credentials. |
| Tests | **None.** |

### 1.2 file-cleaner (copied in, untracked)

| Aspect | Current state |
|---|---|
| Stack | APScheduler (timezone `Asia/Tehran`), SQLAlchemy async (but **no DB driver declared**), `redis`, `httpx`, **`aiokafka`**, `pydantic-settings`. `requires-python >=3.14`. Same broken Dockerfile pattern. |
| Jobs | (a) every 3 h: rows in `uploading_files` whose Redis session key is gone are cleaned via `POST {file_service}/internal/cleanup/{id}`; (b) daily 20:00: `files.committed = false` and `last_seen_at` older than 60 min are deleted via `POST /internal/cleanup/file/{id}` and Kafka `file.cleaner.deleted`; (c) daily 03:00: **private, unprotected files older than 30/90/180 days by size class are deleted**. |
| State access | Reads **file-service's Postgres tables directly**. It duplicates their models, and they have already drifted (`usage_count` default 0 vs 1). It also reads Redis session keys. |
| Broker | **Kafka** producer (`aiokafka`) to topic `files.cleaner.events`. This is the only Kafka usage in the whole repo. |
| Safety | Rule (c) deletes files purely by age, which would delete files still referenced by messages. Rule (b) depends on `committed`, which is set as a side effect of `/metadata` reads. |
| Tests | **None.** |

### 1.3 Main backend: database reality vs docs

The code is the source of truth. **The main backend runs on SQLite, not PostgreSQL**:

| Where | Value |
|---|---|
| `pyproject.toml` | Only `aiosqlite`. No `asyncpg` or `psycopg`. |
| `app/config.py` | Default `sqlite+aiosqlite:///./data/messenger.db`. |
| `.env.example` | Same SQLite URL. |
| `docker-compose.yml` | `sqlite+aiosqlite:////data/messenger.db` on volume `messenger-db`. There is no Postgres service. |
| `alembic/env.py` | Uses `Settings().database_url` with an async engine and `NullPool`. Dialect-agnostic. |
| `app/infrastructure/db/session.py` | `create_async_engine(url)` with default pooling and no pool settings. It enables `PRAGMA foreign_keys` for SQLite. |
| `tests/conftest.py` | Shared in-memory SQLite (`StaticPool`), with the schema from `create_all`. |
| `tests/integration/test_artifacts.py` | Overrides settings with a tmp-file SQLite URL, but `conftest` replaces the engine with in-memory anyway. |
| Playwright | `data/e2e-playwright.db` (SQLite), wiped and migrated by the webServer command. |
| Docs | `CLAUDE.md`, `PLAN/README.md`, `PLAN/01`, `PLAN/02` and `README.md` say "SQLite (→ Postgres later)". This **matches the code**. Your task statement (Postgres) does not. |

Alembic: exactly one head, `c4e7a1b9d2f3` (`add_message_reactions`, pulled from `origin/dev`; checked with `alembic heads`). The existing migrations use only generic types, so they should run on Postgres unchanged (to be verified if decision D1 = migrate).

Baseline after `git pull --rebase origin dev`: `uv run pytest` gives **269 passed**.

### 1.4 Other facts that shape the design

- `ArtifactKind` is only `image | video | audio` with a fixed MIME allow-list (`app/domain/value_objects.py`). file-service also has a `file` kind, which will not be used.
- `MessageOut` carries `reactions` (added on `origin/dev`). `message_to_out` is kept exactly as on dev; nothing reaction-related is changed.
- `ArtifactService.__init__` constructs a `MessageService` itself, and `ws.py::_handle_send` builds repositories and `MessageService` by hand.
- **Existing bug:** `deploy/nginx.conf` has no `client_max_body_size`, so nginx's 1 MB default already rejects artifact uploads (and avatars) over 1 MB in Docker with 413, even though `MAX_ARTIFACT_SIZE_MB=20`.
- Media URLs are `/media/{file_path}` with `file_path = "artifacts/<uuid4hex><ext>"` (`LocalStorage.save`). Nginx serves the `messenger-media` volume read-only. The backend dev server mounts `/media` with `StaticFiles`.
- `ConnectionManager` is in-process memory, so a broadcast only reaches sockets connected to the same backend process.
- Local toolchain: Docker 29 is available, and the `redis:7-alpine` image is cached. There is no local `redis-server`, `psql` or Postgres image. The local `.venv` is Python 3.14.6, while the project targets 3.13 (`python:3.13-slim` image).

---

## 2. Mismatches and how each is aligned

| # | Mismatch | Alignment |
|---|---|---|
| M1 | Python `>=3.14` (services) vs `>=3.13` / `python:3.13-slim` (backend) | Both services use `requires-python >=3.13` and the same `python:3.13-slim` + `uv sync --frozen` Dockerfile pattern. Each gets its own `uv.lock`. |
| M2 | Dependency manager: `uv add` inside Docker, lock files ignored | Use `uv` locally with committed `uv.lock`. `.dockerignore` no longer excludes them, and images run `uv sync --frozen --no-dev`. |
| M3 | Settings: v1 `class Config` + module singleton | Use `SettingsConfigDict(env_file=".env", extra="ignore")` + `@lru_cache get_settings()`, and pass settings into a `create_app(settings)` factory, like `app/main.py`. No import-time globals, so tests can inject settings. |
| M4 | Layering: `core/` + `infrastructure/` + module-global DI | Each service becomes a package that mirrors the backend: `file_service/{domain,application,api,infrastructure}` and `file_cleaner/{domain,application,infrastructure}`. Ports are ABCs in the domain, implementations live in infrastructure, and wiring lives only in `api/deps.py` / a composition function. The distinct package names avoid clashing with the backend's `app`. |
| M5 | Naming: `session_id`, `lookup_key`, `public_id`, `chunk_number` starting at 1 | `upload_id` (32-hex, issued by the backend), `user_id` (int, as in the backend), `chunk index` starting at **0**. Snake_case event fields and dotted stream names. |
| M6 | JWT: Ed25519 cookie token, hand-parsed, `public_id` claim; backend uses HS256 PyJWT Bearer with `sub` | The upload ticket is an HS256 JWT made with **PyJWT** (already a backend dependency) and signed with `UPLOAD_TICKET_SECRET`, which is separate from `JWT_SECRET`. The backend refuses to start if the two are equal. It is sent as `Authorization: Bearer <ticket>`. Claims: `iss=messenger-backend`, `aud=file-service`, `typ=upload`, plus the upload claims. The cookie auth and the Ed25519 keys are removed, and `cryptography` is replaced by `pyjwt`. |
| M7 | DB driver: `asyncpg` hard-wired; backend `aiosqlite` | Depends on D1/D2. The repositories use only portable SQL (compare-and-set `UPDATE … WHERE status=…`, `IntegrityError` on unique violation) so they run on both SQLite (fast tests) and Postgres. |
| M8 | Storage paths: `files/{id}` without extension, partials next to finals, own download endpoint | Final file: `{MEDIA_ROOT}/artifacts/{uuid4hex}{ext}`, the same scheme as `LocalStorage`. The extension comes from the **verified MIME type**, not the user's file name. Chunks: `{UPLOAD_CHUNKS_ROOT}/{upload_id}/{index}.part`, on a separate, never-served volume. |
| M9 | Media URL scheme: file-service serves its own downloads | Files are served exactly as today: `/media/artifacts/...` via nginx (prod) or `StaticFiles` (dev). `Artifact.file_path` stays relative to the media root. The download/thumbnail/metadata endpoints are dropped (see D4). |
| M10 | Message broker: Kafka (cleaner) + Redis Streams with ack-in-finally (service) | One small Redis Streams module per service with consumer groups, ack after commit, `XAUTOCLAIM`, a retry limit and a DLQ (§5). Kafka code and dependencies are removed. There is nothing Kafka-related in compose, env files or docs to remove; `grep` confirms it. |
| M11 | Errors all become 500 | Domain exceptions map to 400/401/403/404/409/413/422, with the same `{detail}` body as the backend. |
| M12 | `create_all` at startup, broken Alembic | A proper Alembic setup per service that owns a DB (§6). Migrations run on container start, like the backend. |
| M13 | Cleaner reads file-service tables directly, with duplicated models | The cleaner owns no schema and reads no DB (D6, recommended): it calls file-service's internal API, and file-service performs every deletion. |
| M14 | `Asia/Tehran` cron times | Plain configurable intervals in seconds (UTC timestamps throughout). |
| M15 | `reactions` in the payload | Present on dev; `message_to_out` untouched (§1.4). |

---

## 3. End-to-end flow

```
Browser                    Backend (/api/v1)                file-service (/files/v1)            Redis
  │ sha256(file) incrementally │                                   │                              │
  │ POST /chats/{id}/uploads ─▶│ membership, block, kind/MIME,     │                              │
  │                            │ size, reply → sign ticket         │                              │
  │◀─ {upload_id, ticket, …} ──│                                   │                              │
  │ POST /uploads  (Bearer ticket) ──────────────────────────────▶│ create session               │
  │ PUT /uploads/{id}/chunks/{i} ×N (≤3 parallel, retry) ────────▶│ stream to disk, atomic rename│
  │ GET /uploads/{id}  (resume) ─────────────────────────────────▶│ list received chunks         │
  │ POST /uploads/{id}/complete ─────────────────────────────────▶│ assemble streaming, verify   │
  │◀─ 202 ─────────────────────────────────────────────────────────│ size+sha256+MIME, rename     │
  │                            │                                   │ commit → XADD upload.completed ─▶│
  │                            │◀── XREADGROUP (lifespan consumer) ─────────────────────────────────│
  │                            │ verify ticket, re-check membership/block, insert message+artifact  │
  │                            │ (unique upload_id) → COMMIT → broadcast message.new                │
  │◀══ WS message.new ═════════│ → XADD upload.outcome (attached|rejected) → XACK ─────────────────▶│
  │                            │                                   │◀── XREADGROUP outcome ────────│
  │                            │                                   │ status attached / rejected   │
                          file-cleaner ── internal API ──▶ file-service purges only safe states
```

---

## 4. Protocols

### 4.1 Backend: upload ticket (new, `U1`)

`POST /api/v1/chats/{chat_id}/uploads` 🔒 (user Bearer token)

Request:
```json
{"file_name": "clip.mp4", "size_bytes": 7340032, "mime_type": "video/mp4",
 "kind": "video", "sha256": "<64 lowercase hex>", "reply_to_id": null}
```

Response `201`:
```json
{"upload_id": "<32 hex>", "ticket": "<jwt>", "upload_url": "/files/v1/uploads",
 "expires_at": "2026-11-06T12:00:00Z"}
```

Rules come from the existing domain and are applied in the application layer (`UploadService`):

| Case | Status |
|---|---|
| chat not found | 404 |
| not a member / blocked in a private chat | 403 |
| `kind` not in `ArtifactKind` / malformed body | 422 (FastAPI validation, as today for T1) |
| MIME not accepted by kind; `size_bytes <= 0` or `> MAX_ARTIFACT_SIZE_MB`; `sha256` not 64 hex; `file_name` empty or > 255; reply target missing or in another chat | 400 (404 for a missing reply target, as `resolve_reply` does today) |

Ticket claims: `iss, aud, typ="upload", sub=user_id, upload_id, chat_id, kind, mime_type, size_bytes, sha256, file_name, reply_to_id, iat, exp`. I added `file_name` so the stored artifact name cannot be changed after authorization. TTL is `UPLOAD_TICKET_TTL_SECONDS`, default **3600**: long enough for a 20 MB upload on a slow link, short enough to bound replay. The backend does **not** store issued tickets. It re-verifies the signature when the ticket comes back inside the completion event, so file-service cannot forge chat or user ids.

### 4.2 file-service HTTP API (`/files/v1`, behind nginx `/files/`)

Every call carries `Authorization: Bearer <ticket>`, and the `upload_id` in the path must equal the ticket's `upload_id` (401 otherwise). file-service never interprets `chat_id`, `reply_to_id` or `kind`. It only uses `upload_id, sub, mime_type, size_bytes, sha256` and forwards the raw ticket.

| Step | Request | Success | Errors |
|---|---|---|---|
| init | `POST /files/v1/uploads` (empty body) | `201` new / `200` existing active session (idempotent): `{upload_id, status, chunk_size, total_chunks, received_chunks: [], expires_at}` | 401 bad/expired/tampered ticket · 409 session already completed/aborted/rejected · 413 `size_bytes` > `MAX_UPLOAD_SIZE_BYTES` |
| chunk | `PUT /files/v1/uploads/{id}/chunks/{index}` · `Content-Type: application/octet-stream` · `Content-Length` required · raw body | `200 {upload_id, index, size_bytes}`; re-sending the same index overwrites atomically and returns 200 | 400 index out of range · 411 no Content-Length · 413/400 length ≠ expected for that index (exact match; the body is cut off once it exceeds the expected length) · 404 unknown session · 409 session not `active` |
| status | `GET /files/v1/uploads/{id}` | `200 {upload_id, status, chunk_size, total_chunks, received_chunks: [0,1,4], expires_at}` (received chunks = `.part` files on disk) | 401 · 404 |
| complete | `POST /files/v1/uploads/{id}/complete` | `202 {upload_id, status: "completed"}`. Idempotent: calling again returns 202 | 409 `{detail, missing_chunks: [...]}` · 422 size / sha256 / MIME mismatch (session → `failed`, chunks and partial deleted) · 409 aborted/expired |
| abort | `DELETE /files/v1/uploads/{id}` | `204`; idempotent for already-aborted sessions | 409 already `completed`/`attached` (too late: a message may exist) |

Chunk math (domain value object `ChunkPlan`): `total_chunks = ceil(size_bytes / chunk_size)`; the expected length is `chunk_size` for every index except the last, which is `size_bytes - chunk_size*(total_chunks-1)`. Out-of-order chunks are fine. Only the set of present indices matters.

**Streaming, never whole files in memory:**
- chunk PUT: `async for piece in request.stream()` → write to `{index}.part.tmp` in pieces of at most 64 KiB → `os.replace` to `{index}.part`. Memory per request stays at about one network buffer. No multipart parsing, so file-service does not need `python-multipart`.
- complete: compare-and-set the status `active → assembling` and record the planned `file_path`, then commit. Next, read the parts in index order in 1 MiB reads, write to `{MEDIA_ROOT}/artifacts/.{upload_id}.partial`, and update `hashlib.sha256` and a byte count as data is written. Then check `size == ticket.size_bytes` and `sha256 == ticket.sha256`, and sniff the MIME type from the first bytes against `ticket.mime_type`. On success, `os.replace` to `artifacts/{uuid}{ext}` (same filesystem, so atomic), set the status to `completed`, commit, `XADD upload.completed`, and delete the chunk directory.
- MIME sniffing reuses file-service's magic-byte idea but returns concrete MIME types: PNG, JPEG, GIF, WEBP; MP4/QuickTime by `ftyp` brand (`qt  ` → QuickTime); WEBM (EBML); MP3 (ID3 / frame sync); OGG; WAV. Only the backend's allow-list is accepted.
- The final file name is generated by file-service. The backend also checks `file_path` against `^artifacts/[0-9a-f]{32}\.[a-z0-9]{2,5}$` before storing it, so path traversal is impossible.

**Default chunk size: 1 MiB (`UPLOAD_CHUNK_SIZE_BYTES=1048576`).**
- Request count: 20 MiB (`MAX_ARTIFACT_SIZE_MB=20`) means **20 PUTs**. With 3 in parallel that is about 7 round-trips. 256 KiB would mean 80 PUTs, each with a JWT check and a DB touch. 8 MiB would mean 3, but a failed retry would resend up to 8 MiB.
- Proxy limits: nginx `client_max_body_size 2m` on `/files/` (chunk + headroom) is the smallest change from today's 1 MB default and well below common CDN/proxy caps. `proxy_request_buffering off` streams bodies to file-service.
- Memory: the server streams, so memory per request does not depend on chunk size. On the client, `file.slice()` means only about 3 × 1 MiB is in flight.
- Progress granularity is 5% steps for a 20 MB file, which is good enough with fetch (no per-byte upload progress).
- Retry cost on a flaky mobile link is at most 1 MiB per failure.
- The value is configurable and **returned by init**, so the client never hard-codes it. Playwright sets 256 KiB to keep the "more than one chunk" test small and fast.

### 4.3 Upload session states (file-service domain)

```
active ──complete──▶ assembling ──ok──▶ completed ──outcome attached──▶ attached   (terminal, never purged)
  │                      │                  └──outcome rejected──▶ rejected ──purge──▶ purged
  │                      └──verify fail──▶ failed ──purge──▶ purged
  ├──abort──▶ aborted ──purge──▶ purged
  └──idle > TTL──▶ expired ──purge──▶ purged
```
Every transition is a compare-and-set `UPDATE … WHERE upload_id=? AND status=?`, so concurrent `complete`/`abort`/outcome/cleaner calls are safe without database-specific locks.

---

## 5. Redis Streams design

| Item | Value |
|---|---|
| Client | `redis` (async, `redis.asyncio`), `decode_responses=True` |
| Streams | `upload.completed` (file-service → backend), `upload.outcome` (backend → file-service) |
| Dead-letter | `upload.completed.dead`, `upload.outcome.dead` |
| Groups | `messenger-backend` on `upload.completed`; `file-service` on `upload.outcome`. Created with `XGROUP CREATE … $ MKSTREAM` (idempotent; BUSYGROUP is ignored) |
| Consumer name | `{hostname}-{pid}` |
| Trim | `XADD … MAXLEN ~ 100000` (bounded memory; far above any realistic backlog) |
| Persistence | Redis started with `--appendonly yes` on its own volume |

**`upload.completed` fields** (all strings, `schema_version="1"`):
`event_id` (uuid4 hex), `type="upload.completed"`, `upload_id`, `ticket` (the original signed JWT), `file_path`, `size_bytes`, `sha256`, `mime_type`, `completed_at` (ISO-8601 UTC).

**`upload.outcome` fields:** `event_id`, `type="upload.attached"|"upload.rejected"`, `upload_id`, `message_id` and `artifact_id` (attached only), `reason` (rejected only: `chat_not_found | not_member | blocked | invalid_ticket | invalid_event | too_old`), `decided_at`.

A shared contract fixture, `contracts/upload-events.v1.json` at the repo root, is used by both test suites so the producer and consumer cannot drift.

**Backend consumer** (`app/infrastructure/streams/` + `app/application/upload_attach_service.py`):
1. `XREADGROUP GROUP messenger-backend <me> COUNT 10 BLOCK 5000 STREAMS upload.completed >`
2. For each entry, open a **new session from a dedicated consumer session factory** (never `get_db`) and call `UploadAttachService.handle(event)`:
   - verify the ticket signature (`aud`, `iss`, `typ`; expiry is ignored here, but `iat` must be newer than `UPLOAD_EVENT_MAX_AGE_SECONDS`, default 6 h, otherwise rejected with `too_old`);
   - check that the event's `size_bytes / sha256 / mime_type` equal the ticket's, and that `file_path` matches the safe pattern and exists under `MEDIA_ROOT`;
   - fast path: if an artifact with this `upload_id` already exists, the outcome is `attached` with the existing ids (no new insert);
   - re-check that the chat exists, membership, the private-chat block rule, and the reply target (see D8);
   - insert the message, then the artifact with `upload_id`. A unique violation on `ux_artifacts_upload_id` (`IntegrityError`) leads to rollback, loading the existing artifact, and an `attached` outcome. **This unique constraint is what guarantees idempotency**; the existence check is only an optimization;
   - `COMMIT`.
3. **Only after the commit succeeds:** call `broadcast_new_message(...)` (same payload builder as today, with the reply preview), then `XADD upload.outcome`, then `XACK`.
4. Transient failure (DB down, Redis error) means **no ack**. The entry stays pending.
5. Recovery loop every `STREAM_CLAIM_INTERVAL_SECONDS` (30): `XAUTOCLAIM … min-idle STREAM_CLAIM_MIN_IDLE_MS (60000)` re-processes stuck entries from dead or failed consumers. `XPENDING` (extended form) supplies `times_delivered`. Above `STREAM_MAX_DELIVERIES` (5), the entry is copied to `upload.completed.dead` with `source_id`, `deliveries` and `error`, and acked. **Exception:** if an artifact for that `upload_id` already exists (the commit succeeded but publishing failed), the entry is never sent to the DLQ. It keeps retrying the outcome publish, so a referenced file is never treated as unattached.
6. Permanent errors (bad signature, missing fields) go straight to the DLQ + ack, and `upload.rejected/invalid_*` is published when `upload_id` can be read, so the file gets cleaned.
7. Duplicates (re-delivery after a crash between commit and ack) produce exactly one message. The broadcast is repeated, which is harmless because `ChatWindow` already de-duplicates by `message.id`. The outcome is re-published, and file-service applies it idempotently.

**Why a lifespan task in the backend process, not a separate process:** `ConnectionManager` is in-process. A separate consumer process could not reach the WebSocket clients without an extra fan-out layer (Redis pub/sub), which is new infrastructure. The task is started in `create_app`'s lifespan only when `REDIS_URL` is set (tests leave it unset and drive the consumer directly). On shutdown it sets a stop event, the loop exits within one `BLOCK` (≤5 s), the task is awaited (cancelled after a timeout), and Redis is closed.

**file-service side:** the outcome consumer works the same way (ack after its own commit, XAUTOCLAIM, DLQ). An **outbox** step makes "commit, then XADD" safe: `upload_sessions.completed_event_id` stays NULL until the XADD succeeds, and a relay loop re-publishes `completed` rows with a NULL event id that are older than 30 s. Duplicates are harmless because the backend is idempotent.

---

## 6. Databases, migrations, pools, test databases

### 6.1 Ownership

- The backend database belongs only to the backend. file-service and file-cleaner never connect to it, and the backend never connects to file-service's storage.
- file-service owns its upload-session state (D2). The cleaner owns **no** state (D6).

### 6.2 Backend migration (exactly one, on top of head `c4e7a1b9d2f3`)

`add_upload_id_to_artifacts`:
```python
op.add_column("artifacts", sa.Column("upload_id", sa.String(32), nullable=True))
op.create_index("ux_artifacts_upload_id", "artifacts", ["upload_id"], unique=True)
# downgrade
op.drop_index("ux_artifacts_upload_id", table_name="artifacts")
op.drop_column("artifacts", "upload_id")
```
- The column is nullable, so existing artifact rows stay valid. Both SQLite and Postgres allow many NULLs in a unique index.
- A unique **index** (not a table constraint) works with plain `ALTER TABLE` on SQLite, so no batch-mode table rebuild is needed.
- The ORM model gets `upload_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)`, named so autogenerate produces no diff. The domain `Artifact` gets `upload_id: str | None = None`, and the repository gets `get_by_upload_id`.
- If D1 = migrate to Postgres, there are no further backend schema changes. Only the URL, driver and pool change.

### 6.3 file-service schema (variant per D2)

**D2-a (recommended if D1 = Postgres): own Postgres database.** Database `file_service`, role `file_service` (LOGIN, owner of only that database; `REVOKE CONNECT … FROM PUBLIC` on both databases, so `messenger` cannot reach `file_service` and vice versa). Its own Alembic setup in `file-service/alembic/` with its own history, starting with one revision that creates:

`upload_sessions(upload_id varchar(32) PK, user_id bigint NOT NULL, mime_type varchar(128) NOT NULL, size_bytes bigint NOT NULL, sha256 char(64) NOT NULL, chunk_size int NOT NULL, total_chunks int NOT NULL, status varchar(16) NOT NULL, file_path varchar(255) NULL, ticket text NOT NULL, completed_event_id varchar(32) NULL, failure_reason varchar(64) NULL, created_at, last_activity_at, completed_at NULL, decided_at NULL timestamptz)`, plus index `ix_upload_sessions_status_last_activity_at (status, last_activity_at)` for the cleaner queries.

The old `files` / `uploading_files` tables are not carried over (there is no existing file-service database in this repo).

Docker DB bootstrap: an idempotent `deploy/postgres/init-file-service.sh`, built from `SELECT … WHERE NOT EXISTS` + `\gexec` (create role, create database, revoke). It is run by a one-shot `db-init` compose service **on every `up`**, not only through `/docker-entrypoint-initdb.d` (that only runs on a fresh volume). `file-service` depends on `db-init: service_completed_successfully` and runs `alembic upgrade head` before uvicorn.

**D2-b: Redis.** A hash per session plus a sorted set per status scored by timestamp (for cleaner range queries). There is **no TTL on `completed` records**, because an expired record would leave an orphaned public file that can never be found again, so Redis has to act as a durable store (AOF). Simpler to run, weaker durability, and no Alembic. Only recommended if D1 = stay on SQLite, to avoid running a Postgres server just for file-service.

### 6.4 Connection pools (only relevant with Postgres; default `max_connections=100`)

| Client | Pool | Max connections |
|---|---|---|
| backend request engine | `pool_size=10, max_overflow=5` | 15 |
| backend stream-consumer engine (separate, so request load cannot starve it) | `pool_size=2, max_overflow=0` | 2 |
| backend Alembic on start | `NullPool` | 1 (transient) |
| file-service engine | `pool_size=5, max_overflow=5` | 10 |
| file-service Alembic on start | `NullPool` | 1 (transient) |
| file-cleaner | none (HTTP only) | 0 |
| psql / db-init / admin margin | — | ~5 |
| **Total** | | **~34 / 100**, room for a second backend replica |

All engines: `pool_timeout=10`, `pool_recycle=1800`, `pool_pre_ping=True`, and asyncpg `server_settings={"statement_timeout": "15000"}`. They are configurable via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS` (and `CONSUMER_DB_POOL_SIZE`), applied only when the dialect is not SQLite.

### 6.5 Test databases

- **Backend:** keep the existing strategy (shared in-memory SQLite + `create_all`; `CLAUDE.md` forbids going back to file databases). All new backend code stays dialect-portable. Additional modules:
  - migration test: `alembic upgrade head`, then `downgrade -1`, then `upgrade head` on an **empty disposable database**. With D1 = Postgres, that is a testcontainers Postgres database created and dropped by the fixture. With SQLite, it is a tmp-file database (one test, ≈40 DDL statements, a few seconds).
  - idempotency-under-concurrency test (two consumers, same event, exactly one row), on Postgres when D1 = Postgres.
- **file-service:** unit tests (no IO); HTTP integration tests with tmp directories plus in-memory SQLite through the same portable repositories (fast, consistent with the backend); a Postgres-marked module for its migrations (D2-a).
- **Redis:** a real `redis:7-alpine` container started once per test session via `testcontainers` (or `TEST_REDIS_URL` if provided for CI), with `FLUSHDB` between tests. The fixture refuses URLs that do not point at that container or an explicit `TEST_REDIS_URL`. `fakeredis` is used only for unit tests of the publisher/consumer wrappers, and only for commands it supports (`XADD/XREADGROUP/XACK/XPENDING`). XAUTOCLAIM and DLQ behaviour is tested only against real Redis.
- **Never touched by tests:** `data/messenger.db`, `media.db`, `data/media`, any compose volume, or dev Redis/Postgres. Playwright uses its own `data/e2e-*` paths and throwaway containers (§8).
- I will not run `alembic downgrade`, `DROP` or any data-deleting command against the dev database without asking.

---

## 7. file-cleaner: rules for the new flow

The cleaner is a small asyncio loop (APScheduler is dropped; one interval per rule). It calls file-service's **internal** API (`/internal/v1/...`, header `X-Internal-Key`, never routed by nginx). file-service performs each deletion with a compare-and-set status guard, so the policy lives in the cleaner and the safety guard lives in file-service.

| Rule | Selects | Deletes | Default timing |
|---|---|---|---|
| R1 stale incomplete | `active` with `last_activity_at < now − UPLOAD_SESSION_TTL` | chunk directory → `expired` → `purged` | TTL 24 h, every 15 min |
| R2 stuck assembly | `assembling` older than `ASSEMBLY_STUCK_TTL` (a crash between DB write and event publish) | `.partial` + planned `file_path` (no event was ever published, so the backend cannot reference it) → `failed` → `purged` | 1 h, every 15 min |
| R3 never attached | `completed` with `completed_at < now − ATTACH_GRACE_PERIOD` **and** the backend group has acked its `completed_event_id` (not pending, not after `last-delivered-id`) **and** the `upload.outcome` group has lag 0 and pending 0 **and** the upload is not in `upload.completed.dead` | final file → `purged` | grace 48 h (must be > backend `UPLOAD_EVENT_MAX_AGE` 6 h; checked at startup), every 1 h |
| R4 rejected / failed / aborted | those statuses with `decided_at`/`last_activity_at` older than `TERMINAL_PURGE_DELAY` | final file (if any) + chunks → `purged` | 10 min, every 15 min |
| R5 leftover chunk dirs | directories in `UPLOAD_CHUNKS_ROOT` whose `upload_id` is unknown or in a terminal state, with mtime older than `ORPHAN_CHUNK_DIR_MIN_AGE` | that directory only | 1 h, every 1 h |

**Never deleted:**
- anything in `attached` state: the purge endpoint returns 409, enforced in SQL with `WHERE status IN (...)`;
- any media file file-service did not create itself (pre-existing T1 artifacts, avatars). file-service only deletes paths stored in its own rows and **never scans `MEDIA_ROOT`**;
- anything whose state cannot be determined (a Redis or DB error, or a group status that cannot be read): the cleaner logs it and skips it.

The old rules are removed: (c) age-based deletion of referenced files violates "never delete a referenced file", and the `committed`/`usage_count` refcount model and the Kafka `file.cleaner.deleted` event have no consumer in this system.

Configuration: `FILE_SERVICE_URL`, `INTERNAL_API_KEY`, `UPLOAD_SESSION_TTL_SECONDS`, `ASSEMBLY_STUCK_TTL_SECONDS`, `ATTACH_GRACE_PERIOD_SECONDS`, `TERMINAL_PURGE_DELAY_SECONDS`, `ORPHAN_CHUNK_DIR_MIN_AGE_SECONDS` and one `*_INTERVAL_SECONDS` per rule. The TTL values are passed as query parameters to `GET /internal/v1/cleanup/candidates`, so file-service stays policy-free.

Dependencies after the change: `httpx`, `pydantic-settings`. Removed: `aiokafka`, `apscheduler`, `sqlalchemy`, `redis`.

---

## 8. Frontend, nginx, Vite, Docker

**`frontend/src/upload.ts`** exports `startUpload(chatId, file, kind, replyToId, {onProgress, signal})`, which returns a handle with `cancel()`:
1. **Incremental SHA-256** over `file.slice()` 1 MiB pieces (D5), reported as progress phase `hashing`.
2. Get a ticket from `api()` (keeps the existing refresh-on-401 behaviour).
3. Init with file-service → `chunk_size`, `total_chunks`, `received_chunks`.
4. Upload the missing indices with **3 concurrent** `fetch` PUTs. Each chunk retries up to 5 times with exponential backoff (500 ms · 2ⁿ + jitter, capped at 8 s) on network errors, 408, 429 and 5xx. Other 4xx errors fail fast.
5. After a temporary connection loss, or when a request runs out of retries while the browser is offline, **resume** with `GET status` and re-queue only the missing chunks.
6. `complete` → 202. The message then shows up through the normal `message.new` WebSocket event (or the polling fallback). Nothing is rendered from the upload response.
7. **Cancel**: `AbortController` aborts the in-flight PUTs, then `DELETE` the session.

Resume after a full page reload is out of scope, because browsers cannot reopen a `File` without the user picking it again.

**`ChatWindow`**: one upload at a time. A thin progress bar with file name + percent (`data-testid="upload-progress"`) and a ✕ button (`upload-cancel`) above the composer. The attach button is disabled while an upload runs. Errors go to the existing `error-banner`. `uploadArtifact` in `api.ts` is removed or kept depending on D3.

**nginx** (`deploy/nginx.conf`):
- `location /files/ { proxy_pass http://file-service:8000; client_max_body_size 2m; proxy_request_buffering off; proxy_read_timeout 60s; }`
- `location ~ ^/media/.*/\. { deny all; }` hides `.partial` staging files.
- `/internal/` is not proxied at all.

**Vite**: `'/files': 'http://localhost:8001'`.

**docker-compose.yml**:
- add `redis` (`redis:7-alpine --appendonly yes`, volume `messenger-redis`, healthcheck `redis-cli ping`);
- add `file-service` (volumes `messenger-media:/data/media` read-write, `messenger-uploads:/data/uploads`; healthcheck on `/health`);
- add `file-cleaner` (`depends_on file-service: service_healthy`);
- with D1/D2-a, add `postgres` (`postgres:17-alpine`, volume `messenger-pg`, `pg_isready` healthcheck) + one-shot `db-init`;
- `depends_on … condition: service_healthy` for Postgres and Redis on backend and file-service; the frontend waits for backend and file-service;
- migrations run on every start in both backend and file-service, so a fresh volume and an existing volume both work.

There is no Kafka or Zookeeper in compose today, so nothing needs removing.

**Playwright**: the webServer list gains a throwaway Redis (`docker rm -f mm-e2e-redis; docker run --rm --name mm-e2e-redis -p 127.0.0.1:6391:6379 redis:7-alpine`), plus Postgres the same way under D1/D2-a, and file-service on :8001 with `data/e2e-uploads`, `data/e2e-media` (shared with the backend) and `UPLOAD_CHUNK_SIZE_BYTES=262144`. Backend and file-service retry Redis/Postgres connections at startup, so it does not matter in what order Playwright starts the servers.

---

## 9. Open decisions — please answer

| # | Decision | Options | My recommendation |
|---|---|---|---|
| **D1** | The backend runs on **SQLite**, not Postgres. | (a) keep SQLite for now and stay Postgres-ready; (b) **move the backend runtime (dev + Docker) to Postgres** as an extra phase before the backend work: `asyncpg`, compose `postgres`, pool settings, Playwright on a throwaway Postgres; unit/integration tests stay on in-memory SQLite, plus Postgres-marked tests | **(b)**, because you described Postgres as the intended main database and several of your requirements (roles, `max_connections`) assume it |
| **D2** | file-service session storage | (a) own Postgres database + role on the same server; (b) Redis (durable, AOF, no TTL on completed records) | **(a) if D1=b**, **(b) if D1=a** |
| **D3** | Old multipart endpoint T1 `POST /chats/{id}/artifacts` | (a) **remove** it (and `ArtifactService.upload`); keep T2 download; (b) keep it as deprecated | **(a)**: one upload path, and the 1 MB nginx limit already breaks T1 in Docker |
| **D4** | file-service features the messenger does not use: dedup/refcount, thumbnails, image resize, private signed downloads, protect counters, metadata cache, `file.delete/protect` streams | (a) **drop** them; (b) keep and adapt them | **(a)**: files are served by nginx `/media`, and nothing in the backend calls these features. Also removes `pillow`, `mutagen`, `cryptography` |
| **D5** | Browser SHA-256 | (a) add **`@noble/hashes`** (small, audited, no dependencies) for streaming hashing; (b) WebCrypto `crypto.subtle.digest`: one-shot only (whole file in memory, 20 MB max) and **unavailable on plain-HTTP non-localhost origins**, e.g. opening `http://<LAN-IP>:8080` from a phone | **(a)** |
| **D6** | How the cleaner reads state | (a) **file-service internal HTTP API**; file-service does every deletion; (b) a read-only DB role on file-service's database + its own deletes | **(a)**: one writer, no duplicated models |
| **D7** | Existing data in the Docker SQLite volume if D1=b | (a) start fresh (dev data only); (b) one-off copy script into Postgres | **(a)**, unless that volume holds data you want to keep |
| **D8** | The reply target was hard-deleted between ticket and attach | (a) attach without the reply; (b) reject the upload | **(a)**, because the user's file is not lost over a missing quote |
| **D9** | Also move `ws.py::_handle_send` and `ArtifactService` onto the new shared composition factory (no hand-built services) | yes / no | **yes**, a small change once the factory exists |
| **D10** | Tests that need real Redis/Postgres (testcontainers / Docker) when Docker is unavailable | (a) **fail** with a clear message; (b) skip | **(a)**: skipping hides regressions |

---

## 10. Existing tests I expect to change (only if D3 = remove T1)

| Test | Why it changes | New form |
|---|---|---|
| `tests/integration/test_artifacts.py::test_upload_image`, `test_upload_video_and_audio`, `test_upload_with_reply` | They call the removed T1 endpoint. The behaviour they protect (an artifact message with the right kind/MIME/size/reply) moves to the consumer | ticket request + `UploadAttachService.handle(fake completed event)`; same assertions on the created message |
| `…::test_upload_kind_mismatch_400`, `test_upload_unsupported_mime_400`, `test_upload_unknown_kind_422`, `test_upload_oversized_400`, `test_upload_non_member_403` | The same validation now runs at ticket time | same status codes against `POST /chats/{id}/uploads` |
| `…::test_download_artifact`, `test_download_non_member_403` | They create their artifact via T1. The download endpoint T2 is unchanged | artifact seeded through the attach service; assertions unchanged |
| `tests/integration/test_messages.py` (reply preview shows the artifact `file_name`) | seeds through T1 | seeded through the attach service; assertion unchanged |
| `tests/e2e/test_group_journey.py` (public group: upload then download) | seeds through T1 | ticket → simulated completion → download; assertion unchanged |
| `frontend/e2e/artifact.spec.ts` | Assertions unchanged. Only `playwright.config.ts` changes (new webServers) | unchanged spec |

If D3 = keep T1, **no existing test changes**; everything below is additive. `tests/unit/test_settings.py` is unaffected (new settings have defaults, and the asserted defaults stay the same).

## 11. New tests (summary; per-test lines go into each service's `TESTING.md`)

- **file-service unit:** `ChunkPlan` math and expected length per index, out-of-range index, idempotent re-put, out-of-order completion, missing chunks on complete, size/MIME/sha256 mismatch, ticket expiry/tamper/wrong audience/wrong upload_id, state-machine transitions and refused transitions, MIME sniffing table.
- **file-service integration (HTTP, tmp dirs, isolated database):** full protocol happy path; resume after a gap; abort; complete is idempotent; no file appears in `MEDIA_ROOT` before verification; outbox relay re-publishes after a simulated XADD failure; outcome consumer marks `attached`/`rejected`; purge refuses `attached`.
- **Redis Streams (real Redis):** publish/consume round-trip; no ack when the commit fails (entry stays pending); redelivery via XAUTOCLAIM after consumer death; duplicate event creates exactly one message; DLQ after `STREAM_MAX_DELIVERIES`; no DLQ when an artifact already exists; contract fixture parses on both sides.
- **Backend:** ticket endpoint (member ok, non-member 403, blocked 403, kind/MIME 400, size 400, bad sha256 400, reply in another chat 400, unknown chat 404); ticket claims and separate secret; the consumer creates exactly one message and broadcasts `message.new` with reply preview to a live WebSocket; the consumer rejects (with no message) when membership is lost or a block appeared; migration upgrade/downgrade/upgrade.
- **file-cleaner:** R1–R5 each select and purge the right thing; R3 skipped while the backend group or outcome group has pending/lag or the upload is in the DLQ; nothing is purged on API errors; `attached` is never purged; grace > max-age check at startup.
- **Playwright:** a file larger than one chunk (256 KiB in e2e) → progress bar visible (chunk PUTs slowed with `page.route`) → the other user sees the image; cancel removes the progress bar and no message appears.

## 12. Phases after approval

1. **file-service alignment + Redis Streams.** Restructure, ticket verification, chunk protocol, streaming assembly, outbox + outcome consumer, Alembic (D2-a), tests, `TESTING.md`.
2. *(if D1=b)* **Backend on Postgres**: driver, pools, compose Postgres + db-init, Postgres-marked tests.
3. **Backend**: shared composition factory, `UploadService` + ticket endpoint, `UploadAttachService` + lifespan consumer, migration `add_upload_id_to_artifacts`, T1 decision (D3), tests.
4. **file-cleaner**: rewrite to R1–R5 through the internal API, remove Kafka, tests, `TESTING.md`.
5. **Frontend + nginx + compose + Playwright.**
6. **Docs**: `CLAUDE.md`, `README.md`, `.env.example`, `PLAN/README.md` (Postgres wording per D1, the new phase, commands, env vars, stream events), and `PLAN/04` (new endpoints).

Each phase: relevant tests green, then a separate commit on `dev`, no push.

New dependencies (each justified):

| Where | Dependency | Why |
|---|---|---|
| backend | `redis` | stream consumer/publisher |
| backend | `asyncpg` (D1=b) | Postgres driver |
| backend dev | `testcontainers` | real Redis/Postgres in tests |
| backend dev | `fakeredis` | unit tests of the stream wrappers |
| file-service | `pyjwt` | replaces `cryptography` |
| file-service | `aiosqlite` (dev) | fast integration tests |
| file-service dev | `pytest`, `pytest-asyncio`, `httpx`, `testcontainers` | test tooling |
| frontend | `@noble/hashes` (D5=a) | streaming SHA-256 in the browser |

## 13. Risks

- **Single backend instance assumed for realtime:** the consumer broadcasts through the in-process `ConnectionManager`. More than one backend replica would need a Redis pub/sub fan-out (out of scope).
- **The backend must see the same media volume** as file-service (it checks that `file_path` exists and serves T2 downloads). This is true in compose and in dev (`./data/media`); it has to hold in any future deployment.
- **The R3 grace period must exceed the backend's max event age.** This is checked at cleaner startup, but the two settings live in different services.
- **`MAXLEN ~ 100000`** would drop unprocessed events only if the backlog ever exceeds 100k entries.
- **Playwright now needs Docker** (throwaway Redis/Postgres containers).
