import uuid
from pathlib import Path


class LocalStorage:
    """File storage under the media root; Nginx serves this tree in prod."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, subdir: str, file_name: str, content: bytes) -> str:
        ext = Path(file_name).suffix.lower()
        relative = f"{subdir}/{uuid.uuid4().hex}{ext}"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return relative

    def path_for(self, relative: str) -> Path:
        return self.root / relative
