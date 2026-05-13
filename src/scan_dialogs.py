from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from app_settings import SCAN_MODE_ALL, SCAN_MODE_CURRENT_ONLY, SCAN_MODE_SUBDIRS_ONLY, normalize_scan_ignore_prefixes
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


class ScanModeDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, folder: Path, ignored_prefixes: list[str]) -> None:
        super().__init__(parent)
        self.title(app_window_title("选择文件夹扫描范围"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(False, True)
        self.minsize(620, 320)
        self.result: str | None = None
        self._size_notice_var = tk.StringVar(value="")
        self._ignored_prefixes = normalize_scan_ignore_prefixes(ignored_prefixes)

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas)
        content_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(content_id, width=canvas.winfo_width())

        def _sync_canvas_width(event) -> None:
            canvas.itemconfigure(content_id, width=event.width)

        content.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _sync_canvas_width)

        ttk.Label(
            content,
            text="当前文件夹包含子文件夹，请选择扫描范围。",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            content,
            text=(
                f"文件夹：{folder}\n"
                f"忽略前缀：{', '.join(self._ignored_prefixes)}\n"
                "名称符合这些前缀的文件夹会被跳过，里面的图片也不会扫描。"
            ),
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(8, 14))

        options = [
            (SCAN_MODE_ALL, "扫描全部，包含子文件夹", "扫描当前文件夹和所有允许进入的子文件夹。"),
            (SCAN_MODE_CURRENT_ONLY, "只扫描当前文件夹", "只读取当前文件夹里的图片。"),
            (SCAN_MODE_SUBDIRS_ONLY, "只扫描子文件夹", "只读取子文件夹中的图片。"),
        ]
        for mode, label, description in options:
            ttk.Button(content, text=label, command=lambda value=mode: self._choose(value)).pack(fill="x", pady=4)
            ttk.Label(content, text=description, wraplength=560, justify="left").pack(anchor="w", padx=(6, 0))

        action_row = ttk.Frame(outer)
        action_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(action_row, textvariable=self._size_notice_var).pack(side="left")
        ttk.Button(action_row, text="取消扫描", command=self._cancel).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update_idletasks()
        width = 640
        max_height = max(260, self.winfo_screenheight() - 120)
        requested_height = min(max_height, max(320, self.winfo_reqheight()))
        bind_minimum_size_notice(self, self._size_notice_var, 620, 320)
        center_window(self, width, requested_height)

    def _choose(self, mode: str) -> None:
        self.result = mode
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def show_scan_mode_dialog(parent: tk.Widget, folder: Path, ignored_prefixes: list[str]) -> str | None:
    dialog = ScanModeDialog(parent, folder, ignored_prefixes)
    dialog.wait_window()
    return dialog.result


__all__ = ["SCAN_MODE_ALL", "SCAN_MODE_CURRENT_ONLY", "SCAN_MODE_SUBDIRS_ONLY", "show_scan_mode_dialog"]
