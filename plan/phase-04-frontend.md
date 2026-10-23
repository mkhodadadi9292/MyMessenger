# Phase 4 — Frontend: SSE client + notification UI + tests

## SSE client (`frontend/src/sse.ts`)

`NotificationClient` mirroring the style of `ws.ts`:

- Uses browser-native `EventSource` against
  `${location.origin}/api/v1/notifications/stream?token=<access_token>` (Vite proxy and
  Nginx both route `/api`).
- `onEvent(handler)` subscribe pattern; event type `notification.new` (payload:
  `{notification: NotificationOut, unread_count}`).
- `connect()`/`disconnect()`; `EventSource` reconnects natively (server sends `retry: 3000`);
  `onerror` just logs — no hand-rolled reconnect loop (unlike `ws.ts`, this is SSE's
  built-in behavior).
- Exported singleton `notifications`.

## API + types

- `types.ts`: `NotificationOut` (id, type, chat_id, chat_title, sender_id, sender_username,
  preview, message_id, invite_id, is_read, created_at).
- `api.ts`: helpers `fetchNotifications()`, `fetchUnreadCount()`, `markNotificationsRead(chatId | null)`.

## UI

- `App.tsx`: when the user is logged in, `notifications.connect()`, initial unread-count
  fetch, and an `notification.new` handler that updates the unread count and refreshes the
  invites list (invite notifications mirror pending invites). Disconnect on logout.
- `Sidebar.tsx`:
  - bell button (`data-testid="notifications-button"`) with a badge
    (`data-testid="notifications-badge"`, hidden at 0) next to Contacts/Settings;
  - panel (`data-testid="notifications-panel"`) listing the latest notifications
    (fetched via N1, newest first): icon per type, sender name, chat title, preview, time;
  - click on a `message` notification → `markNotificationsRead(chat_id)` + open the chat
    (`onSelectChat`) + close the panel; click on an `invite` notification → open the invites
    panel (accept/decline there) and mark it read;
  - "Mark all read" button (`data-testid="notifications-mark-all"`).
- `ChatWindow.tsx` / `App.tsx`: when a chat is opened (or a new message arrives while the
  chat is open), call `markNotificationsRead(chatId)` and refresh the badge — opening a chat
  clears its unread badge automatically (requirement N-6).
- Styles in `styles.css` (badge dot, panel rows, hover states) following the existing
  Telegram-like palette.

## Tests

### Component/unit (Vitest — new devDependencies: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`)

- `src/__tests__/sse.test.ts`: `NotificationClient` with a mocked global `EventSource` —
  connect builds the right URL with token, incoming `notification.new` events reach
  handlers, `disconnect()` closes the source.
- `src/__tests__/notification-panel.test.tsx`: renders a `NotificationsPanel` with sample
  notifications — shows sender/preview, hides badge at 0, calls the mark-read/select
  callbacks on click.
- Script: `npm test` → `vitest run`.

### e2e (Playwright, `frontend/e2e/notifications.spec.ts`)

Two browser contexts (A and B, `uniqueUser` helpers, OTP via debug endpoint):

1. **Message notification**: A opens a private chat with B and sends "hello there".
   B (sitting on the chat list) gets badge `1` without reloading (SSE), opens the
   notifications panel, sees the item ("hello there"), clicks it → the chat opens and the
   badge disappears (mark-read).
2. **Invite notification**: A creates a private group and button-invites B; B's badge
   increments; B opens the panel, clicks the invite item → the invites panel opens with the
   pending invite; B accepts and lands in the group (badge cleared).
3. **No self-notification**: A's own badge stays at 0 after sending.

Run modes: local webServers (SQLite e2e DB) by default; against docker compose with
`PW_BASE_URL=http://localhost:8080 PW_BACKEND_URL=http://localhost:8080` (phase 5).

## Definition of done

`npm run build` clean, `npx vitest run` green, `npx playwright test` green including the new
spec (local mode), and existing specs unaffected.
