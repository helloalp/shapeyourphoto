"""跨平台资源与用户数据目录路径解析。

打包成 PyInstaller 单文件/单目录后，资源（assets/）会被解压到 sys._MEIPASS；
用户配置/统计/缓存等可写文件必须落在系统标准的用户数据目录，
否则 Mac .app 内部 与 Windows Program Files 都是只读区。
"""

from __future__ import annotations

import functools
import shutil
import sys
from pathlib import Path


_APP_NAME = "ShapeYourPhoto"
_APP_AUTHOR = "Helloalp"

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def resource_path(relative: str | Path) -> Path:
    """返回打包资源的绝对路径，开发态退化到源码目录。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent / relative


@functools.cache
def user_data_dir() -> Path:
    """跨平台用户数据目录，目录会被自动创建（结果缓存，mkdir 仅首次执行）。

    macOS: ~/Library/Application Support/ShapeYourPhoto/
    Windows: %APPDATA%/Helloalp/ShapeYourPhoto/
    Linux:   ~/.local/share/ShapeYourPhoto/
    """
    try:
        from platformdirs import user_data_path

        path = Path(user_data_path(_APP_NAME, _APP_AUTHOR))
    except ImportError:
        if IS_MAC:
            path = Path.home() / "Library" / "Application Support" / _APP_NAME
        elif IS_WIN:
            import os

            base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            path = Path(base) / _APP_AUTHOR / _APP_NAME
        else:
            path = Path.home() / ".local" / "share" / _APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def migrate_legacy_file(filename: str) -> Path:
    """把旧版本写入 cwd 的 json 文件迁移到 user_data_dir。

    迁移仅在目标不存在且源存在时执行；返回最终的目标路径。
    """
    target = user_data_dir() / filename
    if target.exists():
        return target

    legacy = Path.cwd() / filename
    if legacy.is_file():
        try:
            shutil.copy2(legacy, target)
        except OSError:
            pass
    return target


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
