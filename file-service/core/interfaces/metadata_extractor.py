from typing import Dict, Any


class IFileMetadataExtractor:
    async def extract(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError
