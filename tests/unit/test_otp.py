import logging
from datetime import datetime, timedelta, timezone

from app.infrastructure.auth.otp import (
    LogOtpSender,
    generate_code,
    hash_code,
    is_expired,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_generate_code_digits_and_length() -> None:
    code = generate_code(6)
    assert len(code) == 6
    assert code.isdigit()


def test_generate_code_custom_length() -> None:
    assert len(generate_code(4)) == 4


def test_generate_code_varies() -> None:
    assert len({generate_code(6) for _ in range(3)}) > 1


def test_hash_code_sha256_hex() -> None:
    digest = hash_code("123456")
    assert digest == hash_code("123456")
    assert len(digest) == 64
    assert digest != hash_code("654321")


def test_is_expired() -> None:
    expires_at = NOW + timedelta(seconds=300)
    assert is_expired(expires_at, NOW) is False
    assert is_expired(expires_at, expires_at) is True
    assert is_expired(expires_at, expires_at + timedelta(seconds=1)) is True


async def test_log_sender_logs_code(caplog) -> None:
    sender = LogOtpSender()
    with caplog.at_level(logging.INFO, logger="app.auth.otp"):
        await sender.send("alice@example.com", "123456")
    assert "123456" in caplog.text
    assert "alice@example.com" in caplog.text
