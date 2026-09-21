# Bidirectional (Real-Time) Messaging — Technologies

> Question: What technologies exist for bidirectional messaging between a client and a server, and which one fits this project?

## The options

### 1. Short polling
The client simply re-requests data every few seconds (e.g. every 2–3s).

- **How**: normal HTTP request → response, repeated on a timer.
- **Latency**: up to one interval.
- **Pros**: dead simple, stateless, works everywhere, easy to test.
- **Cons**: wasteful (many requests for nothing), slow, no instant feel.
- **Status here**: this is what the messenger uses today (messages 2s, chat list 3s).

### 2. Long polling
The client asks for updates and the server **holds the request open** until there is something to send (or a timeout), then the client immediately asks again.

- **How**: plain HTTP with a hanging request.
- **Latency**: low.
- **Pros**: works over plain HTTP, no special server support needed.
- **Cons**: still one request per event, many open connections, proxy timeouts to handle.

### 3. SSE — Server-Sent Events
The server pushes a continuous stream of events to the client over one long-lived HTTP connection.

- **How**: `EventSource` in the browser; the server keeps writing events.
- **Latency**: low.
- **Pros**: very simple, automatic reconnection built into browsers.
- **Cons**: **one-way only** (server → client). Sending still uses normal REST calls. Events are text-only.

### 4. WebSocket
A persistent full-duplex connection: both sides can send at any time over one connection.

- **How**: HTTP connection upgrades to `ws://`; messages flow both ways.
- **Latency**: very low.
- **Pros**: true bidirectional, one connection per client, supported natively by FastAPI and browsers.
- **Cons**: needs connection lifecycle management (heartbeats, reconnects, resync after a drop).

### 5. Others (less relevant here)
- **WebRTC**: peer-to-peer data channels — for voice/video, not server-mediated text chat.
- **MQTT / XMPP / gRPC streaming**: full messaging protocols — powerful but heavy for this stack.

## Recommendation for this project

**WebSocket** is the natural choice:

- FastAPI has first-class WebSocket support — the backend change is small.
- One connection per user can carry everything: messages, typing, invites, blocking events.
- It is the standard Telegram-like pattern.

A production-grade design adds:

1. **Heartbeat** (ping/pong) to detect dead connections.
2. **Reconnect + resync**: after a drop, the client refetches messages it missed.
3. **Polling fallback**: keep the current REST polling for networks that block WebSockets.
4. **Push notifications** (FCM/APNs) later, for delivery while the app is closed — the seam already exists in the plan docs.

## Quick comparison

| Tech | Direction | Latency | Complexity |
|---|---|---|---|
| Short polling | both (REST) | up to interval | lowest |
| Long polling | both (REST) | low | low |
| SSE | server → client only | low | low |
| WebSocket | full-duplex | very low | medium |


---

## Status in this project

WebSocket is now **implemented** (see `PLAN/README.md` and `CLAUDE.md`): a `/ws` endpoint with per-chat subscriptions delivers `message.new` and `chat.list_changed` events; REST remains the send path and short polling is kept only as an automatic fallback when the socket is down.
