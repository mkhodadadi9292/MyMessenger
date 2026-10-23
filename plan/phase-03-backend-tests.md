# Phase 3 — Backend tests (unit / integration / e2e)

Written first, per the project's test-first rule; implementation lands in phases 1–2.
All tests use the existing isolated in-memory SQLite engine from `tests/conftest.py`
(no file DBs, no real data).

## Unit (`tests/unit/test_notifications.py`)

- `NotificationType.parse("message" | "invite")` ok; unknown value → `ValidationError`.
- `Notification.mark_read()` sets `is_read`; calling it again does not raise (idempotent).
- `NotificationService` with a **fake** `NotificationRepository` (+ fake member/user/chat
  repos): `notify_message` creates rows for every member **except the sender**; preview is
  trimmed text; artifact-less text fallback; `notify_invite` creates exactly one row for the
  invitee; `unread_count`/`mark_read` delegate correctly.

## Integration (`tests/integration/test_notifications.py`, httpx ASGI)

- Register A, B; open private chat; A sends a message →
  - B's `GET /notifications` contains one `message` notification (sender = A, preview = text);
  - A's list is **empty** (sender gets no self-notification);
  - `GET /notifications/unread-count` → B: 1, A: 0.
- Artifact upload by A → B's notification preview mentions the file name.
- Button invite: A creates private group, invites B →
  - B's list gains an `invite` notification; B's unread count increments.
- `POST /notifications/read` with `{chat_id}` clears only that chat's notifications and
  returns the updated `unread_count`; without body clears all.
- Pagination: >1 page via `before_id`; newest-first ordering.
- Auth: all N1–N3 reject missing/bad tokens (401). N4 without token → 401 (or 403).
- Mark-read of another user's notifications is impossible (list is scoped to `current_user`).

## E2E (`tests/e2e/test_notifications.py`, real uvicorn server + httpx streaming)

- `test_sse_stream_requires_token`: GET `/notifications/stream` without token → 401.
- `test_sse_delivers_notification_on_message`: register A, B; open A's SSE stream with
  `httpx.stream`; B sends a message to the private chat (REST); A receives a
  `notification.new` frame (parse `event:`/`data:` lines) with preview + `unread_count == 1`;
  A's REST list then shows the row and `mark_read` zeroes the count.
- `test_sse_invite_notification`: A creates a private group and button-invites B; B's stream
  receives `notification.new` with `type == "invite"` and the invite_id.
- `test_sse_no_self_notification`: the sender's own stream receives **no** event within a
  short window (assert via keepalive/timeout, e.g. the next frame is `: keepalive`).

## Definition of done

`uv run pytest tests/unit/test_notifications.py tests/integration/test_notifications.py tests/e2e/test_notifications.py` green,
and the full backend suite (`uv run pytest`) stays green.
