# 04 — API Endpoints

Base URL: `/api/v1`. Auth: `Authorization: Bearer <access_token>` (marked 🔒). Errors: `{detail: str}` with proper status codes.

## Auth

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| A1 | POST | `/auth/otp/request` | `{identifier}` (email or phone) | `{otp_id, expires_in, delivery:"log"}` (code printed in server log) | — |
| A2 | POST | `/auth/otp/verify` | `{identifier, code}` | existing user → `{access_token, refresh_token, user}`; new user → `{registered:false, registration_token}` | — |
| A3 | POST | `/auth/register` | `{registration_token, username, first_name, last_name?}` | `{access_token, refresh_token, user}` | — |
| A4 | POST | `/auth/refresh` | `{refresh_token}` | `{access_token, refresh_token}` (rotation) | — |
| A5 | POST | `/auth/logout` | `{refresh_token}` | `{ok:true}` (revokes session) | — |

## Users

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| U1 | GET | `/users/me` | — | own profile | 🔒 |
| U2 | PATCH | `/users/me` | `{first_name?, last_name?, bio?, username?}` | updated profile | 🔒 |
| U3 | GET | `/users/{user_id}` | — | public profile (no phone; 403 if blocked) | 🔒 |
| U4 | GET | `/users/search` | `?q=` (username prefix or exact phone) | `[public profile]` — phone never included | 🔒 |
| U5 | POST | `/users/me/avatar` | multipart `file` | profile with `avatar_url` | 🔒 |

## Contacts

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| C1 | GET | `/contacts` | — | `[{user_id, username, first_name, last_name, avatar_url}]` | 🔒 |
| C2 | POST | `/contacts` | `{identifier}` (username or phone) | created contact entry | 🔒 |
| C3 | DELETE | `/contacts/{user_id}` | — | `{ok:true}` | 🔒 |

## Blocking

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| B1 | GET | `/blocked` | — | `[{user_id, username, ...}]` | 🔒 |
| B2 | POST | `/blocked/{user_id}` | — | `{ok:true}` | 🔒 |
| B3 | DELETE | `/blocked/{user_id}` | — | `{ok:true}` | 🔒 |

## Chats

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| CH1 | GET | `/chats` | — | `[{chat, last_message?}]` sorted by recency | 🔒 |
| CH2 | POST | `/chats/private` | `{user_id}` | private chat (creates or returns existing pair chat) | 🔒 |
| CH3 | POST | `/chats/groups` | `{title, description?, is_public}` | created group | 🔒 |
| CH4 | GET | `/chats/{chat_id}` | — | chat info (members only) | 🔒 |
| CH5 | PATCH | `/chats/{chat_id}` | `{title?, description?}` (admin) | updated chat | 🔒 |
| CH6 | GET | `/chats/{chat_id}/members` | — | `[{user_id, role, joined_at, ...}]` | 🔒 |
| CH7 | POST | `/chats/{chat_id}/members` | `{user_id}` — private group: admin invite (creates pending invite); public group: admin adds directly | `{invite?}` or `{member}` | 🔒 |
| CH8 | DELETE | `/chats/{chat_id}/members/{user_id}` | — (admin) | `{ok:true}` | 🔒 |
| CH9 | POST | `/chats/{chat_id}/join` | — public groups only | `{ok:true}` (becomes member) | 🔒 |
| CH10 | DELETE | `/chats/{chat_id}/leave` | — | `{ok:true}` (last member → group deleted) | 🔒 |
| CH11 | POST | `/chats/{chat_id}/admins/{user_id}` | — (owner only) | `{ok:true}` | 🔒 |

## Invites

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| I1 | POST | `/chats/{chat_id}/invites` | `{user_id}` — button invite (admin, private group) | `{invite_id, status:"pending"}` | 🔒 |
| I2 | POST | `/chats/{chat_id}/invite-links` | `{ttl_seconds?}` (admin, private group) | `{token, url, expires_at}` | 🔒 |
| I3 | GET | `/invites/{token}` | — | `{chat_id, title, inviter_name, expires_at}` | 🔒 |
| I4 | POST | `/invites/{token}/accept` | — | `{ok:true}` (joins group) | 🔒 |
| I5 | GET | `/me/invites` | — | my pending button invites | 🔒 |
| I6 | POST | `/me/invites/{invite_id}/accept` | — | `{ok:true}` | 🔒 |
| I7 | POST | `/me/invites/{invite_id}/decline` | — | `{ok:true}` | 🔒 |

## Messages

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| M1 | GET | `/chats/{chat_id}/messages` | `?before_id=&limit=50` | `[{id, sender, text, reply_to_id, artifact?, created_at, edited_at, deleted_at}]` newest-first | 🔒 |
| M2 | POST | `/chats/{chat_id}/messages` | `{text?, reply_to_id?}` | created message | 🔒 |
| M3 | PATCH | `/messages/{message_id}` | `{text}` (sender only) | updated message | 🔒 |
| M4 | DELETE | `/messages/{message_id}` | — (sender only) | `{ok:true}` (soft delete) | 🔒 |

## Artifacts

| # | Method | Path | Body / Params | Response | Auth |
|---|---|---|---|---|---|
| T1 | POST | `/chats/{chat_id}/artifacts` | multipart: `file`, `kind` (image\|video\|audio), `reply_to_id?` | created message with artifact | 🔒 |
| T2 | GET | `/artifacts/{artifact_id}/download` | — | file (members only) | 🔒 |

## Misc

| # | Method | Path | Response | Auth |
|---|---|---|---|---|
| H1 | GET | `/health` | `{status:"ok"}` | — |

## Error codes

| HTTP | Domain errors |
|---|---|
| 400 | ValidationError, OtpExpired, OtpInvalid |
| 401 | UnauthorizedError (bad/expired token) |
| 403 | ForbiddenError (not member / not admin / blocked / profile hidden) |
| 404 | NotFoundError (user, chat, message, invite) |
| 409 | ConflictError (username/phone taken, already member, already blocked, private chat already exists, already invited) |

## Notes

- Phone numbers never appear in any response body.
- Replies are plain `reply_to_id` on M2/T1 — no separate endpoint needed.
- Message history is cursor-paginated (`before_id`), default limit 50, max 100.
- Artifact uploads validate MIME + size (e.g. ≤ 20 MB) and kind.
