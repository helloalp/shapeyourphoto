from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import re

from app_metadata import CHANGELOG, CHANGELOG_I18N
from ui.language import get_current_language, normalize_language, tr
from ui.window_titles import app_window_title
from window_layout import center_window


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _plain_history_item(value: object) -> str:
    text = str(value).strip()
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = text.replace("`", "")
    replacements = [
        ("no-op", tr("history.term.noop")),
        ("cleanup candidates", tr("history.term.cleanup_candidates")),
        ("cleanup candidate", tr("history.term.cleanup_candidates")),
        ("cleanup/similar", tr("history.term.cleanup_similar")),
        ("cleanup", tr("history.term.cleanup")),
        ("critical", tr("history.term.critical")),
        ("severe_overexposed", tr("history.term.severe_overexposed")),
    ]
    for raw, label in replacements:
        text = text.replace(raw, label)
    return text


def show_history_dialog(parent: tk.Widget) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title(app_window_title(tr("history.title")))
    dialog.minsize(680, 520)
    dialog.resizable(True, True)
    dialog.transient(parent.winfo_toplevel())
    center_window(dialog, 820, 680)

    outer = ttk.Frame(dialog, padding=14)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text=tr("history.title"), font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")

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

    lang = normalize_language(get_current_language())
    localized_entries = CHANGELOG_I18N.get(lang, [])
    localized_versions = {str(entry.get("version")) for entry in localized_entries}
    entries = [*localized_entries, *[entry for entry in CHANGELOG if str(entry.get("version")) not in localized_versions]]
    for entry in entries:
        text.insert("end", f"{entry['version']}  {entry['date']}\n", "version")
        for index, item in enumerate(entry["items"], start=1):
            text.insert("end", f"{index}. {_plain_history_item(item)}\n", "item")
        text.insert("end", "\n")
    text.config(state="disabled")

    ttk.Button(outer, text=tr("action.close"), command=dialog.destroy).pack(anchor="e", pady=(10, 0))
