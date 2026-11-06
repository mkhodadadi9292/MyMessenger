from abc import ABC, abstractmethod
from pathlib import Path

from app.domain.uploads import IssuedTicket, UploadTicketClaims


class OtpSender(ABC):
    """Delivery port for OTP codes. Implementations: LogOtpSender (dev), email/SMS later."""

    @abstractmethod
    async def send(self, identifier: str, code: str) -> None:
        ...


class UploadTicketCodec(ABC):
    @abstractmethod
    def issue(self, claims: UploadTicketClaims) -> IssuedTicket:
        ...

    @abstractmethod
    def read(self, token: str) -> UploadTicketClaims:
        """Verify the signature (ignoring expiry) and return the claims."""


class UploadOutcomePublisher(ABC):
    @abstractmethod
    async def publish_attached(self, upload_id: str, message_id: int, artifact_id: int) -> None:
        ...

    @abstractmethod
    async def publish_rejected(self, upload_id: str, reason: str) -> None:
        ...


class MediaLibrary(ABC):
    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        ...

    @abstractmethod
    def path_for(self, relative_path: str) -> Path:
        ...
