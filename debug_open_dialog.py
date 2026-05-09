from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from ui.window_titles import app_window_title
from window_layout import center_window


@dataclass(frozen=True)
class DebugOpenEntry:
    display_name: str
    source_path: Path
    output_path: Path


class DebugOpenDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, entries: list[DebugOpenEntry]) -> None:
        super().__init__(parent)
        self.title(app_window_title("调试打开前后图片"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(620, 360)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.result: list[DebugOpenEntry] | None = None
        self._entries = entries
        self._vars = [tk.BooleanVar(value=True) for _ in entries]

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="本轮修复成功的图片如下，可选择打开原图和修复图进行对比。").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        list_shell = ttk.Frame(outer)
        list_shell.grid(row=1, column=0, sticky="nsew")
        list_shell.columnconfigure(0, weight=1)
        list_shell.rowconfigure(0, weight=1)

        canvas = tk.Canvas(list_shell, bg="#fbfcfa", highlightthickness=0)
        scroll = ttk.Scrollbar(list_shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas, padding=(4, 4, 8, 4))
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_scroll(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _fit_content(_event=None) -> None:
            canvas.itemconfigure(window_id, width=max(420, canvas.winfo_width()))

        content.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", _fit_content)

        for index, entry in enumerate(entries):
            row = ttk.Frame(content, padding=(4, 4))
            row.pack(fill="x", pady=2)
            ttk.Checkbutton(row, variable=self._vars[index]).pack(side="left")
            ttk.Label(row, text=f"{entry.display_name}    原图 + 修复图").pack(side="left", padx=(6, 0))

        button_row = ttk.Frame(outer)
        button_row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(button_row, text="关闭", command=self._close).pack(side="right")
        ttk.Button(button_row, text="取消全选", command=self._unselect_all).pack(side="right", padx=(0, 8))
        ttk.Button(button_row, text="全选", command=self._select_all).pack(side="right", padx=(0, 8))
        ttk.Button(button_row, text="打开选中前后版本", command=self._confirm).pack(side="left")

        center_window(self, 760, 520)

    def _select_all(self) -> None:
        for variable in self._vars:
            variable.set(True)

    def _unselect_all(self) -> None:
        for variable in self._vars:
            variable.set(False)

    def _confirm(self) -> None:
        chosen = [entry for entry, variable in zip(self._entries, self._vars) if variable.get()]
        if not chosen:
            messagebox.showinfo("提示", "请至少勾选一项。", parent=self)
            return
        self.result = chosen
        self.destroy()

    def _close(self) -> None:
        self.result = None
        self.destroy()


def show_debug_open_dialog(parent: tk.Widget, entries: list[DebugOpenEntry]) -> list[DebugOpenEntry] | None:
    dialog = DebugOpenDialog(parent, entries)
    dialog.wait_window()
    return dialog.result
