# Phase 1 — Notification domain + persistence

**Goal:** the `Notification` aggregate end to end in the three layers — entity, value object,
repository ABC, SQLAlchemy model, Alembic migration, SQL repository.

## Data model (`notifications` table)

| col | type | notes |
|---|---|---|
| id | int PK | |
| user_id | int FK users | recipient; indexed |
| chat_id | int FK chats | indexed |
| type | str | `message` \| `invite` |
| sender_id | int FK users | who triggered it (message sender / inviter) |
| message_id | int FK messages NULL | for `message` type |
| invite_id | int FK group_invites NULL | for `invite` type |
| chat_title | str NULL | denormalized snapshot (group title; NULL for private chats) |
| preview | str NULL | denormalized snapshot (message text ≤ ~120 chars, artifact file name, or invite text) |
| is_read | bool default false | |
| created_at | datetime | index |

Denormalizing `chat_title` + `preview` at write time keeps the list endpoint to a single
query + one sender lookup (no N+1 over chats/messages). Snapshot semantics are acceptable
for notifications (like push payloads).

## Domain layer

- `app/domain/value_objects.py`: `NotificationType(StrEnum)` — `MESSAGE`, `INVITE` with a
  `parse()` raising `ValidationError` on unknown values.
- `app/domain/entities.py`: `Notification` dataclass (fields above) with `mark_read()`
  (idempotent — marking an already-read notification is a no-op, not an error).
- `app/domain/repositories/notification.py`: `NotificationRepository` ABC:
  - `add(entity)`, `get(id)`
  - `list_for_user(user_id, before_id, limit)` — newest-first cursor page
  - `unread_count(user_id) -> int`
  - `mark_read(user_id, chat_id | None) -> int` — bulk; returns rows affected
  - `delete(entity)`

## Infrastructure layer

- `app/infrastructure/db/models/notification.py`: `NotificationModel` (registered in
  `models/__init__.py`).
- Alembic migration `add_notifications` (chain after `c4e7a1b9d2f3`), Postgres-safe DDL,
  indexes on `user_id`, `chat_id`, `created_at`.
- `app/infrastructure/repositories/notification.py`: `SqlNotificationRepository`.

## Definition of done

- Tests for this phase (written first — see phase 3 test list):
  - unit: `NotificationType.parse`, `Notification.mark_read` idempotency.
  - integration: repository round-trip against the test DB (add → list → count → mark read).
- Migration applies cleanly on SQLite (dev DB) and Postgres (docker).
