from app.application.ports import OtpSender


class CapturingOtpSender(OtpSender):
    """Test double for the OTP delivery port; captures codes per identifier."""

    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    async def send(self, identifier: str, code: str) -> None:
        self.sent[identifier] = code

    def code_for(self, identifier: str) -> str:
        return self.sent[identifier]
