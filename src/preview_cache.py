from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps, ImageTk


class ThumbnailCache:
    def __init__(self) -> None:
        self._tree_cache: dict[tuple[str, int], ImageTk.PhotoImage] = {}

    def get_tree_thumbnail(self, path: Path, size: tuple[int, int] = (90, 68)) -> ImageTk.PhotoImage | None:
        cache_key = (str(path), size[0] * 1000 + size[1])
        if cache_key in self._tree_cache:
            return self._tree_cache[cache_key]

        try:
            with Image.open(path) as img:
                image = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return None

        image.thumbnail(size)
        thumb = Image.new("RGB", size, (237, 242, 238))
        offset_x = (size[0] - image.width) // 2
        offset_y = (size[1] - image.height) // 2
        thumb.paste(image, (offset_x, offset_y))
        photo = ImageTk.PhotoImage(thumb)
        self._tree_cache[cache_key] = photo
        return photo

    def clear(self) -> None:
        self._tree_cache.clear()

    def evict(self, path: Path) -> None:
        prefix = str(path)
        doomed = [key for key in self._tree_cache if key[0] == prefix]
        for key in doomed:
            self._tree_cache.pop(key, None)
