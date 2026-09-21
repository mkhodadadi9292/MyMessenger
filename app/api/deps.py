from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.artifact_service import ArtifactService
from app.application.auth_service import AuthService
from app.application.block_service import BlockService
from app.application.chat_service import ChatService
from app.application.contact_service import ContactService
from app.application.invite_service import InviteService
from app.application.message_service import MessageService
from app.application.ports import OtpSender
from app.application.user_service import UserService
from app.config import Settings
from app.domain.entities import User
from app.domain.exceptions import UnauthorizedError
from app.infrastructure.auth.jwt import TOKEN_ACCESS, decode_token
from app.infrastructure.repositories.auth import (
    SqlOtpRepository,
    SqlRefreshSessionRepository,
)
from app.infrastructure.repositories.chat import (
    SqlChatMemberRepository,
    SqlChatRepository,
    SqlInviteRepository,
)
from app.infrastructure.repositories.contact import SqlBlockRepository, SqlContactRepository
from app.infrastructure.repositories.message import SqlArtifactRepository, SqlMessageRepository
from app.infrastructure.repositories.user import SqlUserRepository
from app.infrastructure.storage import LocalStorage


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_otp_sender(request: Request) -> OtpSender:
    return request.app.state.otp_sender


def get_storage(request: Request) -> LocalStorage:
    return LocalStorage(request.app.state.settings.media_root)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_user_repo(db: AsyncSession = Depends(get_db)) -> SqlUserRepository:
    return SqlUserRepository(db)


def get_otp_repo(db: AsyncSession = Depends(get_db)) -> SqlOtpRepository:
    return SqlOtpRepository(db)


def get_session_repo(db: AsyncSession = Depends(get_db)) -> SqlRefreshSessionRepository:
    return SqlRefreshSessionRepository(db)


def get_contact_repo(db: AsyncSession = Depends(get_db)) -> SqlContactRepository:
    return SqlContactRepository(db)


def get_block_repo(db: AsyncSession = Depends(get_db)) -> SqlBlockRepository:
    return SqlBlockRepository(db)


def get_chat_repo(db: AsyncSession = Depends(get_db)) -> SqlChatRepository:
    return SqlChatRepository(db)


def get_member_repo(db: AsyncSession = Depends(get_db)) -> SqlChatMemberRepository:
    return SqlChatMemberRepository(db)


def get_invite_repo(db: AsyncSession = Depends(get_db)) -> SqlInviteRepository:
    return SqlInviteRepository(db)


def get_message_repo(db: AsyncSession = Depends(get_db)) -> SqlMessageRepository:
    return SqlMessageRepository(db)


def get_artifact_repo(db: AsyncSession = Depends(get_db)) -> SqlArtifactRepository:
    return SqlArtifactRepository(db)


def get_auth_service(
    users: SqlUserRepository = Depends(get_user_repo),
    otps: SqlOtpRepository = Depends(get_otp_repo),
    sessions: SqlRefreshSessionRepository = Depends(get_session_repo),
    sender: OtpSender = Depends(get_otp_sender),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(users, otps, sessions, sender, settings)


def get_user_service(
    users: SqlUserRepository = Depends(get_user_repo),
    blocks: SqlBlockRepository = Depends(get_block_repo),
    storage: LocalStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> UserService:
    return UserService(users, blocks, storage, settings)


def get_contact_service(
    contacts: SqlContactRepository = Depends(get_contact_repo),
    users: SqlUserRepository = Depends(get_user_repo),
    blocks: SqlBlockRepository = Depends(get_block_repo),
) -> ContactService:
    return ContactService(contacts, users, blocks)


def get_block_service(
    blocks: SqlBlockRepository = Depends(get_block_repo),
    users: SqlUserRepository = Depends(get_user_repo),
) -> BlockService:
    return BlockService(blocks, users)


def get_chat_service(
    chats: SqlChatRepository = Depends(get_chat_repo),
    members: SqlChatMemberRepository = Depends(get_member_repo),
    invites: SqlInviteRepository = Depends(get_invite_repo),
    messages: SqlMessageRepository = Depends(get_message_repo),
    artifacts: SqlArtifactRepository = Depends(get_artifact_repo),
    users: SqlUserRepository = Depends(get_user_repo),
) -> ChatService:
    return ChatService(chats, members, invites, messages, artifacts, users)


def get_invite_service(
    invites: SqlInviteRepository = Depends(get_invite_repo),
    chats: SqlChatRepository = Depends(get_chat_repo),
    members: SqlChatMemberRepository = Depends(get_member_repo),
    users: SqlUserRepository = Depends(get_user_repo),
) -> InviteService:
    return InviteService(invites, chats, members, users)


def get_message_service(
    messages: SqlMessageRepository = Depends(get_message_repo),
    artifacts: SqlArtifactRepository = Depends(get_artifact_repo),
    chats: SqlChatRepository = Depends(get_chat_repo),
    members: SqlChatMemberRepository = Depends(get_member_repo),
    users: SqlUserRepository = Depends(get_user_repo),
    blocks: SqlBlockRepository = Depends(get_block_repo),
) -> MessageService:
    return MessageService(messages, artifacts, chats, members, users, blocks)


def get_artifact_service(
    messages: SqlMessageRepository = Depends(get_message_repo),
    artifacts: SqlArtifactRepository = Depends(get_artifact_repo),
    chats: SqlChatRepository = Depends(get_chat_repo),
    members: SqlChatMemberRepository = Depends(get_member_repo),
    users: SqlUserRepository = Depends(get_user_repo),
    blocks: SqlBlockRepository = Depends(get_block_repo),
    storage: LocalStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> ArtifactService:
    return ArtifactService(messages, artifacts, chats, members, users, blocks, storage, settings)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("missing bearer token")
    payload = decode_token(token, settings)
    if payload.get("type") != TOKEN_ACCESS:
        raise UnauthorizedError("invalid access token")
    user = await SqlUserRepository(db).get(int(payload["sub"]))
    if user is None:
        raise UnauthorizedError("user not found")
    return user
