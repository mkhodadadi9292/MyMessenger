import os
import subprocess
from PIL import Image

from settings import settings
from infrastructure.logging.logger import logger
from core.interfaces.thumbnail_service import IThumbnailService


class LocalThumbnailService(IThumbnailService):
    def __init__(self):
        self.files_dir = os.path.join(settings.storage_path, "files")
        self.thumbs_dir = os.path.join(settings.storage_path, "thumbnails")

    async def generate_image_thumbnail(self, session_id: str) -> bool:
        src = os.path.join(self.files_dir, session_id)
        dst = os.path.join(self.thumbs_dir, f"{session_id}.jpg")

        try:
            with Image.open(src) as img:
                img.thumbnail((320, 320))
                img = img.convert("RGB")
                img.save(dst, "JPEG", quality=70)
            return True
        except Exception as e:
            logger.error(f"[Thumbnail][IMAGE] Failed for {session_id}: {type(e).__name__}: {e}")
            return False

    async def generate_video_thumbnail(self, session_id: str) -> bool:
        src = os.path.join(self.files_dir, session_id)
        dst = os.path.join(self.thumbs_dir, f"{session_id}.jpg")

        try:
            cmd = [
                "ffmpeg",
                "-i", src,
                "-vf", "thumbnail",
                "-frames:v", "1",
                dst,
                "-y"
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return os.path.exists(dst) and os.path.getsize(dst) > 0
        except Exception as e:
            logger.error(f"[Thumbnail][VIDEO] Failed for {session_id}: {type(e).__name__}: {e}")
            return False

    async def generate_audio_thumbnail(self, session_id: str, file_ext: str | None = None) -> bool:
        src = os.path.join(self.files_dir, session_id)
        dst = os.path.join(self.thumbs_dir, f"{session_id}.jpg")

        try:
            if not file_ext:
                return False

            file_ext = file_ext.lower()

            if file_ext in ("mp3", "m4a", "mp4", "aac", "flac"):
                cmd = [
                    "ffmpeg",
                    "-i", src,
                    "-an",
                    "-vcodec", "copy",
                    dst,
                    "-y"
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return os.path.exists(dst) and os.path.getsize(dst) > 0

            return False
        except Exception as e:
            logger.error(f"[Thumbnail][AUDIO] Failed for {session_id}: {type(e).__name__}: {e}")
            return False

    async def delete_thumbnail(self, session_id: str):
        thumb_path = os.path.join(self.thumbs_dir, f"{session_id}.jpg")
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

    async def get_thumbnail(self, session_id: str) -> bytes:
        thumb_path = os.path.join(self.thumbs_dir, f"{session_id}.jpg")
        try:
            if not os.path.exists(thumb_path):
                return b""

            with open(thumb_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"[Thumbnail][GET] Failed for {session_id}: {type(e).__name__}: {e}")
            return b""
