from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageOps, ImageTk


class ThumbnailCache:
    def __init__(self, *, max_items: int = 900) -> None:
        self.max_items = max(64, int(max_items))
        self._tree_cache: OrderedDict[tuple[str, int, int], ImageTk.PhotoImage] = OrderedDict()

    def get_tree_thumbnail(self, path: Path, size: tuple[int, int] = (90, 68)) -> ImageTk.PhotoImage | None:
        cache_key = (str(path), size[0] * 1000 + size[1], self._mtime_stamp(path))
        if cache_key in self._tree_cache:
            self._tree_cache.move_to_end(cache_key)
            return self._tree_cache[cache_key]

        try:
            with Image.open(path) as img:
                try:
                    img.draft("RGB", (max(1, size[0] * 2), max(1, size[1] * 2)))
                except Exception:
                    pass
                image = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return None

        image.thumbnail(size)
        thumb = Image.new("RGB", size, (237, 242, 238))
        offset_x = (size[0] - image.width) // 2
        offset_y = (size[1] - image.height) // 2
        thumb.paste(image, (offset_x, offset_y))
        photo = ImageTk.PhotoImage(thumb)
        self._evict_stale_path_keys(path, keep_key=cache_key)
        self._tree_cache[cache_key] = photo
        self._tree_cache.move_to_end(cache_key)
        while len(self._tree_cache) > self.max_items:
            self._tree_cache.popitem(last=False)
        return photo

    def clear(self) -> None:
        self._tree_cache.clear()

    def evict(self, path: Path) -> None:
        prefix = str(path)
        doomed = [key for key in self._tree_cache if key[0] == prefix]
        for key in doomed:
            self._tree_cache.pop(key, None)

    def _evict_stale_path_keys(self, path: Path, *, keep_key: tuple[str, int, int]) -> None:
        prefix = str(path)
        for key in [key for key in self._tree_cache if key[0] == prefix and key != keep_key]:
            self._tree_cache.pop(key, None)

    def _mtime_stamp(self, path: Path) -> int:
        try:
            stat = path.stat()
            return int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        except Exception:
            return 0
