from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import re

from app_metadata import CHANGELOG
from ui.window_titles import app_window_title
from window_layout import center_window


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _plain_history_item(value: object) -> str:
    text = str(value).strip()
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = text.replace("`", "")
    replacements = [
        ("no-op", "未生成新的修复版本"),
        ("cleanup candidates", "不适合保留图片"),
        ("cleanup candidate", "不适合保留图片"),
        ("cleanup/similar", "不适合保留图片/相似图"),
        ("cleanup", "清理"),
        ("critical", "极其严重"),
        ("severe_overexposed", "严重过度曝光"),
    ]
    for raw, label in replacements:
        text = text.replace(raw, label)
    return text


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

    frame = ttk.Frame(outer)
    frame.pack(fill="both", expand=True, pady=(10, 0))
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    text = tk.Text(frame, wrap="word", font=("Microsoft YaHei UI", 10), bg="#f8fbf8", relief="flat", padx=10, pady=10)
    text.tag_configure("version", font=("Microsoft YaHei UI", 11, "bold"), spacing1=8, spacing3=4)
    text.tag_configure("item", lmargin1=18, lmargin2=38, spacing2=2)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")

    for entry in CHANGELOG:
        text.insert("end", f"{entry['version']}  {entry['date']}\n", "version")
        for index, item in enumerate(entry["items"], start=1):
            text.insert("end", f"{index}. {_plain_history_item(item)}\n", "item")
        text.insert("end", "\n")
    text.config(state="disabled")

    ttk.Button(outer, text="关闭", command=dialog.destroy).pack(anchor="e", pady=(10, 0))
