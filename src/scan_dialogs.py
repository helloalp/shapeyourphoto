from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from app_settings import (
    SCAN_MODE_ALL,
    SCAN_MODE_CURRENT_ONLY,
    SCAN_MODE_SUBDIRS_ONLY,
    normalize_scan_ignore_contains,
    normalize_scan_ignore_prefixes,
    normalize_scan_ignore_suffixes,
)
from ui.language import tr
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


def _rule_text(label: str, values: list[str]) -> str:
    return label.format(values=", ".join(values) if values else tr("scan_dialog.none"))


class ScanModeDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        folder: Path,
        ignored_prefixes: list[str],
        ignored_suffixes: list[str] | None = None,
        ignored_contains: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(app_window_title(tr("scan_dialog.title")))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(680, 460)
        self.result: str | None = None
        self._size_notice_var = tk.StringVar(value="")
        self._ignored_prefixes = normalize_scan_ignore_prefixes(ignored_prefixes)
        self._ignored_suffixes = normalize_scan_ignore_suffixes(ignored_suffixes)
        self._ignored_contains = normalize_scan_ignore_contains(ignored_contains)

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
            text=tr("scan_dialog.heading"),
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            content,
            text=(
                f"{tr('scan_dialog.folder').format(folder=folder)}\n"
                f"{_rule_text(tr('scan_dialog.prefix'), self._ignored_prefixes)}\n"
                f"{_rule_text(tr('scan_dialog.suffix'), self._ignored_suffixes)}\n"
                f"{_rule_text(tr('scan_dialog.contains'), self._ignored_contains)}\n"
                f"{tr('scan_dialog.rule_note')}"
            ),
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(8, 14))

        options = [
            (SCAN_MODE_ALL, tr("scan_dialog.all"), tr("scan_dialog.all_desc")),
            (SCAN_MODE_CURRENT_ONLY, tr("scan_dialog.current"), tr("scan_dialog.current_desc")),
            (SCAN_MODE_SUBDIRS_ONLY, tr("scan_dialog.subdirs"), tr("scan_dialog.subdirs_desc")),
        ]
        for mode, label, description in options:
            ttk.Button(content, text=label, command=lambda value=mode: self._choose(value)).pack(fill="x", pady=4)
            ttk.Label(content, text=description, wraplength=620, justify="left").pack(anchor="w", padx=(6, 0))

        action_row = ttk.Frame(outer)
        action_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(action_row, textvariable=self._size_notice_var).pack(side="left")
        ttk.Button(action_row, text=tr("scan_dialog.cancel"), command=self._cancel).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update_idletasks()
        width = min(760, max(680, self.winfo_reqwidth()))
        max_height = max(460, self.winfo_screenheight() - 120)
        requested_height = min(max_height, max(520, self.winfo_reqheight()))
        bind_minimum_size_notice(self, self._size_notice_var, 680, 460)
        center_window(self, width, requested_height)

    def _choose(self, mode: str) -> None:
        self.result = mode
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def show_scan_mode_dialog(
    parent: tk.Widget,
    folder: Path,
    ignored_prefixes: list[str],
    ignored_suffixes: list[str] | None = None,
    ignored_contains: list[str] | None = None,
) -> str | None:
    dialog = ScanModeDialog(parent, folder, ignored_prefixes, ignored_suffixes, ignored_contains)
    dialog.wait_window()
    return dialog.result


__all__ = ["SCAN_MODE_ALL", "SCAN_MODE_CURRENT_ONLY", "SCAN_MODE_SUBDIRS_ONLY", "show_scan_mode_dialog"]
