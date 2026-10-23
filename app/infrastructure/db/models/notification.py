from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.time import utcnow
from app.infrastructure.db.base import Base


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    invite_id: Mapped[int | None] = mapped_column(
        ForeignKey("group_invites.id", ondelete="CASCADE")
    )
    chat_title: Mapped[str | None] = mapped_column(String(255))
    preview: Mapped[str | None] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
