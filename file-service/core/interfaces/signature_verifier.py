class ISignatureVerifier:
    async def verify(self, signature: str, lookup_key: str) -> bool:
        raise NotImplementedError
