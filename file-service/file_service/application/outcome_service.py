import logging

from file_service.domain.events import UPLOAD_ATTACHED, UPLOAD_REJECTED
from file_service.domain.ports import Clock, Transaction, UploadSessionRepository
from file_service.domain.upload_session import UploadStatus

logger = logging.getLogger("file_service.outcomes")


class UnknownOutcomeError(Exception):
    pass


class OutcomeService:
    def __init__(
        self, sessions: UploadSessionRepository, transaction: Transaction, clock: Clock
    ) -> None:
        self._sessions = sessions
        self._transaction = transaction
        self._clock = clock

    async def apply(self, outcome_type: str, upload_id: str, reason: str | None = None) -> None:
        if outcome_type == UPLOAD_ATTACHED:
            target = UploadStatus.ATTACHED
        elif outcome_type == UPLOAD_REJECTED:
            target = UploadStatus.REJECTED
        else:
            raise UnknownOutcomeError(outcome_type)
        changed = await self._sessions.transition(
            upload_id,
            [UploadStatus.COMPLETED],
            target,
            self._clock.now(),
            failure_reason=reason if target is UploadStatus.REJECTED else None,
            decided=True,
        )
        await self._transaction.commit()
        if not changed:
            session = await self._sessions.get(upload_id)
            current = session.status.value if session else "missing"
            logger.info("outcome %s for %s ignored, status is %s", outcome_type, upload_id, current)
