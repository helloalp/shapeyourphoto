from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import messagebox

from app_metadata import APP_BUILD_ID, APP_VERSION_ID
from cloud_client import compare_builds, fetch_cloud_messages, fetch_update_manifest
from cloud_state import remember_message, set_temporary_decline, should_suppress_update_prompt
from integrity_guard import check_cloud_update_modules
from paths import user_data_dir
from ui.cloud_dialogs import CheckingUpdateDialog, show_cloud_message_dialog, show_update_available_dialog


class UiCloudActionsMixin:
    def _run_startup_cloud_checks(self) -> None:
        report = check_cloud_update_modules()
        for message in report.messages:
            self._log_console(f"cloud integrity: {message}")
        if not report.ok:
            messagebox.showerror(
                "更新/公告模块异常",
                "ShapeYourPhoto 的更新或公告模块缺失/被篡改。\n\n"
                + "\n".join(report.messages)
                + "\n\n请恢复完整发布包后重新启动。",
                parent=self.root,
            )
            return
        self._check_cloud_messages_async()
        if getattr(self.settings, "auto_check_updates", True):
            self._check_updates_async(manual=False)

    def check_updates_now(self) -> None:
        progress = CheckingUpdateDialog(self.root)

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
                _finish(lambda: messagebox.showwarning("检查更新失败", result.error or "无法读取更新信息。", parent=self.root))
                self._log_console(f"manual update check failed: {result.error}")
                return
            _finish(lambda: self._handle_update_manifest(result.payload, manual=True))

        threading.Thread(target=_worker, daemon=True).start()

    def _check_updates_async(self, *, manual: bool) -> None:
        def _worker() -> None:
            result = fetch_update_manifest("")
            if not result.ok or result.payload is None:
                self._log_console(f"auto update check skipped: {result.error}")
                return
            self._dispatch_ui(lambda: self._handle_update_manifest(result.payload, manual=manual))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_update_manifest(self, manifest: dict, *, manual: bool) -> None:
        if compare_builds(manifest) <= 0:
            if manual:
                messagebox.showinfo("检查更新", "当前已经是最新版本。", parent=self.root)
            return
        remote_id = int(manifest.get("version_id") or manifest.get("build_id") or 0)
        if not manual and should_suppress_update_prompt(remote_id):
            self._log_console(f"update available but prompt suppressed for version_id={remote_id}")
            return
        result = show_update_available_dialog(self.root, manifest, manual=manual)
        if result == "decline":
            if not manual:
                set_temporary_decline(remote_id)
            else:
                set_temporary_decline(remote_id)
            return
        if result == "update":
            self._launch_updater(manifest)

    def _launch_updater(self, manifest: dict) -> None:
        pending = user_data_dir() / "pending_update_manifest.json"
        pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        app_dir = Path(__file__).resolve().parents[1]
        restart_cmd = [sys.executable, str(app_dir / "app.py")]
        cmd = [
            sys.executable,
            str(app_dir / "updater.py"),
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
            messagebox.showerror("启动更新器失败", f"无法启动独立更新器：\n{exc}", parent=self.root)
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

        threading.Thread(target=_worker, daemon=True).start()

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
            show_cloud_message_dialog(self.root, message, update_callback=self.check_updates_now)
            remember_message(message_id)
            break
