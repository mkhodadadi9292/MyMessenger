from datetime import UTC, datetime, timedelta

import jwt

from app.application.ports import UploadTicketCodec
from app.domain.exceptions import UnauthorizedError
from app.domain.uploads import IssuedTicket, UploadTicketClaims
from app.domain.value_objects import ArtifactKind

TICKET_TYPE = "upload"
TICKET_ALGORITHM = "HS256"
REQUIRED_CLAIMS = [
    "exp",
    "iat",
    "sub",
    "upload_id",
    "chat_id",
    "kind",
    "mime_type",
    "size_bytes",
    "sha256",
    "file_name",
]


class JwtUploadTicketCodec(UploadTicketCodec):
    def __init__(self, secret: str, issuer: str, audience: str, ttl_seconds: int) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._ttl = timedelta(seconds=ttl_seconds)

    def issue(self, claims: UploadTicketClaims) -> IssuedTicket:
        issued_at = claims.issued_at.replace(tzinfo=UTC)
        expires_at = issued_at + self._ttl
        token = jwt.encode(
            {
                "iss": self._issuer,
                "aud": self._audience,
                "typ": TICKET_TYPE,
                "sub": str(claims.user_id),
                "upload_id": claims.upload_id,
                "chat_id": claims.chat_id,
                "kind": claims.kind.value,
                "mime_type": claims.mime_type,
                "size_bytes": claims.size_bytes,
                "sha256": claims.sha256,
                "file_name": claims.file_name,
                "reply_to_id": claims.reply_to_id,
                "iat": issued_at,
                "exp": expires_at,
            },
            self._secret,
            algorithm=TICKET_ALGORITHM,
        )
        return IssuedTicket(upload_id=claims.upload_id, token=token, expires_at=expires_at)

    def read(self, token: str) -> UploadTicketClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[TICKET_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={"verify_exp": False, "require": REQUIRED_CLAIMS},
            )
            if payload.get("typ") != TICKET_TYPE:
                raise UnauthorizedError("not an upload ticket")
            reply_to_id = payload.get("reply_to_id")
            return UploadTicketClaims(
                upload_id=str(payload["upload_id"]),
                user_id=int(payload["sub"]),
                chat_id=int(payload["chat_id"]),
                kind=ArtifactKind(payload["kind"]),
                mime_type=str(payload["mime_type"]),
                size_bytes=int(payload["size_bytes"]),
                sha256=str(payload["sha256"]),
                file_name=str(payload["file_name"]),
                reply_to_id=int(reply_to_id) if reply_to_id is not None else None,
                issued_at=datetime.fromtimestamp(int(payload["iat"]), UTC).replace(tzinfo=None),
            )
        except UnauthorizedError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise UnauthorizedError("invalid upload ticket") from exc
