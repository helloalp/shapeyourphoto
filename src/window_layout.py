from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass

from paths import IS_WIN

MIN_SIZE_NOTICE = "已达到最小可用窗口大小。"
DEFAULT_DIALOG_MARGIN = 22
DEFAULT_FOOTER_HEIGHT = 58
DEFAULT_ACTION_GAP = 8


@dataclass(frozen=True)
class LayoutDefaults:
    main_window_scale: float = 0.60
    dialog_window_scale: float = 0.78
    main_pane_ratio: float = 0.56
    main_pane_left_min: int = 620
    main_pane_right_min: int = 520


LAYOUT_DEFAULTS = LayoutDefaults()
DEFAULT_MAIN_WINDOW_SCALE = LAYOUT_DEFAULTS.main_window_scale
DEFAULT_DIALOG_WINDOW_SCALE = LAYOUT_DEFAULTS.dialog_window_scale


def default_layout_settings() -> dict[str, float]:
    return {
        "main_window_scale": LAYOUT_DEFAULTS.main_window_scale,
        "dialog_window_scale": LAYOUT_DEFAULTS.dialog_window_scale,
    }


def clamp_window_scale(value: object, *, default: float = DEFAULT_MAIN_WINDOW_SCALE) -> float:
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.45, min(0.95, scale))


def _get_work_area() -> tuple[int, int, int, int] | None:
    if not IS_WIN:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        rect = RECT()
        SPI_GETWORKAREA = 48
        if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None
    return None


def center_window(
    window: tk.Misc,
    desired_width: int,
    desired_height: int,
    min_margin: int = DEFAULT_DIALOG_MARGIN,
    *,
    parent: tk.Widget | None = None,
    max_parent_ratio: float | None = None,
) -> tuple[int, int]:
    window.update_idletasks()
    area = _get_work_area()
    if area is None:
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        left, top, right, bottom = 0, 0, screen_w, screen_h
    else:
        left, top, right, bottom = area

    avail_w = max(360, right - left - min_margin * 2)
    avail_h = max(260, bottom - top - min_margin * 2)
    width = max(1, min(int(desired_width), avail_w))
    height = max(1, min(int(desired_height), avail_h))
    try:
        min_w = int(window.minsize()[0])
        min_h = int(window.minsize()[1])
        width = max(width, min_w)
        height = max(height, min_h)
    except Exception:
        min_w = 1
        min_h = 1
    if parent is not None and max_parent_ratio is not None:
        try:
            parent_root = parent.winfo_toplevel()
            parent_w = parent_root.winfo_width()
            parent_h = parent_root.winfo_height()
            if parent_w > 1 and parent_h > 1:
                ratio = clamp_window_scale(max_parent_ratio, default=DEFAULT_DIALOG_WINDOW_SCALE)
                width = min(width, max(min_w, int(parent_w * ratio)))
                height = min(height, max(min_h, int(parent_h * ratio)))
        except Exception:
            pass
    x = left + max(min_margin, (right - left - width) // 2)
    y = top + max(min_margin, (bottom - top - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    try:
        if isinstance(window, tk.Toplevel):
            window.deiconify()
    except Exception:
        pass
    return width, height


def center_main_window(window: tk.Misc, *, scale: object = DEFAULT_MAIN_WINDOW_SCALE) -> tuple[int, int]:
    normalized = clamp_window_scale(scale, default=DEFAULT_MAIN_WINDOW_SCALE)
    area = _get_work_area()
    if area is None:
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
    else:
        left, top, right, bottom = area
        screen_w = right - left
        screen_h = bottom - top
    desired_width = int(screen_w * normalized)
    desired_height = int(screen_h * normalized)
    return center_window(window, desired_width, desired_height)


def default_main_pane_sash(width: int) -> int:
    width = max(1, int(width or 1))
    left_min = LAYOUT_DEFAULTS.main_pane_left_min
    right_min = LAYOUT_DEFAULTS.main_pane_right_min
    return min(max(left_min, int(width * LAYOUT_DEFAULTS.main_pane_ratio)), max(left_min, width - right_min))


def dialog_size_for_parent(
    parent: tk.Widget | None,
    *,
    fallback_width: int,
    fallback_height: int,
    scale: object = DEFAULT_DIALOG_WINDOW_SCALE,
    min_width: int = 360,
    min_height: int = 260,
) -> tuple[int, int]:
    normalized = clamp_window_scale(scale, default=DEFAULT_DIALOG_WINDOW_SCALE)
    if parent is None:
        return fallback_width, fallback_height
    try:
        parent_root = parent.winfo_toplevel()
        parent_root.update_idletasks()
        parent_w = parent_root.winfo_width()
        parent_h = parent_root.winfo_height()
        if parent_w > 1 and parent_h > 1:
            return max(min_width, int(parent_w * normalized)), max(min_height, int(parent_h * normalized))
    except Exception:
        pass
    return fallback_width, fallback_height


def create_dialog_window(
    parent: tk.Widget,
    *,
    title: str,
    min_width: int,
    min_height: int,
    resizable: tuple[bool, bool] = (True, True),
    modal: bool = True,
) -> tk.Toplevel:
    dialog = tk.Toplevel(parent)
    prepare_dialog_window(
        dialog,
        parent,
        title=title,
        min_width=min_width,
        min_height=min_height,
        resizable=resizable,
        modal=modal,
    )
    return dialog


def prepare_dialog_window(
    window: tk.Toplevel,
    parent: tk.Widget | None,
    *,
    title: str,
    min_width: int,
    min_height: int,
    resizable: tuple[bool, bool] = (True, True),
    modal: bool = True,
) -> None:
    """Apply the shared dialog contract before widgets are laid out."""
    window.withdraw()
    window.title(title)
    if parent is not None:
        try:
            window.transient(parent.winfo_toplevel())
        except Exception:
            pass
    window.resizable(*resizable)
    window.minsize(min_width, min_height)
    if modal and parent is not None:
        try:
            window.grab_set()
        except Exception:
            pass


def make_footer(parent: tk.Widget, *, row: int, pady: tuple[int, int] = (14, 0)) -> ttk.Frame:
    footer = ttk.Frame(parent)
    footer.grid(row=row, column=0, sticky="ew", pady=pady)
    footer.grid_columnconfigure(0, weight=1)
    return footer


def bind_minimum_size_notice(
    window: tk.Misc,
    notice_var: tk.StringVar,
    min_width: int,
    min_height: int,
    *,
    threshold: int = 8,
) -> None:
    def _update(event=None) -> None:
        if event is not None and event.widget is not window:
            return
        width = window.winfo_width()
        height = window.winfo_height()
        if width <= min_width + threshold and height <= min_height + threshold:
            notice_var.set(MIN_SIZE_NOTICE)
        elif notice_var.get() == MIN_SIZE_NOTICE:
            notice_var.set("")

    window.bind("<Configure>", _update, add="+")
    try:
        window.after_idle(_update)
    except Exception:
        pass
