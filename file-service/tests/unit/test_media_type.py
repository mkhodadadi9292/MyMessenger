import pytest

from file_service.domain.media_type import content_matches_declared_type, sniff_mime_type

SAMPLES = {
    "image/png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 8,
    "image/jpeg": b"\xff\xd8\xff\xe0" + b"\x00" * 8,
    "image/gif": b"GIF89a" + b"\x00" * 8,
    "image/webp": b"RIFF\x00\x00\x00\x00WEBPVP8 ",
    "audio/wav": b"RIFF\x00\x00\x00\x00WAVEfmt ",
    "video/mp4": b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8,
    "video/quicktime": b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 8,
    "video/webm": b"\x1a\x45\xdf\xa3" + b"\x00" * 8,
    "audio/ogg": b"OggS" + b"\x00" * 8,
    "audio/mpeg": b"ID3" + b"\x00" * 8,
}


@pytest.mark.parametrize(("mime", "head"), SAMPLES.items())
def test_sniffs_each_supported_type(mime: str, head: bytes) -> None:
    assert sniff_mime_type(head) == mime


def test_unknown_content_is_not_sniffed() -> None:
    assert sniff_mime_type(b"hello world, plain text") is None


def test_declared_type_must_match_content() -> None:
    assert content_matches_declared_type(SAMPLES["image/png"], "image/png")
    assert not content_matches_declared_type(SAMPLES["image/png"], "image/jpeg")
    assert not content_matches_declared_type(b"plain text", "image/png")


def test_mp3_alias_matches_mpeg_content() -> None:
    assert content_matches_declared_type(SAMPLES["audio/mpeg"], "audio/mp3")
