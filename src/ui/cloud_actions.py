from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

from app_metadata import APP_BUILD_ID, APP_VERSION_ID
from cloud_client import compare_builds, fetch_cloud_messages, fetch_update_manifest
from cloud_state import has_seen_message, remember_message, set_temporary_decline, should_suppress_update_prompt
from integrity_guard import check_cloud_update_modules
from paths import user_data_dir
from ui.language import tr, trf
from ui.cloud_dialogs import (
    CheckingUpdateDialog,
    show_cloud_message_dialog,
    show_update_available_dialog,
    update_manifest_external_download_only,
)
from update_policy import evaluate_update_lag, has_acknowledged_update_policy


class UiCloudActionsMixin:
    def _run_startup_cloud_checks(self) -> None:
        report = check_cloud_update_modules()
        for message in report.messages:
            self._log_console(f"cloud integrity: {message}")
        if not report.ok:
            messagebox.showerror(
                tr("update.integrity_title"),
                tr("update.integrity_body"),
                parent=self.root,
            )
            return
        if getattr(self.settings, "auto_check_updates", True):
            self._check_updates_async(manual=False, after_done=self._check_cloud_messages_async)
        else:
            self._check_cloud_messages_async()

    def check_updates_now(self, parent=None) -> None:
        owner = parent or self.root
        progress = CheckingUpdateDialog(owner)

        def _finish(callback) -> None:
            def _wrapped() -> None:
                try:
                    if progress.winfo_exists():
                        progress.destroy()
                except Exception:
                    pass
                callback()

            self._dispatch_ui(_wrapped)

        def _worker() -> None:
            result = fetch_update_manifest("")
            if not result.ok or result.payload is None:
                _finish(
                    lambda message=result.user_message or tr("update.service_unavailable"): messagebox.showwarning(
                        tr("update.check_failed_title"),
                        message,
                        parent=owner,
                    )
                )
                self._log_console(f"manual update check failed: {result.error}")
                return
            _finish(lambda: self._handle_update_manifest(result.payload, manual=True, parent=owner))

        self.task_manager.submit(kind="update_check", name="manual_update_check", target=lambda _record: _worker(), exclusive=False)

    def _check_updates_async(self, *, manual: bool, after_done=None) -> None:
        def _worker() -> None:
            result = fetch_update_manifest("")
            if not result.ok or result.payload is None:
                self._log_console(f"auto update check skipped: {result.error}")
                if after_done is not None:
                    self._dispatch_ui(after_done)
                return

            def _finish() -> None:
                outcome = self._handle_update_manifest(result.payload, manual=manual)
                if after_done is not None and outcome != "update":
                    after_done()

            self._dispatch_ui(_finish)

        self.task_manager.submit(kind="update_check", name="auto_update_check", target=lambda _record: _worker(), exclusive=False)

    def _handle_update_manifest(self, manifest: dict, *, manual: bool, parent=None) -> str:
        owner = parent or self.root
        if compare_builds(manifest) <= 0:
            if manual:
                messagebox.showinfo(tr("update.checking_title"), tr("update.current"), parent=owner)
            return "current"
        remote_id = int(manifest.get("version_id") or manifest.get("build_id") or 0)
        lag_decision = evaluate_update_lag(manifest)
        if lag_decision is not None and lag_decision.blocks_in_app_update and not manual and has_acknowledged_update_policy(lag_decision):
            self._log_console(f"update blocked prompt suppressed: current={APP_VERSION_ID} latest={lag_decision.latest_version_id}")
            return "blocked_ack"
        if not manual and should_suppress_update_prompt(remote_id):
            self._log_console(trf("update.suppressed_log", version=remote_id))
            return "suppressed"
        result = show_update_available_dialog(owner, manifest, manual=manual)
        if result == "decline":
            if not manual:
                set_temporary_decline(remote_id)
            else:
                set_temporary_decline(remote_id)
            return result
        if result == "update":
            if lag_decision is not None and lag_decision.blocks_in_app_update:
                self._log_console(f"in-app updater blocked: current={APP_VERSION_ID} latest={lag_decision.latest_version_id}")
                messagebox.showwarning(tr("update.blocked_title"), tr("update.blocked_body"), parent=owner)
                return "blocked"
            if update_manifest_external_download_only(manifest):
                self._log_console("update manifest requires external download; updater launch skipped")
                return "external"
            self._launch_updater(manifest)
            return result
        return result

    def _launch_updater(self, manifest: dict) -> None:
        pending = user_data_dir() / "pending_update_manifest.json"
        pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        app_dir = Path(__file__).resolve().parents[2]
        restart_cmd = [sys.executable, str(app_dir / "tools" / "entry" / "app.py")]
        updater_entry = app_dir / "src" / "updater_bootstrap.py"
        if not updater_entry.exists():
            updater_entry = app_dir / "src" / "updater.py"
        cmd = [
            sys.executable,
            str(updater_entry),
            "--manifest-cache",
            str(pending),
            "--app-dir",
            str(app_dir),
            "--restart-cmd",
            json.dumps(restart_cmd),
            "--expected-version-id",
            str(max(APP_VERSION_ID, APP_BUILD_ID)),
        ]
        try:
            subprocess.Popen(cmd, cwd=str(app_dir), close_fds=True)
        except Exception as exc:
            messagebox.showerror(tr("update.launch_failed_title"), tr("update.launch_failed_body"), parent=self.root)
            self._log_console(f"updater launch failed: {exc}")
            return
        self._log_console("updater launched; closing main application")
        self._begin_close_sequence()

    def _check_cloud_messages_async(self) -> None:
        def _worker() -> None:
            result = fetch_cloud_messages("")
            if not result.ok or result.payload is None:
                self._log_console(f"cloud message check skipped: {result.error}")
                return
            self._dispatch_ui(lambda: self._handle_cloud_messages(result.payload))

        self.task_manager.submit(kind="update_check", name="cloud_message_check", target=lambda _record: _worker(), exclusive=False)

    def _handle_cloud_messages(self, payload: dict) -> None:
        messages = payload.get("messages", [])
        if isinstance(messages, dict):
            messages = [messages]
        if not isinstance(messages, list):
            return
        local_id = max(APP_VERSION_ID, APP_BUILD_ID)
        for message in messages:
            if not isinstance(message, dict) or not message.get("enabled", True):
                continue
            min_id = int(message.get("min_version_id") or 0)
            max_id = int(message.get("max_version_id") or 999999)
            if not (min_id <= local_id <= max_id):
                continue
            message_id = str(message.get("id") or "")
            if not message_id:
                continue
            if has_seen_message(message_id):
                continue
            remember_message(message_id)
            show_cloud_message_dialog(self.root, message, update_callback=self.check_updates_now)
            break
