# 03 — Data Model

All IDs: integer autoincrement PKs. Timestamps UTC. FKs indexed. Soft-delete where noted. Naming: snake_case tables.

## Tables

### users
| col | type | notes |
|---|---|---|
| id | int PK | |
| username | str UNIQUE NOT NULL | public handle, `[a-z0-9_]{3,32}` |
| phone | str UNIQUE NULL | E.164, never exposed in API responses |
| email | str UNIQUE NULL | for OTP delivery (future real sending) |
| first_name | str | |
| last_name | str NULL | |
| bio | str NULL | |
| avatar_path | str NULL | relative path under media root |
| created_at | datetime | |

### otp_codes
| col | type | notes |
|---|---|---|
| id | int PK | |
| identifier | str | email or phone used to request |
| code_hash | str | sha256(code) — never store plain |
| purpose | str | `register` \| `login` |
| expires_at | datetime | +5 min |
| used_at | datetime NULL | single-use |

### refresh_sessions
| col | type | notes |
|---|---|---|
| id | int PK | |
| user_id | int FK users | |
| token_hash | str | sha256 of refresh JWT |
| expires_at | datetime | |
| revoked_at | datetime NULL | logout/rotation revokes |

### contacts
| col | type | notes |
|---|---|---|
| id | int PK | |
| owner_id | int FK users | who added |
| contact_id | int FK users | who was added |
| created_at | datetime | |
| | | UNIQUE(owner_id, contact_id) |

### blocked_users
| col | type | notes |
|---|---|---|
| id | int PK | |
| blocker_id | int FK users | |
| blocked_id | int FK users | |
| created_at | datetime | |
| | | UNIQUE(blocker_id, blocked_id) |

### chats
| col | type | notes |
|---|---|---|
| id | int PK | |
| type | str | `private` \| `group` |
| title | str NULL | groups only |
| description | str NULL | groups only |
| is_public | bool | groups only; private chat = false |
| owner_id | int FK users | creator |
| created_at | datetime | |

### chat_members
| col | type | notes |
|---|---|---|
| id | int PK | |
| chat_id | int FK chats | |
| user_id | int FK users | |
| role | str | `owner` \| `admin` \| `member` |
| joined_at | datetime | |
| invited_by_id | int FK users NULL | |
| | | UNIQUE(chat_id, user_id) |

### group_invites  (button invites + temporary links)
| col | type | notes |
|---|---|---|
| id | int PK | |
| chat_id | int FK chats | |
| inviter_id | int FK users | admin who invited |
| invitee_id | int FK users NULL | NULL for link invites |
| token | str UNIQUE NULL | link invites only |
| status | str | `pending` \| `accepted` \| `declined` \| `expired` |
| expires_at | datetime NULL | links always have it |
| created_at | datetime | |

### messages
| col | type | notes |
|---|---|---|
| id | int PK | |
| chat_id | int FK chats | index (chat_id, id) for cursor pagination |
| sender_id | int FK users | |
| reply_to_id | int FK messages NULL | reply chain head |
| text | str NULL | NULL when pure artifact, or "deleted" marker |
| edited_at | datetime NULL | |
| deleted_at | datetime NULL | soft delete → UI shows "deleted" |
| created_at | datetime | |

### artifacts
| col | type | notes |
|---|---|---|
| id | int PK | |
| message_id | int FK messages | one artifact per message in v1 |
| kind | str | `image` \| `video` \| `audio` |
| file_name | str | original name |
| file_path | str | relative path under media root |
| mime_type | str | |
| size_bytes | int | |
| created_at | datetime | |

## Value objects (domain)

| VO | Rules |
|---|---|
| `Username` | 3–32 chars, `[a-z0-9_]+`, lowercase |
| `Phone` | E.164 regex; optional |
| `ChatType` | `private` \| `group` |
| `MemberRole` | `owner` \| `admin` \| `member` |
| `InviteStatus` | `pending` \| `accepted` \| `declined` \| `expired` |
| `ArtifactKind` | `image` \| `video` \| `audio` |

## Invariants (enforced in services, verified in tests)

1. Private chat: exactly 2 members, no title, no roles, no invites.
2. Group: ≥1 member (owner). Last member leaving deletes the group.
3. Only owner/admin can invite (private group), promote, remove members.
4. Owner cannot be removed; admins cannot remove other admins (only owner can).
5. Message sender must be a member; reply target must be in same chat.
6. Link invite: single-use per user, expires → `expired`.
7. Button invite: invitee accept/decline is required; status transitions `pending → accepted|declined`.
8. Blocking: blocker↔blocked cannot exchange messages, invite, view profile, add contact.
9. OTP: 6 digits, 5-minute TTL, single-use, hashed at rest.
10. Refresh token: stored hashed, revocable, rotation on refresh.

## Future-proofing (notifications — out of scope)

- `messages` already has sender/chat/timestamps needed to build notification events.
- Notification delivery would be a new infrastructure port (`Notifier`) + `device_tokens` table; no changes to message model required.
