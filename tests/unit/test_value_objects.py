import pytest

from app.domain.exceptions import ValidationError
from app.domain.value_objects import (
    ArtifactKind,
    ChatType,
    InviteStatus,
    MemberRole,
    Phone,
    Username,
)


class TestUsername:
    @pytest.mark.parametrize("value", ["ali", "a1_2", "user_name", "abc", "a" * 32])
    def test_valid(self, value: str) -> None:
        assert Username(value).value == value

    @pytest.mark.parametrize(
        "value", ["ab", "a" * 33, "Ali", "a-b", "a b", "a.b", "a/b", "", "a!b", "a b c"]
    )
    def test_invalid(self, value: str) -> None:
        with pytest.raises(ValidationError):
            Username(value)

    def test_equality(self) -> None:
        assert Username("ali") == Username("ali")
        assert Username("ali") != Username("bob")

    def test_str(self) -> None:
        assert str(Username("ali")) == "ali"


class TestPhone:
    @pytest.mark.parametrize("value", ["+989123456789", "+12025550123", "+447911123456"])
    def test_valid(self, value: str) -> None:
        assert Phone(value).value == value

    @pytest.mark.parametrize(
        "value",
        ["989123456789", "+09123456789", "+98912", "+98912345678901234567", "abc", ""],
    )
    def test_invalid(self, value: str) -> None:
        with pytest.raises(ValidationError):
            Phone(value)

    def test_equality(self) -> None:
        assert Phone("+989123456789") == Phone("+989123456789")


class TestArtifactKind:
    @pytest.mark.parametrize(
        ("mime", "kind"),
        [
            ("image/png", ArtifactKind.IMAGE),
            ("image/jpeg", ArtifactKind.IMAGE),
            ("image/gif", ArtifactKind.IMAGE),
            ("video/mp4", ArtifactKind.VIDEO),
            ("audio/mpeg", ArtifactKind.AUDIO),
            ("audio/mp3", ArtifactKind.AUDIO),
        ],
    )
    def test_from_mime(self, mime: str, kind: ArtifactKind) -> None:
        assert ArtifactKind.from_mime(mime) is kind

    @pytest.mark.parametrize("mime", ["application/pdf", "text/plain", ""])
    def test_from_mime_unknown(self, mime: str) -> None:
        with pytest.raises(ValidationError):
            ArtifactKind.from_mime(mime)


def test_enum_values() -> None:
    assert {m.value for m in ChatType} == {"private", "group"}
    assert {m.value for m in MemberRole} == {"owner", "admin", "member"}
    assert {m.value for m in InviteStatus} == {"pending", "accepted", "declined", "expired"}
    assert {m.value for m in ArtifactKind} == {"image", "video", "audio"}
