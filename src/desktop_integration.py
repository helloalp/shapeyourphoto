from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app_metadata import APP_ID
from paths import IS_WIN, is_frozen, resource_path, user_data_dir


def ensure_app_icon() -> tuple[Path, Path]:
    png_path = resource_path("assets/app_icon.png")
    ico_path = resource_path("assets/app_icon.ico")
    if png_path.exists() and ico_path.exists():
        return png_path, ico_path

    # 打包态下 _MEIPASS 是只读；走到这里说明 spec datas 漏了 assets，退到 user_data_dir 兜底
    if is_frozen():
        target_dir = user_data_dir() / "assets"
        target_dir.mkdir(parents=True, exist_ok=True)
        png_path = target_dir / "app_icon.png"
        ico_path = target_dir / "app_icon.ico"
        if png_path.exists() and ico_path.exists():
            return png_path, ico_path
    else:
        png_path.parent.mkdir(parents=True, exist_ok=True)

    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle((20, 20, 236, 236), radius=56, fill=(28, 58, 48, 255))
    draw.ellipse((56, 56, 200, 200), fill=(236, 247, 236, 255))
    draw.ellipse((82, 82, 174, 174), fill=(28, 58, 48, 255))
    draw.polygon([(182, 174), (228, 220), (214, 234), (166, 188)], fill=(246, 198, 91, 255))
    draw.rectangle((48, 178, 128, 196), fill=(246, 198, 91, 255))
    draw.rectangle((48, 156, 106, 170), fill=(244, 120, 76, 255))

    try:
        canvas.save(png_path)
        canvas.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    except OSError:
        pass
    return png_path, ico_path


def _configure_windows_taskbar(root, ico_path: Path) -> None:
    """设置 Windows 任务栏 AppUserModelID 与 hwnd 图标。"""
    if not IS_WIN:
        return
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

    try:
        icon = ctypes.windll.user32.LoadImageW(0, str(ico_path), 1, 0, 0, 0x00000010)
        if icon:
            ctypes.windll.user32.SendMessageW(root.winfo_id(), 0x0080, 0, icon)
            ctypes.windll.user32.SendMessageW(root.winfo_id(), 0x0080, 1, icon)
    except Exception:
        pass


def configure_window_icon(root) -> None:
    png_path, ico_path = ensure_app_icon()

    _configure_windows_taskbar(root, ico_path)

    # iconbitmap 仅 Windows 接受 .ico；macOS/Linux 走 iconphoto。
    if IS_WIN:
        try:
            root.iconbitmap(default=str(ico_path))
        except Exception:
            pass

    try:
        from tkinter import PhotoImage

        root._app_icon = PhotoImage(file=str(png_path))
        root.iconphoto(True, root._app_icon)
    except Exception:
        pass
