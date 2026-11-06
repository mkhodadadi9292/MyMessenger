from app.application.ports import OtpSender, UploadOutcomePublisher


class CapturingOtpSender(OtpSender):
    """Test double for the OTP delivery port; captures codes per identifier."""

    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    async def send(self, identifier: str, code: str) -> None:
        self.sent[identifier] = code

    def code_for(self, identifier: str) -> str:
        return self.sent[identifier]


class RecordingOutcomePublisher(UploadOutcomePublisher):
    def __init__(self) -> None:
        self.attached: list[tuple[str, int, int]] = []
        self.rejected: list[tuple[str, str]] = []

    async def publish_attached(self, upload_id: str, message_id: int, artifact_id: int) -> None:
        self.attached.append((upload_id, message_id, artifact_id))

    async def publish_rejected(self, upload_id: str, reason: str) -> None:
        self.rejected.append((upload_id, reason))
