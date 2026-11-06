import jwt

from file_service.domain.exceptions import UnauthorizedError
from file_service.domain.ports import TicketVerifier
from file_service.domain.ticket import UploadTicket

TICKET_TYPE = "upload"
TICKET_ALGORITHM = "HS256"


class JwtTicketVerifier(TicketVerifier):
    def __init__(self, secret: str, issuer: str, audience: str) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> UploadTicket:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[TICKET_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "upload_id"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("upload ticket expired") from exc
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("invalid upload ticket") from exc
        if claims.get("typ") != TICKET_TYPE:
            raise UnauthorizedError("invalid upload ticket")
        try:
            return UploadTicket(
                upload_id=str(claims["upload_id"]),
                user_id=int(claims["sub"]),
                mime_type=str(claims["mime_type"]),
                size_bytes=int(claims["size_bytes"]),
                sha256=str(claims["sha256"]),
                raw=token,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise UnauthorizedError("invalid upload ticket") from exc
