from app.domain.value_objects import MemberRole


def can_edit_chat(role: MemberRole) -> bool:
    return role in (MemberRole.OWNER, MemberRole.ADMIN)


def can_invite(role: MemberRole) -> bool:
    return role in (MemberRole.OWNER, MemberRole.ADMIN)


def can_promote(role: MemberRole) -> bool:
    return role is MemberRole.OWNER


def can_remove_member(actor: MemberRole, target: MemberRole) -> bool:
    if actor is MemberRole.OWNER:
        return target in (MemberRole.ADMIN, MemberRole.MEMBER)
    if actor is MemberRole.ADMIN:
        return target is MemberRole.MEMBER
    return False
