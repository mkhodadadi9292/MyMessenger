# 08 — Notifications (SSE)

Per-user, per-chat notifications delivered over **Server-Sent Events (SSE)** with a persistent
inbox: unread state survives disconnects and is synced on reconnect via the REST list.

Architecture alternatives and the selection rationale: `knowledge/notification-system-architectures.md`.
Phased plan: `plan/README.md`.

## Requirements

| # | Requirement |
|---|---|
| N-1 | A notification is created for every chat member **except the sender** when a message is sent — via REST, WS send, or artifact upload (text + reply included). |
| N-2 | A notification is created for the invitee when a button invite is created (private group). |
| N-3 | Live delivery over an authenticated SSE stream (`GET /api/v1/notifications/stream`). |
| N-4 | List (cursor-paginated, newest-first), unread count, and mark-read (all or per chat). |
| N-5 | Frontend: bell + unread badge, notification panel, click-through to chat / invites panel, mark-all-read. |
| N-6 | Opening a chat (or reading messages in the open chat) marks its notifications read automatically. |
| N-7 | Works through Nginx (buffering disabled) and the Vite dev proxy; verified with docker compose. |

Out of scope for v1: push while the app is closed (FCM/APNs), device tokens, grouping/coalescing,
multi-instance fan-out (Redis) — seams documented below.

## Architecture

```
send message / invite
   │  (same DB transaction)
   ├──▶ inbox rows  (notifications table, per recipient)
   │
   └── after commit ──▶ SseHub.publish(user_id, event) ──▶ per-user asyncio.Queue
                                                              │
                    GET /api/v1/notifications/stream ◀────────┘
                    (EventSource, auto-reconnect)
```

- **Inbox table**: `notifications` — one row per (recipient, event). Unread badge, history and
  mark-read all come from it; nothing is lost while the user is offline.
- **`SseHub`** (`app/infrastructure/sse.py`): the SSE twin of `ConnectionManager` — maps
  `user_id → set[asyncio.Queue]`; `put_nowait` fan-out; dead queues are dropped (a dead stream
  never blocks a sender). Single-instance; a Redis Pub/Sub layer is the multi-instance seam.
- **Commit-before-notify**: rows are inserted in the same transaction as the business change;
  SSE events are published only **after `db.commit()`**, so a receiver can always refetch what
  the event references (same rule as commit-before-broadcast for WS).
- **Stream endpoint**: auth via `?token=` query param (EventSource cannot send headers — same
  pattern as `/ws`; the `Authorization` header is also accepted). Events:
  ```
  retry: 3000
  event: notification.new
  data: {"type":"notification.new","notification":{…dto},"unread_count":n}
  : keepalive   (every 15 s, sse_keepalive_seconds)
  ```
- **Denormalized snapshots**: `chat_title` and `preview` are copied into the row at write time
  (like push payloads) so the list endpoint is one query + one sender lookup.

## Data model (`notifications`)

| col | type | notes |
|---|---|---|
| id | int PK | cursor for pagination |
| user_id | int FK users | recipient, indexed |
| chat_id | int FK chats | indexed |
| type | str | `message` \| `invite` (`NotificationType` VO) |
| sender_id | int FK users | message sender / inviter |
| message_id | int FK messages NULL | `message` type |
| invite_id | int FK group_invites NULL | `invite` type |
| chat_title | str NULL | snapshot (group title; NULL for private chats) |
| preview | str NULL | snapshot (text ≤120 chars, `sent <file>`, or `invited you to <title>`) |
| is_read | bool default false | |
| created_at | datetime | indexed |

Alembic migration: `a7e5f9c2d4b1_add_notifications`.

## API endpoints (prefix `/api/v1`, 🔒 = Bearer token)

| # | Method | Path | Body / Params | Response |
|---|---|---|---|---|
| N1 | GET | `/notifications` | `?before_id=&limit=` (default 50, max 100) | `[{id, type, chat_id, chat_title, sender_id, sender_username, preview, message_id, invite_id, is_read, created_at}]` newest-first |
| N2 | GET | `/notifications/unread-count` | — | `{count}` |
| N3 | POST | `/notifications/read` | `{chat_id?: int}` (null = all) | `{ok:true, unread_count}` |
| N4 | GET | `/notifications/stream` | `?token=<access_token>` | SSE stream (`text/event-stream`) |

Privacy: payloads never contain phone/email.

## Delivery guarantees & failure modes

- **Offline/disconnected**: rows persist in the inbox; on reconnect the client refetches the
  list and unread count (no gap).
- **Reconnect**: `EventSource` reconnects natively (`retry: 3000`); keepalive comments keep
  proxies from idling out; Nginx has `proxy_buffering off` for the stream location.
- **Ordering**: per-user FIFO queues preserve send order; history uses id-cursor pagination.
- **Duplicates**: not possible in-process; a multi-instance deployment with a broker would need
  id-based dedupe on the client (notification ids are monotonic).
- **Sender never notified of their own message** (recipients = members − sender).

## Where events are produced (wiring)

`app/api/notify.py` (`notify_new_message`, `notify_new_invite`), called after commit in:

| Write path | File |
|---|---|
| REST text message | `app/api/routers/messages.py` (`send_message`) |
| REST artifact upload | `app/api/routers/artifacts.py` |
| WS `message.send` | `app/api/routers/ws.py` (`_handle_send`) |
| Button invite | `app/api/routers/invites.py` (`invite_user`) |

## Frontend

- `frontend/src/sse.ts` — `NotificationClient` over `EventSource` (auto-reconnect; no manual
  retry loop). Singleton `notifications`.
- `frontend/src/components/NotificationsPanel.tsx` — bell (`data-testid="notifications-button"`),
  badge (`notifications-badge`, rendered only when > 0), panel (`notifications-panel`) with
  items (`notification-<id>`), mark-all (`notifications-mark-all`).
- `App.tsx` — connects the stream when logged in, updates the badge from `unread_count` in each
  event; marks read on chat open and on incoming messages in the open chat.
- Vite dev proxy and Nginx both route the stream (no WS upgrade needed).

## Tests

| Layer | File | Covers |
|---|---|---|
| unit | `tests/unit/test_notifications.py` | `NotificationType.parse`, `mark_read` idempotency, service fan-out rules (sender excluded), preview trimming |
| integration | `tests/integration/test_notifications.py` | rows created on message/artifact/invite, unread counts, mark-read scoping, pagination, auth |
| e2e (backend) | `tests/e2e/test_notifications.py` | real SSE stream over uvicorn: event delivery, no self-notification, invite events, 401s |
| component | `frontend/src/__tests__/sse.test.ts`, `notifications-panel.test.tsx` | EventSource mock, badge/panel behavior |
| e2e (frontend) | `frontend/e2e/notifications.spec.ts` | badge via SSE, panel click-through, mark-all, invite accept flow — local and docker (`PW_BASE_URL`) modes |

## Future seams

- **Push (FCM/APNs)**: add `device_tokens` + an outbox relay after the notification insert —
  the inbox rows are already the source of truth.
- **Multi-instance**: swap the in-process `SseHub` for Redis Pub/Sub (each instance pushes to
  its local subscribers).
- **Coalescing**: group repeated `message` rows per (user, chat) with a counter instead of a
  row per message, if volume grows.

## Status: done
