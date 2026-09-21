import re
from enum import StrEnum

from app.domain.exceptions import ValidationError

# Policy (mirrored in frontend/src/username.ts): 3-32 chars, must start
# with a lowercase letter, only a-z, 0-9 and _ allowed.
_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


class Username:
    def __init__(self, value: str) -> None:
        if not _USERNAME_RE.fullmatch(value):
            raise ValidationError(
                "username must be 3-32 chars, start with a lowercase letter, "
                "and contain only a-z, 0-9 or _"
            )
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Username) and other.value == self.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value


class Phone:
    def __init__(self, value: str) -> None:
        if not _PHONE_RE.fullmatch(value):
            raise ValidationError("phone must be in E.164 format, e.g. +989123456789")
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Phone) and other.value == self.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value


class ChatType(StrEnum):
    PRIVATE = "private"
    GROUP = "group"


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class InviteStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


_MIME_TYPES_BY_KIND: dict[str, set[str]] = {
    "image": {"image/png", "image/jpeg", "image/gif", "image/webp"},
    "video": {"video/mp4", "video/webm", "video/quicktime"},
    "audio": {"audio/mpeg", "audio/mp3", "audio/ogg", "audio/wav"},
}


class ArtifactKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"

    @classmethod
    def from_mime(cls, mime: str) -> "ArtifactKind":
        for kind in cls:
            if kind.accepts_mime(mime):
                return kind
        raise ValidationError(f"unsupported artifact mime type: {mime}")

    def accepts_mime(self, mime: str) -> bool:
        return mime in _MIME_TYPES_BY_KIND[self.value]
