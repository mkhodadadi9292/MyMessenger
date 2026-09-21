import hashlib
import logging
import secrets
from datetime import datetime

logger = logging.getLogger("app.auth.otp")


def generate_code(length: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_code(code: str) -> str:
    return sha256_hex(code)


def is_expired(expires_at: datetime, now: datetime) -> bool:
    return now >= expires_at


class LogOtpSender:
    """Dev OTP delivery: prints the code to the server log (email later)."""

    def __init__(self) -> None:
        self.last_codes: dict[str, str] = {}

    async def send(self, identifier: str, code: str) -> None:
        self.last_codes[identifier] = code
        logger.info("OTP for %s: %s", identifier, code)
