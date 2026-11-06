from dataclasses import dataclass

@dataclass
class DownloadPayload:
    lookup_key: str
    exp: int
