from abc import ABC, abstractmethod


class OtpSender(ABC):
    """Delivery port for OTP codes. Implementations: LogOtpSender (dev), email/SMS later."""

    @abstractmethod
    async def send(self, identifier: str, code: str) -> None:
        ...
