from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from app_metadata import APP_NAME, APP_VERSION
from window_layout import center_window


class SplashScreen:
    def __init__(self, root: tk.Tk, *, min_ms: int = 900) -> None:
        self.root = root
        self.min_ms = max(300, min_ms)
        self._photo: ImageTk.PhotoImage | None = None
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.configure(bg="#f7faf8")
        self.window.attributes("-topmost", True)
        outer = tk.Frame(self.window, bg="#f7faf8", padx=28, pady=24)
        outer.pack(fill="both", expand=True)

        logo_path = Path("assets/app_icon.png")
        if logo_path.exists():
            try:
                with Image.open(logo_path) as img:
                    image = img.convert("RGBA")
                    image.thumbnail((96, 96))
                    self._photo = ImageTk.PhotoImage(image)
                    tk.Label(outer, image=self._photo, bg="#f7faf8").pack(pady=(0, 10))
            except Exception:
                self._photo = None
        if self._photo is None:
            tk.Label(
                outer,
                text="SYP",
                bg="#2f8f63",
                fg="#ffffff",
                font=("Segoe UI", 28, "bold"),
                width=4,
                height=1,
            ).pack(pady=(0, 10))

        tk.Label(outer, text="ShapeYourPhoto", bg="#f7faf8", fg="#17361f", font=("Segoe UI", 18, "bold")).pack()
        tk.Label(outer, text=f"{APP_NAME} v{APP_VERSION}", bg="#f7faf8", fg="#45604d", font=("Microsoft YaHei UI", 10)).pack(pady=(4, 0))
        center_window(self.window, 420, 260)
        self.window.update_idletasks()

    def close_after_ready(self) -> None:
        def _close() -> None:
            try:
                self.window.attributes("-topmost", False)
                self.window.destroy()
            except Exception:
                pass

        self.root.after(self.min_ms, _close)
