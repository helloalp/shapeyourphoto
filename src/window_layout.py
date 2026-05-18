from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from paths import IS_WIN

MIN_SIZE_NOTICE = "已达到最小可用窗口大小。"
DEFAULT_DIALOG_MARGIN = 22
DEFAULT_FOOTER_HEIGHT = 58
DEFAULT_ACTION_GAP = 8


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


def center_window(window: tk.Misc, desired_width: int, desired_height: int, min_margin: int = DEFAULT_DIALOG_MARGIN) -> tuple[int, int]:
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
    width = min(desired_width, avail_w)
    height = min(desired_height, avail_h)
    x = left + max(min_margin, (right - left - width) // 2)
    y = top + max(min_margin, (bottom - top - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    try:
        if isinstance(window, tk.Toplevel):
            window.deiconify()
    except Exception:
        pass
    return width, height


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
