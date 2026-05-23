from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageOps, ImageTk


class ThumbnailCache:
    def __init__(self, *, max_items: int = 900) -> None:
        self.max_items = max(64, int(max_items))
        self._tree_cache: OrderedDict[tuple[str, int, int, bool], ImageTk.PhotoImage] = OrderedDict()
        self._duplicate_badge: Image.Image | None = None

    def get_tree_thumbnail(self, path: Path, size: tuple[int, int] = (90, 68), *, duplicate_badge: bool = False) -> ImageTk.PhotoImage | None:
        cache_key = (str(path), size[0] * 1000 + size[1], self._mtime_stamp(path), duplicate_badge)
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
        if duplicate_badge:
            badge = self._get_duplicate_badge()
            if badge is not None:
                thumb = thumb.convert("RGBA")
                thumb.alpha_composite(badge, (size[0] - badge.width - 3, 3))
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

    def _evict_stale_path_keys(self, path: Path, *, keep_key: tuple[str, int, int, bool]) -> None:
        prefix = str(path)
        for key in [key for key in self._tree_cache if key[0] == prefix and key != keep_key]:
            self._tree_cache.pop(key, None)

    def _mtime_stamp(self, path: Path) -> int:
        try:
            stat = path.stat()
            return int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        except Exception:
            return 0

    def _get_duplicate_badge(self) -> Image.Image | None:
        if self._duplicate_badge is not None:
            return self._duplicate_badge
        badge_path = Path(__file__).resolve().parents[1] / "assets" / "ui" / "info_duplicate.png"
        try:
            with Image.open(badge_path) as image:
                self._duplicate_badge = image.convert("RGBA").resize((18, 18), Image.Resampling.LANCZOS)
        except Exception:
            return None
        return self._duplicate_badge
