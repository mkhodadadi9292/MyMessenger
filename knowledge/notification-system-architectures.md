# Notification Systems — Architectures & Delivery Options

> Question: how do notification systems work in general, and which architecture fits this messenger (per-user, per-chat notifications)?

## 1. What a notification system is

A notification is a message produced by an *event* (a message was sent, someone invited you, …)
that must reach a specific *recipient* (or a set of recipients) through one or more *channels*.

Every notification system is a small pipeline:

```
event → fan-out/routing → storage (inbox) → delivery → client UI
```

The two hard problems are **routing** (who should get this?) and **delivery** (how does it
reach a possibly-offline client without being lost?).

## 2. Storage models

| Model | Shape | Use when |
|---|---|---|
| **Inbox table** (per-user rows) | one row per (recipient, event): `notifications(user_id, type, payload, is_read)` | per-user state matters: unread counts, mark-as-read, personal history |
| **Activity feed** (global log) | one row per event, read-filtered by recipient at query time | many recipients per event, no per-user mutation (Twitter-style feeds) |
| **Outbox pattern** | event written to a local outbox table in the same DB transaction as the business change, a relay worker publishes it onward | guaranteed delivery to message brokers / push providers; avoids dual-write problems |
| **Ephemeral only** | nothing stored; event is pushed to connected clients and dropped otherwise | pure presence signals (typing indicators) |

Messengers use the **inbox table**: unread state and per-user history are core UX.

## 3. Delivery transports (client ← server)

### 3.1 Short polling
Client re-requests an unread-count/list endpoint on a timer (every 2–5 s).

- **Latency**: up to one interval. **Cost**: request storm, mostly empty responses.
- **Pros**: trivial, stateless, works everywhere, easy to test.
- **Cons**: wasteful, feels laggy; DB hit per poll per user.

### 3.2 Long polling
Client requests; server holds the connection open until an event exists or a timeout (25–30 s) expires.

- **Pros**: low latency, plain HTTP, no protocol support needed.
- **Cons**: one outstanding request per client, connection churn, proxy timeouts to manage.

### 3.3 SSE (Server-Sent Events)
One long-lived HTTP response streams `event:`/`data:` frames over a single connection.

- **Protocol**: `Content-Type: text/event-stream`; client = browser-native `EventSource`.
- **Latency**: low (sub-second).
- **Pros**: dead simple, **built-in auto-reconnect** (with `Last-Event-ID` resync), one-way is exactly what notifications need, plain HTTP (no upgrade), works through standard proxies when buffering is disabled.
- **Cons**: server → client only (sending still uses REST), text-only frames, per-tab connection (not shared), HTTP/1.1 connection-per-stream (HTTP/2 fixes this).

### 3.4 WebSocket
Full-duplex upgraded connection; the server pushes events and the client can send commands.

- **Pros**: one connection carries everything (messages, notifications, typing, acks).
- **Cons**: more lifecycle management (heartbeats, reconnect + resync, backpressure); overkill when the channel is one-directional.

### 3.5 Web Push / mobile push (FCM, APNs)
The *only* channel that reaches a user while the app/tab is closed.

- **Flow**: app registers a device token → backend calls the provider API → provider pushes to the OS.
- **Pros**: works when the client is offline; deep-linking.
- **Cons**: external dependency, token lifecycle management, rate limits; needs a `device_tokens` table + outbox.

### 3.6 Email / SMS
Fallback channels for high-importance events; not realtime.

## 4. Common end-to-end architectures

### A. Pull-based inbox (simplest)
REST inbox (`GET /notifications`, `GET /notifications/unread-count`) + client polling.
Good for low volume; the baseline everything else is compared against.

### B. Push over SSE with an inbox table (recommended here)
Same inbox table, plus an SSE stream per user. Writes append inbox rows **and**
publish to an in-process fan-out hub; the SSE stream reads from a per-user queue.

- **Fan-out on write**: message sent → for each recipient: insert row + enqueue event.
  Simple, correct, fine while recipients-per-event is small (chats, not broadcast lists).

