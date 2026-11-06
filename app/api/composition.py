from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.artifact_service import ArtifactService
from app.application.message_service import MessageService
from app.application.upload_attach_service import UploadAttachService
from app.application.upload_service import UploadService
from app.config import Settings
from app.infrastructure.auth.upload_ticket import JwtUploadTicketCodec
from app.infrastructure.repositories.chat import SqlChatMemberRepository, SqlChatRepository
from app.infrastructure.repositories.contact import SqlBlockRepository
from app.infrastructure.repositories.message import (
    SqlArtifactRepository,
    SqlMessageRepository,
    SqlReactionRepository,
)
from app.infrastructure.repositories.user import SqlUserRepository
from app.infrastructure.storage import LocalStorage


@dataclass(frozen=True)
class MessagingRepositories:
    messages: SqlMessageRepository
    artifacts: SqlArtifactRepository
    chats: SqlChatRepository
    members: SqlChatMemberRepository
    users: SqlUserRepository
    blocks: SqlBlockRepository
    reactions: SqlReactionRepository


def build_messaging_repositories(session: AsyncSession) -> MessagingRepositories:
    return MessagingRepositories(
        messages=SqlMessageRepository(session),
        artifacts=SqlArtifactRepository(session),
        chats=SqlChatRepository(session),
        members=SqlChatMemberRepository(session),
        users=SqlUserRepository(session),
        blocks=SqlBlockRepository(session),
        reactions=SqlReactionRepository(session),
    )


def build_message_service(repos: MessagingRepositories) -> MessageService:
    return MessageService(
        repos.messages,
        repos.artifacts,
        repos.chats,
        repos.members,
        repos.users,
        repos.blocks,
        repos.reactions,
    )


def build_media_library(settings: Settings) -> LocalStorage:
    return LocalStorage(settings.media_root)


def build_artifact_service(repos: MessagingRepositories, settings: Settings) -> ArtifactService:
    return ArtifactService(
        repos.messages, repos.artifacts, repos.members, build_media_library(settings)
    )


def build_upload_ticket_codec(settings: Settings) -> JwtUploadTicketCodec:
    return JwtUploadTicketCodec(
        settings.upload_ticket_secret,
        settings.upload_ticket_issuer,
        settings.upload_ticket_audience,
        settings.upload_ticket_ttl_seconds,
    )


def build_upload_service(repos: MessagingRepositories, settings: Settings) -> UploadService:
    return UploadService(
        build_message_service(repos),
        build_upload_ticket_codec(settings),
        settings.max_artifact_size_mb * 1024 * 1024,
    )


def build_upload_attach_service(
    repos: MessagingRepositories, settings: Settings
) -> UploadAttachService:
    return UploadAttachService(
        repos.messages,
        repos.artifacts,
        repos.users,
        build_message_service(repos),
        build_upload_ticket_codec(settings),
        build_media_library(settings),
        settings.upload_event_max_age_seconds,
    )
