from __future__ import annotations

import functools
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from paths import IS_MAC, IS_WIN, resource_path


SOFTWARE_NAME = "ShapeYourPhoto"
AUTHOR_NAME = "Helloalp"


@functools.cache
def _font_candidates() -> list[Path]:
    """按优先级返回字体候选：先用打包内字体，再退系统中文字体。结果缓存。"""
    bundled = [
        resource_path("assets/fonts/SourceHanSansCN-Regular.otf"),
        resource_path("assets/fonts/NotoSansCJKsc-Regular.otf"),
    ]
    if IS_WIN:
        system = [
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\msyhbd.ttc"),
            Path(r"C:\Windows\Fonts\arial.ttf"),
        ]
    elif IS_MAC:
        system = [
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
        ]
    else:
        system = [
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    return bundled + system


@functools.cache
def _resolve_font_path() -> Path | None:
    """返回首个真实存在的字体路径，缓存结果避免每张图重复 stat。"""
    for path in _font_candidates():
        if path.exists():
            return path
    return None


def _load_overlay_font(image: Image.Image) -> ImageFont.ImageFont:
    font_size = max(14, int(min(image.size) * 0.018))
    path = _resolve_font_path()
    if path is not None:
        try:
            return ImageFont.truetype(str(path), font_size)
        except OSError:
            pass
    return ImageFont.load_default()


def add_signature_overlay(image: Image.Image, text: str | None = None) -> Image.Image:
    signed = image.copy()
    draw = ImageDraw.Draw(signed, "RGBA")
    font = _load_overlay_font(signed)
    overlay_text = text or f"{SOFTWARE_NAME} | {AUTHOR_NAME}"
    bbox = draw.textbbox((0, 0), overlay_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    margin = max(16, int(min(signed.size) * 0.02))
    x0 = signed.width - text_w - margin * 2
    y0 = signed.height - text_h - margin * 2
    draw.rounded_rectangle((x0, y0, signed.width - margin, signed.height - margin), radius=10, fill=(18, 30, 24, 145))
    draw.text((x0 + margin // 2, y0 + margin // 2), overlay_text, font=font, fill=(245, 251, 246, 230))
    return signed