```
POST /messages ──▶ app ──▶ DB insert (per recipient)      ──▶ inbox rows
                     └──▶ SseHub.publish(user, event) ──▶ SSE stream ──▶ EventSource
```

### C. Push over WebSocket (reuse the realtime channel)
If the app already has a WS connection per user, notifications are just another event type
on the same socket. Saves a connection; couples notification delivery to the WS lifecycle.

### D. Broker-based fan-out (scale-out)
Events go to Redis Pub/Sub / NATS / Kafka; per-instance workers consume and push to their
local SSE/WS connections. Required when the backend runs on **multiple instances** — an
in-process hub can't reach users connected to another instance. The outbox pattern is
usually added here so broker publishes survive DB transactions.

### E. Hybrid: realtime channel + mobile push
In-app realtime (SSE/WS) for foreground, FCM/APNs for background/closed app, with a
`device_tokens` table and an outbox relay. This is the production Telegram-like shape.

## 5. Cross-cutting concerns

| Concern | Standard answers |
|---|---|
| **Unread counts** | denormalized counter or `COUNT(*)` on inbox; badge pushed with each event |
| **Mark-as-read** | per-notification or bulk per-chat; triggers a count refresh event |
| **Dedupe / grouping** | coalesce repeated events of the same (chat, type) — e.g. one "5 new messages in X" |
| **Reconnect & gaps** | SSE: `Last-Event-ID` header + server replays since that id; WS: refetch on reconnect |
| **Fan-out cost** | inbox rows are per-recipient — fine for chat groups, problematic for millions of followers (then use feed model / batching) |
| **Proxy behavior** | disable response buffering (`proxy_buffering off`, `X-Accel-Buffering: no`), long read timeouts, keep-alive comments/heartbeats every ~15 s |
| **Multi-instance** | replace the in-process hub with Redis Pub/Sub; each instance subscribes and pushes locally |
| **Ordering** | per-user queue preserves send order; id-based cursor pagination for history |

## 6. Comparison

| Architecture | Latency | Complexity | Offline delivery | Multi-instance | Fits |
|---|---|---|---|---|---|
| Polling inbox | seconds | lowest | yes (rows persist) | yes | small apps, dashboards |
| SSE + inbox | sub-second | low | yes (rows persist) | needs broker | notification feeds, this project |
| WS reuse | sub-second | medium | yes (rows persist) | needs broker | apps already on WS |
| Broker + push | sub-second | high | with FCM/APNs | yes | large-scale production |
| Web Push | instant | medium-high | **yes (app closed)** | yes | any app with closed-app needs |

## 7. Decision for this project

**SSE + inbox table** (architecture B):

- Notifications are inherently one-way → SSE's one-way stream is the exact fit; `EventSource`
  gives auto-reconnect for free (no hand-rolled reconnect logic like WS).
- The messenger already uses WebSocket for **chat message delivery**; notifications are a
  separate concern (badges, unread state, history) and deserve their own channel with
  persistence — the inbox rows survive disconnects, so nothing is lost while offline.
- Single-instance backend → a simple in-process fan-out hub (per-user `asyncio.Queue`) is
  enough today. The seam (a `Notifier`-style hub port) leaves room for Redis Pub/Sub and
  FCM/APNs (documented in `system-design-docs/03-data-model.md`, "future-proofing").
- Sending stays on REST; the SSE stream is read-only.

### Events produced (v1)

| Event | Recipients | Type |
|---|---|---|
| message sent (REST, WS, or artifact upload) | all chat members except the sender | `message` |
| button invite created (private group) | the invited user | `invite` |

### Delivery path

```
message sent → (same tx) insert inbox rows for recipients → commit
             → SseHub.publish per recipient → GET /api/v1/notifications/stream → EventSource
             → frontend badge + panel; mark-as-read on chat open
```

See `plan/` for the phased implementation plan and `system-design-docs/08-notifications.md`
for the final design (endpoints, data model, delivery guarantees).
