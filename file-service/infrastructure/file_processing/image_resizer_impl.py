import os
from PIL import Image

from settings import settings
from core.interfaces.image_resizer import IImageResizer


class LocalImageResizer(IImageResizer):
    def __init__(self):
        self.files_dir = os.path.join(settings.storage_path, "files")

    async def resize(self, session_id: str, width: int, height: int) -> str:
        src = os.path.join(self.files_dir, session_id)
        dst = src

        with Image.open(src) as img:
            orig_w, orig_h = img.size
            target_ratio = width / height
            orig_ratio = orig_w / orig_h

            if orig_ratio > target_ratio:
                new_w = int(orig_h * target_ratio)
                offset = (orig_w - new_w) // 2
                img = img.crop((offset, 0, offset + new_w, orig_h))
            elif orig_ratio < target_ratio:
                new_h = int(orig_w / target_ratio)
                offset = (orig_h - new_h) // 2
                img = img.crop((0, offset, orig_w, offset + new_h))

            cropped_w, cropped_h = img.size
            if cropped_w > width or cropped_h > height:
                img = img.resize((width, height), Image.Resampling.LANCZOS)

            img = img.convert("RGB")
            img.save(dst, format="JPEG", quality=85)

        return dst
