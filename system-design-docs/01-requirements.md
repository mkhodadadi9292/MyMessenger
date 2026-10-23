# 01 — Requirements

## Functional requirements

### FR-1 User accounts & profiles
- FR-1.1 Register with email or phone + OTP.
- FR-1.2 Login with OTP. For dev simplicity the OTP is printed in the server log (email-sending is a future swap-in behind the same interface).
- FR-1.3 User info: `username` (unique, public), `phone` (unique, **never exposed**), email, first name, last name, bio, avatar.
- FR-1.4 Users can edit their own profile (name, bio, username, avatar).
- FR-1.5 Users can search for other users by **username** or **phone**. Phone-based search only matches an exact phone and never reveals the phone in responses (privacy).

### FR-2 Private (1-to-1) chat
- FR-2.1 Any user can open a private chat with any other user (both become members; no invite needed).
- FR-2.2 A private chat exists at most once per pair of users.
- FR-2.3 Sending messages to a user who blocked you is refused.

### FR-3 Groups
- FR-3.1 **Private group**: created by a user (owner). Only admins can invite new members.
- FR-3.2 **Public group**: created by a user (owner). Anyone can join directly (via link or by opening the group).
- FR-3.3 Roles per group: `owner` (creator), `admin`, `member`. Owner can promote/demote admins, remove members. Admins can invite and remove members (except owner/admins).
- FR-3.4 Members can leave a group. If the last member leaves, the group is deleted.
- FR-3.5 Group profile: title, description — editable by admins.

### FR-4 Invites
- FR-4.1 **Button invite** (private groups): admin invites a specific user → invite is created → invited user sees it and must **accept or decline** to join.
- FR-4.2 **Temporary link invite** (private groups): admin generates a short-lived token link; anyone holding the link can request to join and joins on accept. Link has an expiry.
- FR-4.3 Public groups need no invite: join directly.

### FR-5 Messages
- FR-5.1 Members can send text messages to any chat they belong to.
- FR-5.2 **Reply**: any participant in any chat type can reply to any message (`reply_to_id`).
- FR-5.3 Sender can edit or delete their own messages (soft-delete: text cleared, "deleted" marker).
- FR-5.4 Message history is paginated (cursor-based: `before_id` + `limit`).
- FR-5.5 Blocked users cannot message you; you cannot message users who blocked you.

### FR-6 Artifacts (media)
- FR-6.1 In any chat they are a member of, a user can send artifacts of kinds: **image**, **video**, **audio (music)**.
- FR-6.2 Artifacts are uploaded (multipart), stored on disk (served by Nginx in prod), linked to a message; a message may carry an artifact instead of / alongside text.
- FR-6.3 Artifacts can be downloaded by chat members.

### FR-7 Contacts
- FR-7.1 Every user has a contact list.
- FR-7.2 Add a contact by **username or phone** (phone stays hidden; contact list stores the user reference).
- FR-7.3 Remove a contact.

### FR-8 Blocking (Telegram-like)
- FR-8.1 Block / unblock any user.
- FR-8.2 While A blocks B: B cannot message A, cannot invite A to groups, cannot see A's profile (profile access denied), cannot add A to contacts.

### FR-9 Notifications (in-app, SSE)
- FR-9.1 Users receive a notification for every message sent in a chat they are a member of, except their own messages (REST, WS, or artifact upload).
- FR-9.2 Users receive a notification when they are invited to a private group (button invite).
- FR-9.3 Notifications are delivered live over an authenticated SSE stream and persisted in an inbox (survives disconnects; list + unread count via REST).
- FR-9.4 Users can mark notifications read — all, or per chat; opening a chat marks its notifications read automatically.
- FR-9.5 The frontend shows a bell with an unread badge and a notification panel; clicking a notification opens the chat (or the invites panel for invites).

Out of scope for v1 (design-ready): push notifications while the app is closed (FCM/APNs), device tokens, notification grouping/coalescing — see `system-design-docs/08-notifications.md`.

## Non-functional requirements

| # | Requirement |
|---|---|
| NFR-1 | Python 3.13, FastAPI REST, SQLite via SQLAlchemy 2.0 async; DB URL swappable to Postgres later |
| NFR-2 | Alembic migrations from day one |
| NFR-3 | Three layers (presentation / application / domain) + infrastructure; abstract repository interfaces |
| NFR-4 | SOLID, full typing (`mypy`-clean), DI via FastAPI `Depends` |
| NFR-5 | Tests-first: unit, integration, e2e in separate `tests/` tree |
| NFR-6 | Frontend React + Vite, Telegram-like UI; Playwright e2e |
| NFR-7 | Nginx serves static/media files; uvicorn behind it |
| NFR-8 | All persistent resources in tests are isolated (separate test DB, tmp storage) — real data never touched |
