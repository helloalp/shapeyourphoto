from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from window_layout import DEFAULT_DIALOG_MARGIN, bind_minimum_size_notice, center_window, dialog_size_for_parent, prepare_dialog_window


@dataclass(frozen=True)
class DialogSpec:
    title: str
    min_width: int
    min_height: int
    fallback_width: int
    fallback_height: int
    modal: bool = False
    resizable: tuple[bool, bool] = (True, True)
    parent_ratio: float | None = None


def create_dialog_window(parent: tk.Widget, spec: DialogSpec) -> tk.Toplevel:
    dialog = tk.Toplevel(parent)
    prepare_dialog_window(
        dialog,
        parent,
        title=spec.title,
        min_width=spec.min_width,
        min_height=spec.min_height,
        resizable=spec.resizable,
        modal=spec.modal,
    )
    return dialog


def finalize_dialog_window(
    dialog: tk.Toplevel,
    parent: tk.Widget | None,
    spec: DialogSpec,
    *,
    size_notice_var: tk.StringVar | None = None,
) -> tuple[int, int]:
    if parent is not None and spec.parent_ratio is not None:
        width, height = dialog_size_for_parent(
            parent,
            fallback_width=spec.fallback_width,
            fallback_height=spec.fallback_height,
            scale=spec.parent_ratio,
            min_width=spec.min_width,
            min_height=spec.min_height,
        )
    else:
        width, height = spec.fallback_width, spec.fallback_height
    actual = center_window(dialog, width, height, DEFAULT_DIALOG_MARGIN, parent=parent, max_parent_ratio=spec.parent_ratio)
    if size_notice_var is not None:
        bind_minimum_size_notice(dialog, size_notice_var, spec.min_width, spec.min_height)
    try:
        dialog.deiconify()
        dialog.lift(parent.winfo_toplevel() if parent is not None else None)
        dialog.focus_set()
    except Exception:
        pass
    return actual


def make_dialog_footer(parent: tk.Widget, *, row: int, columnspan: int = 1, pady: tuple[int, int] = (14, 0)) -> ttk.Frame:
    footer = ttk.Frame(parent)
    footer.grid(row=row, column=0, columnspan=columnspan, sticky="ew", pady=pady)
    footer.columnconfigure(0, weight=1)
    return footer
