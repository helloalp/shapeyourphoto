from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import font as tkfont, ttk


def enable_dpi_awareness() -> str:
    """Enable best-effort Windows DPI awareness before Tk creates windows."""
    try:
        shcore = ctypes.windll.shcore
        # Per-monitor DPI aware. Older systems may reject this and fall back.
        result = shcore.SetProcessDpiAwareness(2)
        return "per-monitor" if result == 0 else f"system-fallback({result})"
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return "system"
        except Exception:
            return "unavailable"


def configure_tk_scaling(root: tk.Misc) -> float:
    try:
        dpi = float(root.winfo_fpixels("1i"))
    except Exception:
        dpi = 96.0
    scaling = max(1.0, min(2.5, dpi / 72.0))
    try:
        root.tk.call("tk", "scaling", scaling)
    except Exception:
        pass
    return scaling


def configure_fonts(root: tk.Misc, *, delta: int = 0) -> dict[str, str]:
    families = set(tkfont.families(root))
    ui_family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in families else "Segoe UI"
    mono_family = "Cascadia Mono" if "Cascadia Mono" in families else "Consolas"
    base_size = 10 + int(delta or 0)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
        try:
            font = tkfont.nametofont(name)
            font.configure(family=ui_family, size=base_size)
        except Exception:
            pass
    try:
        tkfont.nametofont("TkFixedFont").configure(family=mono_family, size=max(9, base_size - 1))
    except Exception:
        pass
    style = ttk.Style(root)
    style.configure(".", font=(ui_family, base_size))
    return {"ui": ui_family, "mono": mono_family, "base_size": str(base_size)}
