from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ui.window_titles import app_window_title
from window_layout import center_window


UPDATE_RECOMMENDATION = "建议更新以获得更多算法、更强性能与更佳体验。"


def _notes_text(manifest: dict[str, Any]) -> str:
    notes = manifest.get("release_notes", "")
    if isinstance(notes, list):
        return "\n\n".join(str(item) for item in notes)
    return str(notes or "云端未提供更新说明。")


class UpdateAvailableDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, manifest: dict[str, Any], *, manual: bool = False) -> None:
        super().__init__(parent)
        self.result = "later"
        self.title(app_window_title("发现新版本"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(620, 430)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.overrideredirect(True)
        try:
            self.attributes("-toolwindow", True)
        except tk.TclError:
            pass

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        version = manifest.get("version", "latest")
        ttk.Label(outer, text=f"ShapeYourPhoto {version}", font=("Microsoft YaHei UI", 13, "bold")).grid(row=0, column=0, sticky="w")

        text_frame = ttk.Frame(outer)
        text_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        notes = tk.Text(text_frame, wrap="word", height=13, padx=10, pady=10)
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=notes.yview)
        notes.configure(yscrollcommand=scroll.set)
        notes.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        notes.insert("1.0", _notes_text(manifest))
        notes.config(state="disabled")

        ttk.Label(outer, text=UPDATE_RECOMMENDATION, font=("Microsoft YaHei UI", 10, "bold")).grid(row=2, column=0, sticky="w")

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(1, weight=1)
        left_text = "暂时不更新"
        if manual:
            left_text = "暂时不更新"
        ttk.Button(actions, text=left_text, command=lambda: self._finish("decline")).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="稍后更新", command=lambda: self._finish("later")).grid(row=0, column=1)
        ttk.Button(actions, text="更新", command=lambda: self._finish("update")).grid(row=0, column=2, sticky="e")
        center_window(self, 700, 520)

    def _finish(self, result: str) -> None:
        self.result = result
        self.destroy()


def show_update_available_dialog(parent: tk.Widget, manifest: dict[str, Any], *, manual: bool = False) -> str:
    dialog = UpdateAvailableDialog(parent, manifest, manual=manual)
    dialog.wait_window()
    return dialog.result


class CheckingUpdateDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title(app_window_title("检查更新"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.overrideredirect(True)
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="正在检查更新...", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        bar = ttk.Progressbar(outer, mode="indeterminate", length=260)
        bar.pack(fill="x", pady=(14, 0))
        bar.start(12)
        center_window(self, 360, 150)


class CloudMessageDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        message: dict[str, Any],
        *,
        update_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(app_window_title(str(message.get("title") or "云端公告")))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(560, 360)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.overrideredirect(True)
        self._remaining = int(message.get("countdown_seconds") or 0) if message.get("countdown_enabled") else 0
        self._confirm_var = tk.StringVar(value="确认")
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(outer, text=str(message.get("title") or "ShapeYourPhoto 公告"), font=("Microsoft YaHei UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        text_frame = ttk.Frame(outer)
        text_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        body = tk.Text(text_frame, wrap="word", padx=10, pady=10)
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=scroll.set)
        body.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        body.insert("1.0", str(message.get("body") or ""))
        body.config(state="disabled")
        actions = ttk.Frame(outer)
        actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        if message.get("show_update_button") and update_callback is not None:
            ttk.Button(actions, text="更新", command=update_callback).grid(row=0, column=1, padx=(0, 8))
        self.confirm_button = ttk.Button(actions, textvariable=self._confirm_var, command=self.destroy)
        self.confirm_button.grid(row=0, column=2)
        if self._remaining > 0:
            self.confirm_button.configure(state="disabled")
            self._tick()
        center_window(self, 650, 460)

    def _tick(self) -> None:
        if self._remaining <= 0:
            self._confirm_var.set("确认")
            self.confirm_button.configure(state="normal")
            return
        self._confirm_var.set(f"确认 ({self._remaining}s)")
        self._remaining -= 1
        self.after(1000, self._tick)


def show_cloud_message_dialog(
    parent: tk.Widget,
    message: dict[str, Any],
    *,
    update_callback: Callable[[], None] | None = None,
) -> None:
    dialog = CloudMessageDialog(parent, message, update_callback=update_callback)
    dialog.wait_window()
