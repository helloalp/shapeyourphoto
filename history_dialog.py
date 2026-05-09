from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app_metadata import CHANGELOG
from ui.window_titles import app_window_title
from window_layout import center_window


def show_history_dialog(parent: tk.Widget) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title(app_window_title("更新历史"))
    dialog.minsize(680, 520)
    dialog.resizable(True, True)
    dialog.transient(parent.winfo_toplevel())
    center_window(dialog, 820, 680)

    outer = ttk.Frame(dialog, padding=14)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text="更新历史", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
    ttk.Label(outer, text="这里列出版本和变更记录。").pack(anchor="w", pady=(4, 10))

    frame = ttk.Frame(outer)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    text = tk.Text(frame, wrap="word", font=("Microsoft YaHei UI", 10), bg="#f8fbf8", relief="flat", padx=10, pady=10)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")

    lines: list[str] = []
    for entry in CHANGELOG:
        lines.append(f"{entry['version']} - {entry['date']}")
        for item in entry["items"]:
            lines.append(f"- {item}")
        lines.append("")

    text.insert("1.0", "\n".join(lines).strip())
    text.config(state="disabled")

    ttk.Button(outer, text="关闭", command=dialog.destroy).pack(anchor="e", pady=(10, 0))
