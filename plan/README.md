# Notification System (SSE) — Implementation Plan

Per-user, per-chat notifications delivered over **Server-Sent Events (SSE)**, with a
persistent inbox (unread state survives disconnects) and a notification UI in the frontend.

Rationale and architecture alternatives: `knowledge/notification-system-architectures.md`.
Final design (endpoints, data model, guarantees): `system-design-docs/08-notifications.md`.

## Scope (v1)

| # | Requirement |
|---|---|
| N-1 | A notification row is created for every chat member **except the sender** when a message (text or artifact) is sent — via REST, WS send, or artifact upload. |
| N-2 | A notification row is created for the invitee when a button invite is created (private group). |
| N-3 | Users receive live notification events over an authenticated SSE stream (`GET /api/v1/notifications/stream`). |
| N-4 | Users can list their notifications (cursor-paginated), read the unread count, and mark notifications read (all or per chat). |
| N-5 | Frontend shows a bell with an unread badge in the sidebar; the panel lists notifications; clicking one opens the chat (or the invites panel for invites) and marks that chat's notifications read. |
| N-6 | Mark-as-read happens automatically when a chat is opened. |
| N-7 | Works through Nginx (buffering disabled) and Vite dev proxy; verified end-to-end with docker compose. |

Out of scope: push notifications for closed apps (FCM/APNs), device tokens, grouping/coalescing,
multi-instance fan-out (Redis) — all documented as future seams.

## Phase index

| Phase | Doc | Content |
|---|---|---|
| 1 | [phase-01-backend-domain.md](phase-01-backend-domain.md) | Domain entity/VO/repository ABC + SQL model + Alembic migration + SQL repository |
| 2 | [phase-02-backend-sse-api.md](phase-02-backend-sse-api.md) | NotificationService, SSE hub, SSE stream endpoint, REST endpoints, event wiring in message/artifact/WS/invite paths, nginx/vite config |
| 3 | [phase-03-backend-tests.md](phase-03-backend-tests.md) | Unit / integration / e2e backend tests |
| 4 | [phase-04-frontend.md](phase-04-frontend.md) | Frontend SSE client, bell/badge/panel UI, mark-read on chat open, Vitest + Playwright specs |
| 5 | [phase-05-docker-docs.md](phase-05-docker-docs.md) | Nginx SSE config, docker compose verification, final docs + CLAUDE.md update |

## Global rules

- Test-first: each phase writes its tests before (or together with) the implementation;
  a phase is "done" when its tests pass.
- Same layering as the rest of the app: domain stays pure (no fastapi/sqlalchemy/pydantic),
  repositories are ABCs implemented in `infrastructure/`, wiring in `api/deps.py`.
- **Commit-before-broadcast**: notification rows are inserted in the same transaction as the
  business change, committed before SSE events are pushed, so the receiver can refetch.
- Privacy: notification payloads never expose phone/email.
- Tests use the existing isolated in-memory SQLite engine (`tests/conftest.py`); real DBs
  (including `media.db`) are never touched.

## Definition of done (whole feature)

- Backend suite green: `uv run pytest` (unit + integration + e2e, incl. new notification tests).
- Frontend: `npm run build` clean, Vitest green, Playwright green (existing specs + new
  `notifications.spec.ts`).
- Docker compose stack verified: SSE stream reaches the browser through Nginx
  (`PW_BASE_URL=http://localhost:8080 npx playwright test`).
- Docs: `system-design-docs/08-notifications.md` added, 01/03/04/05/06 + README updated,
  `CLAUDE.md` updated.
