from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from file_service.domain.ports import Transaction, UploadSessionRepository
from file_service.domain.upload_session import UploadSession, UploadStatus
from file_service.infrastructure.db.models import UploadSessionModel


def session_to_entity(model: UploadSessionModel) -> UploadSession:
    return UploadSession(
        upload_id=model.upload_id,
        user_id=model.user_id,
        mime_type=model.mime_type,
        size_bytes=model.size_bytes,
        sha256=model.sha256,
        chunk_size=model.chunk_size,
        total_chunks=model.total_chunks,
        status=UploadStatus(model.status),
        ticket=model.ticket,
        created_at=model.created_at,
        last_activity_at=model.last_activity_at,
        file_path=model.file_path,
        completed_event_id=model.completed_event_id,
        failure_reason=model.failure_reason,
        completed_at=model.completed_at,
        decided_at=model.decided_at,
    )


class SqlTransaction(Transaction):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


class SqlUploadSessionRepository(UploadSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, upload_id: str) -> UploadSession | None:
        model = await self._session.scalar(
            select(UploadSessionModel)
            .where(UploadSessionModel.upload_id == upload_id)
            .execution_options(populate_existing=True)
        )
        return session_to_entity(model) if model else None

    async def add(self, session: UploadSession) -> bool:
        self._session.add(
            UploadSessionModel(
                upload_id=session.upload_id,
                user_id=session.user_id,
                mime_type=session.mime_type,
                size_bytes=session.size_bytes,
                sha256=session.sha256,
                chunk_size=session.chunk_size,
                total_chunks=session.total_chunks,
                status=session.status.value,
                file_path=session.file_path,
                ticket=session.ticket,
                created_at=session.created_at,
                last_activity_at=session.last_activity_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return False
        return True

    async def transition(
        self,
        upload_id: str,
        from_statuses: Iterable[UploadStatus],
        to_status: UploadStatus,
        now: datetime,
        *,
        older_than: datetime | None = None,
        file_path: str | None = None,
        failure_reason: str | None = None,
        completed: bool = False,
        decided: bool = False,
    ) -> bool:
        values: dict = {"status": to_status.value, "last_activity_at": now}
        if file_path is not None:
            values["file_path"] = file_path
        if failure_reason is not None:
            values["failure_reason"] = failure_reason
        if completed:
            values["completed_at"] = now
        if decided:
            values["decided_at"] = now
        stmt = (
            update(UploadSessionModel)
            .where(UploadSessionModel.upload_id == upload_id)
            .where(UploadSessionModel.status.in_([s.value for s in from_statuses]))
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if older_than is not None:
            stmt = stmt.where(UploadSessionModel.last_activity_at < older_than)
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    async def touch(self, upload_id: str, now: datetime) -> None:
        await self._session.execute(
            update(UploadSessionModel)
            .where(UploadSessionModel.upload_id == upload_id)
            .values(last_activity_at=now)
            .execution_options(synchronize_session=False)
        )

    async def mark_published(self, upload_id: str, event_id: str) -> None:
        await self._session.execute(
            update(UploadSessionModel)
            .where(UploadSessionModel.upload_id == upload_id)
            .values(completed_event_id=event_id)
            .execution_options(synchronize_session=False)
        )

    async def list_unpublished_completed(
        self, older_than: datetime, limit: int
    ) -> list[UploadSession]:
        models = await self._session.scalars(
            select(UploadSessionModel)
            .where(UploadSessionModel.status == UploadStatus.COMPLETED.value)
            .where(UploadSessionModel.completed_event_id.is_(None))
            .where(UploadSessionModel.completed_at < older_than)
            .order_by(UploadSessionModel.completed_at)
            .limit(limit)
        )
        return [session_to_entity(m) for m in models]

    async def list_by_status(
        self, statuses: Iterable[UploadStatus], older_than: datetime, limit: int
    ) -> list[UploadSession]:
        models = await self._session.scalars(
            select(UploadSessionModel)
            .where(UploadSessionModel.status.in_([s.value for s in statuses]))
            .where(UploadSessionModel.last_activity_at < older_than)
            .order_by(UploadSessionModel.last_activity_at)
            .limit(limit)
        )
        return [session_to_entity(m) for m in models]
