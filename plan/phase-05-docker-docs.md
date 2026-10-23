# Phase 5 — Nginx SSE config, docker compose verification, docs

## Nginx (`deploy/nginx.conf`)

Add a dedicated location **before** the generic `/api/` block:

```nginx
# SSE notification stream — buffering must be off or events are held back
location = /api/v1/notifications/stream {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 1h;
    chunked_transfer_encoding off;
}
```

(Keep-alive comments every 15 s from the backend prevent idle timeouts.)

## Docker compose verification

1. `docker compose up --build` (backend runs `alembic upgrade head` → the new migration
   applies on Postgres).
2. `cd frontend && PW_BASE_URL=http://localhost:8080 PW_BACKEND_URL=http://localhost:8080 npx playwright test`
   — the whole suite, including `notifications.spec.ts`, against the docker stack:
   proves SSE survives Nginx proxying and Postgres persistence.
3. Manual smoke: open two browsers, send a message, watch the badge appear on the other
   session; `docker compose logs backend | grep notification` optional.
4. `docker compose down` after verification (keep volumes unless a reset is wanted —
   ask before `down -v`).

## Docs (final deliverable)

- `system-design-docs/08-notifications.md` — new: requirements, architecture (SSE hub,
  delivery path, commit-before-notify), data model, endpoint table, guarantees & failure
  modes (reconnect, duplicates, ordering), future work (Redis fan-out, FCM/APNs).
- Update `system-design-docs/03-data-model.md` — add the `notifications` table; replace the
  "future-proofing" section (notifications are now implemented).
- Update `system-design-docs/04-api-endpoints.md` — add N1–N4.
- Update `system-design-docs/01-requirements.md` — move FR-9 notifications into an FR with
  SSE delivery; adjust NFRs if needed.
- Update `system-design-docs/05-phases.md` — mark phases 0–8 done, add Phase 9
  (notifications) with deliverables + status.
- Update `system-design-docs/06-testing-strategy.md` — SSE stream testing notes
  (httpx streaming e2e, EventSource mock in Vitest, Playwright dual-mode).
- Update `system-design-docs/README.md` — add the new doc + phase row.
- Update `CLAUDE.md` — notifications/SSE conventions: stream endpoint auth via query token,
  commit-before-notify rule, SseHub, Nginx buffering-off location, frontend `sse.ts`
  (EventSource auto-reconnect), tests locations.
- Update `knowledge/bidirectional-messaging-tech.md` — cross-link the new knowledge doc.

## Definition of done (feature)

- Docker stack verified end to end (playwright against `localhost:8080`).
- All docs updated; `CLAUDE.md` reflects the new conventions.
