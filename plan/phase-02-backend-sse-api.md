# Phase 2 — NotificationService, SSE hub, endpoints, event wiring

## SSE hub (`app/infrastructure/sse.py`)

`SseHub` — the SSE twin of `ConnectionManager`:

- `subscribe(user_id) -> asyncio.Queue` (one queue per open stream; several streams per
  user allowed — multiple tabs).
- `unsubscribe(user_id, queue)`.
- `publish(user_id, event: dict)` / `publish_many(user_ids, event)` — `put_nowait` on every
  queue; failures log + drop the queue (a dead stream must not block a sender).
- Registered on `app.state.sse` in `create_app()`.

## NotificationService (`app/application/notification_service.py`)

Ports: `NotificationRepository`, `ChatMemberRepository`, `UserRepository`, `ChatRepository`.

- `notify_message(message, sender) -> list[NotificationDto]` — recipients = chat members
  minus the sender; builds `chat_title` (group title or NULL) and `preview` (text trimmed
  to 120 chars, else `sent <file_name>` / `sent an artifact`); inserts one row per recipient.
- `notify_invite(invite, chat, inviter, invitee) -> NotificationDto` — one row for the invitee,
  preview `invited you to <title>`.
- `list_for_user(user_id, before_id, limit)` — page of DTOs (joins sender usernames).
- `unread_count(user_id)`.
- `mark_read(user_id, chat_id | None) -> int` — bulk mark; returns new unread count.

DTO shape (JSON, used by REST list and SSE events):

```json
{
  "id": 1, "type": "message", "chat_id": 4, "chat_title": null,
  "sender_id": 2, "sender_username": "bob",
  "preview": "hello", "message_id": 9, "invite_id": null,
  "is_read": false, "created_at": "2026-10-23T…"
}
```

## REST endpoints (`app/api/routers/notifications.py`, prefix `/api/v1`)

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| N1 | GET | `/notifications` | `?before_id=&limit=50` | `[{notification dto}]` newest-first | 🔒 |
| N2 | GET | `/notifications/unread-count` | — | `{count}` | 🔒 |
| N3 | POST | `/notifications/read` | `{chat_id?: int}` (null = all) | `{ok:true, unread_count}` | 🔒 |
| N4 | GET | `/notifications/stream` | `?token=<access_token>` | SSE stream (`text/event-stream`) | token (query) |

- N4 auth: `EventSource` cannot send headers → JWT in the query string, same pattern as
  `/ws?token=`. Header `Authorization: Bearer` is also accepted (used by tests/curl).
  Auth check runs before the stream starts (short-lived session via `app.state.session_factory`).
- Stream format: `event: notification.new` + `data: {json}` frames; a `: keepalive` comment
  every 15 s; `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`
  headers; `retry: 3000` so `EventSource` reconnects fast.
- Cleanup: `hub.unsubscribe` in the generator's `finally`.

## Event wiring (commit-before-notify, same as commit-before-broadcast)

One helper in `app/api/notify.py`:

```python
async def notify_new_message(request, session, message, sender) -> None
async def notify_new_invite(request, session, invite) -> None
```

called **after `db.commit()`** at every write path that creates notifications:

1. `messages.py` `send_message` (text)
2. `artifacts.py` upload (artifact message)
3. `ws.py` `_handle_send` (message sent over the socket)
4. `invites.py` `invite_user` (button invite)

Each helper: builds DTOs via `NotificationService`, then
`await app.state.sse.publish(user_id, {"type": "notification.new", "notification": dto, "unread_count": n})`
per recipient. Events go to the recipient's streams only (sender excluded).

## Config / proxy

- Vite dev: the existing `/api` proxy already forwards SSE (`text/event-stream` passes
  through http-proxy); nothing to change.
- Nginx (docker): dedicated location for the stream with `proxy_buffering off`,
  `proxy_cache off`, `proxy_read_timeout 1h`, `proxy_http_version 1.1`,
  `proxy_set_header Connection ""` (see phase 5).

## Definition of done

- All four write paths create notification rows; SSE events reach subscribed recipients;
  REST list/count/read endpoints behave per spec.
- Covered by phase-3 tests.
