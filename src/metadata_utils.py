from __future__ import annotations

from pathlib import Path

from PIL import ExifTags, Image


EXIF_NAME_MAP = {key: value for key, value in ExifTags.TAGS.items()}


def summarize_image_metadata(path: Path) -> str:
    lines = [f"文件：{path.name}", f"路径：{path}"]
    try:
        with Image.open(path) as img:
            lines.append(f"模式：{img.mode}")
            lines.append(f"尺寸：{img.width} x {img.height}")
            if img.info.get("dpi"):
                lines.append(f"DPI：{img.info.get('dpi')}")
            lines.append(f"ICC：{'存在' if img.info.get('icc_profile') else '无'}")
            lines.append(f"XMP：{'存在' if img.info.get('xmp') else '无'}")
            exif = img.getexif()
            if exif:
                lines.append("")
                lines.append("EXIF：")
                shown = 0
                for key, value in exif.items():
                    name = EXIF_NAME_MAP.get(key, f"Tag {key}")
                    lines.append(f"- {name}：{value}")
                    shown += 1
                    if shown >= 24:
                        break
    except Exception as exc:
        lines.append("")
        lines.append(f"元数据读取失败：{exc}")
    return "\n".join(lines)
