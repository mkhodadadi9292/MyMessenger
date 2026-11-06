import uuid
from pathlib import Path

from app.application.ports import MediaLibrary


class LocalStorage(MediaLibrary):
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

    def path_for(self, relative_path: str) -> Path:
        return self.root / relative_path

    def exists(self, relative_path: str) -> bool:
        path = (self.root / relative_path).resolve()
        return path.is_file() and path.is_relative_to(self.root.resolve())
