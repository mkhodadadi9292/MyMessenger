import pytest

from app.domain.permissions import can_edit_chat, can_invite, can_promote, can_remove_member
from app.domain.value_objects import MemberRole

OWNER, ADMIN, MEMBER = MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER


@pytest.mark.parametrize(
    ("role", "expected"),
    [(OWNER, True), (ADMIN, True), (MEMBER, False)],
)
def test_can_edit_chat(role: MemberRole, expected: bool) -> None:
    assert can_edit_chat(role) is expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [(OWNER, True), (ADMIN, True), (MEMBER, False)],
)
def test_can_invite(role: MemberRole, expected: bool) -> None:
    assert can_invite(role) is expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [(OWNER, True), (ADMIN, False), (MEMBER, False)],
)
def test_can_promote(role: MemberRole, expected: bool) -> None:
    assert can_promote(role) is expected


@pytest.mark.parametrize(
    ("actor", "target", "expected"),
    [
        (OWNER, MEMBER, True),
        (OWNER, ADMIN, True),
        (OWNER, OWNER, False),
        (ADMIN, MEMBER, True),
        (ADMIN, ADMIN, False),
        (ADMIN, OWNER, False),
        (MEMBER, MEMBER, False),
        (MEMBER, ADMIN, False),
        (MEMBER, OWNER, False),
    ],
)
def test_can_remove_member(
    actor: MemberRole, target: MemberRole, expected: bool
) -> None:
    assert can_remove_member(actor, target) is expected
