import base64
import json
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class TokenValidationError(Exception):
    pass


class TokenValidator:
    def __init__(self, public_key_path: str = "infrastructure/key/public_key.pem"):
        self.public_key = self._load_public_key(public_key_path)

    @staticmethod
    def _load_public_key(path: str) -> Ed25519PublicKey:
        with open(path, "rb") as f:
            return serialization.load_pem_public_key(f.read())

    @staticmethod
    def _b64decode(data: str) -> bytes:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)

    def validate(self, token: str) -> dict:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError:
            raise TokenValidationError("Invalid token format")

        unsigned = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = self._b64decode(signature_b64)

        try:
            self.public_key.verify(signature, unsigned)
        except Exception:
            raise TokenValidationError("Invalid signature")

        payload_raw = self._b64decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))

        now = int(time.time())
        if payload.get("exp") is None or payload["exp"] < now:
            raise TokenValidationError("Token expired")

        return payload
