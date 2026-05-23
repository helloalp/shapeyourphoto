from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Any, Callable

from ui.window_titles import app_window_title
from ui.language import tr, trf
from window_layout import center_window
from update_policy import (
    OFFICIAL_SITE_URL,
    RULE_BLOCK_IN_APP_UPDATE,
    UpdateLagDecision,
    evaluate_update_lag,
    remember_update_policy_ack,
)


def _activate_modal(dialog: tk.Toplevel, parent: tk.Widget, *, grab: bool = True) -> None:
    dialog.update_idletasks()
    dialog.deiconify()
    dialog.lift(parent.winfo_toplevel())
    try:
        dialog.attributes("-topmost", True)

        def _clear_topmost() -> None:
            try:
                if dialog.winfo_exists():
                    dialog.attributes("-topmost", False)
            except tk.TclError:
                pass

        dialog.after(250, _clear_topmost)
    except tk.TclError:
        pass
    try:
        dialog.wait_visibility()
    except tk.TclError:
        pass
    if grab:
        dialog.grab_set()
    dialog.focus_force()


def update_manifest_external_download_only(manifest: dict[str, Any]) -> bool:
    return bool(
        manifest.get("external_download_only")
        or manifest.get("disable_in_app_update")
        or manifest.get("manual_download_only")
    )


def _notes_text(manifest: dict[str, Any]) -> str:
    notes = manifest.get("release_notes", "")
    if isinstance(notes, list):
        return "\n\n".join(str(item) for item in notes)
    return str(notes or tr("update.no_notes"))


def _lag_message(decision: UpdateLagDecision) -> str:
    return trf(
        "update.lag_notice",
        count=decision.count,
        version=decision.latest_version,
        date=decision.published_at or tr("update.unknown_date"),
    )


class UpdateAvailableDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, manifest: dict[str, Any], *, manual: bool = False) -> None:
        super().__init__(parent)
        self.result = "later"
        self.title(app_window_title(tr("update.available_title")))
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.minsize(620, 430)
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish("later"))
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
        self.lag_decision = evaluate_update_lag(manifest)
        notes.insert("1.0", _lag_message(self.lag_decision) if self.lag_decision is not None else _notes_text(manifest))
        notes.config(state="disabled")

        external_download_only = update_manifest_external_download_only(manifest) or bool(
            self.lag_decision is not None and self.lag_decision.blocks_in_app_update
        )
        recommendation = tr("update.external_recommendation") if external_download_only else tr("update.recommendation")
        ttk.Label(outer, text=recommendation, font=("Microsoft YaHei UI", 10, "bold")).grid(row=2, column=0, sticky="w")

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(1, weight=1)
        left_text = tr("update.decline")
        ttk.Button(actions, text=left_text, command=lambda: self._finish("decline")).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text=tr("update.later"), command=lambda: self._finish("later")).grid(row=0, column=1)
        if external_download_only:
            ttk.Button(actions, text=tr("update.acknowledge"), command=lambda: self._finish("decline")).grid(row=0, column=2, sticky="e")
        else:
            ttk.Button(actions, text=tr("update.install"), command=lambda: self._finish("update")).grid(row=0, column=2, sticky="e")
        if self.lag_decision is not None:
            ttk.Button(actions, text=tr("update.official_site"), command=self._open_official_site).grid(row=0, column=3, sticky="e", padx=(8, 0))
        center_window(self, 700, 520)
        _activate_modal(self, parent)

    def _finish(self, result: str) -> None:
        if result == "decline" and self.lag_decision is not None and self.lag_decision.rule == RULE_BLOCK_IN_APP_UPDATE:
            remember_update_policy_ack(self.lag_decision)
        self.result = result
        self.destroy()

    def _open_official_site(self) -> None:
        try:
            webbrowser.open(OFFICIAL_SITE_URL)
        except Exception:
            pass
        self._finish("official_site")


def show_update_available_dialog(parent: tk.Widget, manifest: dict[str, Any], *, manual: bool = False) -> str:
    dialog = UpdateAvailableDialog(parent, manifest, manual=manual)
    dialog.wait_window()
    return dialog.result


class CheckingUpdateDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title(app_window_title(tr("update.checking_title")))
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=tr("update.checking_body"), font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        bar = ttk.Progressbar(outer, mode="indeterminate", length=260)
        bar.pack(fill="x", pady=(14, 0))
        bar.start(12)
        center_window(self, 360, 150)
        _activate_modal(self, parent, grab=False)


class CloudMessageDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        message: dict[str, Any],
        *,
        update_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(app_window_title(str(message.get("title") or tr("announcement.title"))))
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.minsize(560, 360)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._remaining = int(message.get("countdown_seconds") or 0) if message.get("countdown_enabled") else 0
        self._confirm_var = tk.StringVar(value=tr("announcement.confirm"))
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(outer, text=str(message.get("title") or tr("announcement.default_title")), font=("Microsoft YaHei UI", 13, "bold")).grid(row=0, column=0, sticky="w")
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
            ttk.Button(actions, text=tr("update.install"), command=lambda: self._start_update(update_callback)).grid(row=0, column=1, padx=(0, 8))
        self.confirm_button = ttk.Button(actions, textvariable=self._confirm_var, command=self.destroy)
        self.confirm_button.grid(row=0, column=2)
        if self._remaining > 0:
            self.confirm_button.configure(state="disabled")
            self._tick()
        center_window(self, 650, 460)
        _activate_modal(self, parent)

    def _start_update(self, update_callback: Callable[[], None]) -> None:
        self.destroy()
        update_callback()

    def _tick(self) -> None:
        if self._remaining <= 0:
            self._confirm_var.set(tr("announcement.confirm"))
            self.confirm_button.configure(state="normal")
            return
        self._confirm_var.set(trf("announcement.confirm_countdown", seconds=self._remaining))
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
