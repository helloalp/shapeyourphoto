from __future__ import annotations

import argparse
import json
import os
import platform
import queue
import shutil
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from app_metadata import APP_VERSION, APP_VERSION_ID
from cloud_security import path_within, sha256_file
from task_state import TaskManager, TaskRecord, TaskStateMachine, TaskStatus
from update_policy import evaluate_update_lag
from ui.language import DEFAULT_LANGUAGE, set_current_language, tr, trf


DOWNLOAD_TIMEOUT = 30
DOWNLOAD_RETRIES = 3
DOWNLOAD_CHUNK_SIZE = 64 * 1024
ROLLBACK_TIMEOUT_SECONDS = 30
USER_AGENT = f"ShapeYourPhotoUpdater/{APP_VERSION} (version_id={APP_VERSION_ID}; {platform.system() or 'Unknown'})"

PROTECTED_TOP_LEVEL = {
    ".git",
    ".github",
    "benchmark_reports",
    "data",
    "private",
    "test",
    "tmp",
    "_cleanup_candidates",
    "_repair",
    "_repair_canceled_outputs",
    "_repair_cancel_backups",
    "_update_removed_files",
}


def _manifest_external_download_only(manifest: dict) -> bool:
    return bool(
        manifest.get("external_download_only")
        or manifest.get("disable_in_app_update")
        or manifest.get("manual_download_only")
    )


@dataclass
class UpdateContext:
    manifest: dict
    app_dir: Path
    restart_cmd: list[str]
    log: queue.SimpleQueue[str] = field(default_factory=queue.SimpleQueue)
    cancel_requested: threading.Event = field(default_factory=threading.Event)
    backups: list[tuple[Path, Path]] = field(default_factory=list)
    quarantine_root: Path | None = None
    deferred_replacements: list[tuple[Path, Path]] = field(default_factory=list)
    deferred_deletions: list[Path] = field(default_factory=list)
    stager_path: Path | None = None
    task_record: TaskRecord | None = None

    def emit(self, message: str) -> None:
        self.log.put(message)


def _read_url_to_file(url: str, target: Path, ctx: UpdateContext) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"", "file"}:
        source = Path(urllib.request.url2pathname(parsed.path if parsed.scheme == "file" else url))
        if ctx.cancel_requested.is_set():
            raise RuntimeError("用户已取消更新")
        with source.open("rb") as src, target.open("wb") as dst:
            while True:
                chunk = src.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                dst.write(chunk)
                if ctx.cancel_requested.is_set():
                    raise RuntimeError("用户已取消更新")
        return
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        if ctx.cancel_requested.is_set():
            raise RuntimeError("用户已取消更新")
        if attempt > 1:
            ctx.emit(trf("updater.status.download_retry", attempt=attempt, total=DOWNLOAD_RETRIES))
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response, target.open("wb") as handle:
                total = int(response.headers.get("Content-Length") or 0)
                copied = 0
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    copied += len(chunk)
                    if total:
                        ctx.emit(trf("updater.status.download_progress", copied=copied, total=total))
                    if ctx.cancel_requested.is_set():
                        raise RuntimeError("用户已取消更新")
            return
        except Exception as exc:
            last_error = exc
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
            if ctx.cancel_requested.is_set():
                raise RuntimeError("用户已取消更新")
            if attempt < DOWNLOAD_RETRIES:
                ctx.emit(tr("updater.status.download_interrupted"))
                time.sleep(0.5 * attempt)
    raise RuntimeError(f"下载更新包失败：{last_error}")


def _safe_zip_extract(zip_path: Path, target_dir: Path, ctx: UpdateContext) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if ctx.cancel_requested.is_set():
                raise RuntimeError("用户已取消更新")
            name = member.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            parts = [part for part in Path(name).parts if part not in {"", "."}]
            if len(parts) > 1 and parts[0].lower().startswith("shapeyourphoto"):
                relative = Path(*parts[1:])
            else:
                relative = Path(*parts)
            if any(part == ".." for part in relative.parts):
                raise RuntimeError(f"更新包包含异常路径：{name}")
            destination = target_dir / relative
            if not path_within(target_dir, destination):
                raise RuntimeError(f"更新包包含异常路径：{name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, destination.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 256)
                    if not chunk:
                        break
                    dst.write(chunk)
                    if ctx.cancel_requested.is_set():
                        raise RuntimeError("用户已取消更新")
    ctx.emit(tr("updater.status.archive_ready"))


def _manifest_paths(manifest: dict, *keys: str) -> list[Path]:
    raw = None
    for key in keys:
        if manifest.get(key):
            raw = manifest.get(key)
            break
    if raw is None:
        raw = []
    if isinstance(raw, dict):
        raw = raw.keys()
    paths: list[Path] = []
    for item in raw:
        path = Path(str(item).replace("\\", "/"))
        if path.parts and path.parts[0] not in PROTECTED_TOP_LEVEL and ".." not in path.parts:
            paths.append(path)
    return paths


def _managed_paths(manifest: dict) -> list[Path]:
    return _manifest_paths(manifest, "managed_files", "files")


def _deleted_paths(manifest: dict) -> list[Path]:
    return _manifest_paths(manifest, "deleted_paths", "delete", "cleanup_paths")


def _deferred_deleted_paths(manifest: dict) -> list[Path]:
    return _manifest_paths(manifest, "deferred_deleted_paths", "delete_after_restart")


def _move_specs(manifest: dict) -> list[tuple[Path, Path]]:
    raw = manifest.get("moved_paths") or manifest.get("move_paths") or []
    if isinstance(raw, dict):
        raw = [{"from": source, "to": target} for source, target in raw.items()]
    specs: list[tuple[Path, Path]] = []
    for item in raw:
        source = target = None
        if isinstance(item, dict):
            source = item.get("from") or item.get("source")
            target = item.get("to") or item.get("target")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            source, target = item
        if not source or not target:
            continue
        source_path = Path(str(source).replace("\\", "/"))
        target_path = Path(str(target).replace("\\", "/"))
        if (
            source_path.parts
            and target_path.parts
            and source_path.parts[0] not in PROTECTED_TOP_LEVEL
            and target_path.parts[0] not in PROTECTED_TOP_LEVEL
            and ".." not in source_path.parts
            and ".." not in target_path.parts
        ):
            specs.append((source_path, target_path))
    return specs


def _backup_path(ctx: UpdateContext, relative: Path, backup_root: Path) -> None:
    source = ctx.app_dir / relative
    if not source.exists():
        return
    if not path_within(ctx.app_dir, source):
        raise RuntimeError(f"备份路径超出应用目录：{relative}")
    backup = backup_root / relative
    backup.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, backup, dirs_exist_ok=True)
    else:
        shutil.copy2(source, backup)
    ctx.backups.append((relative, backup))


def _restore_backups(ctx: UpdateContext, *, timeout_seconds: int = ROLLBACK_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout_seconds
    for relative, backup in reversed(ctx.backups):
        if time.monotonic() > deadline:
            raise TimeoutError("恢复更新前状态超时")
        target = ctx.app_dir / relative
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        if backup.is_dir():
            shutil.copytree(backup, target, dirs_exist_ok=True)
        else:
            shutil.copy2(backup, target)


def _is_deferred_replacement(relative: Path) -> bool:
    normalized = relative.as_posix().casefold()
    return normalized in {"src/updater.py", "updater.py"} or normalized.endswith("/updater.exe")


def _is_deferred_deletion(relative: Path) -> bool:
    normalized = relative.as_posix().casefold()
    return normalized in {"src/updater.py", "updater.py"} or normalized.endswith("/updater.exe")


def _replace_files(ctx: UpdateContext, extracted_root: Path, backup_root: Path) -> None:
    managed = _managed_paths(ctx.manifest)
    if not managed:
        managed = [path.relative_to(extracted_root) for path in extracted_root.rglob("*") if path.is_file()]
    for relative in managed:
        if ctx.cancel_requested.is_set():
            raise RuntimeError("用户已取消更新")
        source = extracted_root / relative
        target = ctx.app_dir / relative
        if not source.exists() or not source.is_file():
            ctx.emit(trf("updater.status.file_skipped", path=relative))
            continue
        if not path_within(ctx.app_dir, target):
            raise RuntimeError(f"写入路径超出应用目录：{relative}")
        _backup_path(ctx, relative, backup_root)
        if _is_deferred_replacement(relative):
            ctx.deferred_replacements.append((relative, source))
            ctx.emit(trf("updater.status.deferred", path=relative))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        ctx.emit(trf("updater.status.file_updated", path=relative))


def _apply_moves(ctx: UpdateContext, backup_root: Path) -> None:
    for source_relative, target_relative in _move_specs(ctx.manifest):
        if ctx.cancel_requested.is_set():
            raise RuntimeError("update cancelled")
        source = ctx.app_dir / source_relative
        target = ctx.app_dir / target_relative
        if not source.exists():
            continue
        if target.exists():
            ctx.emit(trf("updater.status.preserved", path=target_relative))
            continue
        if not path_within(ctx.app_dir, source) or not path_within(ctx.app_dir, target):
            raise RuntimeError(f"move path escapes app dir: {source_relative} -> {target_relative}")
        _backup_path(ctx, source_relative, backup_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        ctx.emit(trf("updater.status.file_updated", path=target_relative))


def _quarantine_deleted(ctx: UpdateContext) -> None:
    deleted = _deleted_paths(ctx.manifest)
    deferred = _deferred_deleted_paths(ctx.manifest)
    if not deleted:
        deleted = []
    root = ctx.app_dir / "data" / "update_quarantine" / time.strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=True)
    ctx.quarantine_root = root
    for relative in [*deleted, *deferred]:
        if ctx.cancel_requested.is_set():
            raise RuntimeError("用户已取消更新")
        target = ctx.app_dir / relative
        if not target.exists():
            continue
        if not path_within(ctx.app_dir, target):
            raise RuntimeError(f"移出路径超出应用目录：{relative}")
        if target.parts and relative.parts[0] in PROTECTED_TOP_LEVEL:
            ctx.emit(trf("updater.status.preserved", path=relative))
            continue
        if relative in deferred or _is_deferred_deletion(relative):
            ctx.deferred_deletions.append(relative)
            ctx.emit(trf("updater.status.deferred", path=relative))
            continue
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(destination))
        ctx.emit(trf("updater.status.file_updated", path=relative))


def _post_update_required_files(ctx: UpdateContext) -> None:
    required = _manifest_paths(ctx.manifest, "post_update_required_files", "required_files")
    pending = {relative.as_posix() for relative, _source in ctx.deferred_replacements}
    missing = []
    for relative in required:
        target = ctx.app_dir / relative
        if not target.exists() and relative.as_posix() not in pending:
            missing.append(relative.as_posix())
    if missing:
        raise RuntimeError("post-update required files are missing: " + ", ".join(missing))


def _write_stager(ctx: UpdateContext, tmp_dir: Path) -> Path | None:
    if not ctx.deferred_replacements and not ctx.deferred_deletions:
        return None
    stager = tmp_dir / "apply_deferred_update.py"
    payload = {
        "app_dir": str(ctx.app_dir),
        "pid": os.getpid(),
        "restart_cmd": ctx.restart_cmd,
        "quarantine_root": str(
            ctx.quarantine_root
            or (ctx.app_dir / "data" / "update_quarantine" / time.strftime("%Y%m%d-%H%M%S"))
        ),
        "files": [
            {"relative": relative.as_posix(), "source": str(source)}
            for relative, source in ctx.deferred_replacements
        ],
        "delete_paths": [relative.as_posix() for relative in ctx.deferred_deletions],
    }
    stager.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import json, os, shutil, subprocess, sys, time",
                f"payload = json.loads({json.dumps(json.dumps(payload, ensure_ascii=False))})",
                "deadline = time.time() + 30",
                "pid = int(payload['pid'])",
                "if os.name == 'nt':",
                "    import ctypes",
                "    kernel32 = ctypes.windll.kernel32",
                "    SYNCHRONIZE = 0x00100000",
                "    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)",
                "    if handle:",
                "        kernel32.WaitForSingleObject(handle, 30000)",
                "        kernel32.CloseHandle(handle)",
                "else:",
                "    while time.time() < deadline:",
                "        try:",
                "            os.kill(pid, 0)",
                "        except OSError:",
                "            break",
                "        time.sleep(0.25)",
                "app_dir = payload['app_dir']",
                "app_root = os.path.abspath(app_dir)",
                "for item in payload['files']:",
                "    target = os.path.abspath(os.path.join(app_root, item['relative']))",
                "    if target != app_root and not target.startswith(app_root + os.sep):",
                "        raise SystemExit(f'bad target: {target}')",
                "    os.makedirs(os.path.dirname(target), exist_ok=True)",
                "    shutil.copy2(item['source'], target)",
                "quarantine_root = os.path.abspath(payload['quarantine_root'])",
                "if not quarantine_root.startswith(app_root + os.sep):",
                "    raise SystemExit(f'bad quarantine root: {quarantine_root}')",
                "for relative in payload.get('delete_paths', []):",
                "    target = os.path.abspath(os.path.join(app_root, relative))",
                "    if target == app_root or not target.startswith(app_root + os.sep):",
                "        raise SystemExit(f'bad delete target: {target}')",
                "    if not os.path.exists(target):",
                "        continue",
                "    destination = os.path.abspath(os.path.join(quarantine_root, relative))",
                "    os.makedirs(os.path.dirname(destination), exist_ok=True)",
                "    if os.path.exists(destination):",
                "        destination = destination + '.' + str(int(time.time()))",
                "    shutil.move(target, destination)",
                "subprocess.Popen(payload['restart_cmd'], cwd=app_dir, close_fds=True)",
            ]
        ),
        encoding="utf-8",
    )
    return stager


def run_update(ctx: UpdateContext) -> None:
    package_url = str(ctx.manifest.get("package_url") or ctx.manifest.get("url") or "")
    expected_hash = str(ctx.manifest.get("sha256") or "").lower()
    expected_size = int(ctx.manifest.get("package_size") or 0)
    if not package_url or not expected_hash:
        raise RuntimeError("更新信息缺少下载地址或校验值")
    work_parent = ctx.app_dir / "tmp" / "update_work"
    work_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = work_parent / f"syp-update-{secrets.token_hex(8)}"
    tmp_dir.mkdir(parents=True, exist_ok=False)
    success = False
    try:
        package_path = tmp_dir / "package.zip"
        extract_dir = tmp_dir / "extract"
        backup_root = tmp_dir / "backup"
        extract_dir.mkdir()
        backup_root.mkdir()
        ctx.emit(tr("updater.status.download_start"))
        _read_url_to_file(package_url, package_path, ctx)
        if ctx.cancel_requested.is_set():
            raise RuntimeError("用户已取消更新")
        actual_hash = sha256_file(package_path)
        actual_size = package_path.stat().st_size
        if expected_size and actual_size != expected_size:
            if actual_hash.lower() != expected_hash:
                raise RuntimeError(
                    "更新包大小校验失败："
                    f"expected={expected_size}, actual={actual_size}, url={package_url}"
                )
        if actual_hash.lower() != expected_hash:
            raise RuntimeError(
                "更新包 sha256 校验失败："
                f"expected={expected_hash}, actual={actual_hash}, size={actual_size}, url={package_url}"
            )
        ctx.emit(tr("updater.status.verify_ok"))
        _safe_zip_extract(package_path, extract_dir, ctx)
        if ctx.cancel_requested.is_set():
            raise RuntimeError("用户已取消更新")
        _replace_files(ctx, extract_dir, backup_root)
        _apply_moves(ctx, backup_root)
        _quarantine_deleted(ctx)
        _post_update_required_files(ctx)
        ctx.stager_path = _write_stager(ctx, tmp_dir)
        success = True
    finally:
        if success and not ctx.deferred_replacements and not ctx.deferred_deletions:
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                ctx.emit(tr("updater.status.deferred"))
        elif success:
            ctx.emit(tr("updater.status.deferred"))
        else:
            ctx.emit(tr("updater.status.deferred"))
    ctx.emit(tr("updater.status.complete"))


class UpdaterWindow(tk.Tk):
    def __init__(self, ctx: UpdateContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.title(tr("updater.title"))
        self.geometry("720x460")
        self.minsize(620, 380)
        self.protocol("WM_DELETE_WINDOW", self._cancel_and_close)
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(outer, text=tr("updater.heading"), font=("Microsoft YaHei UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.text = tk.Text(outer, wrap="word", height=14, padx=10, pady=10)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=1, column=0, sticky="nsew", pady=(12, 10))
        scroll.grid(row=1, column=1, sticky="ns", pady=(12, 10))
        self.button = ttk.Button(outer, text=tr("updater.cancel_close"), command=self._cancel_and_close)
        self.button.grid(row=2, column=0, sticky="e")
        self._ui_queue: queue.SimpleQueue[object] = queue.SimpleQueue()
        self._task_manager = TaskManager(
            ui_dispatch=lambda callback: self._ui_queue.put(callback),
            error_callback=self.ctx.emit,
            max_workers=1,
        )
        self.ctx.task_record = TaskRecord(
            task_id=int(time.time() * 1000),
            run_id=f"update-{int(time.time() * 1000)}",
            kind="update",
            name="ShapeYourPhoto update",
            total=1,
            cancel_event=self.ctx.cancel_requested,
        )
        TaskStateMachine(self.ctx.task_record).transition(TaskStatus.RUNNING)
        self.after(100, self._drain_log)
        self._task_manager.submit_worker(task_id=None, target=self._worker)

    def _dispatch_ui(self, callback) -> None:
        self._ui_queue.put(callback)

    def _drain_log(self) -> None:
        while True:
            try:
                message = self.ctx.log.get_nowait()
            except queue.Empty:
                break
            self.text.insert("end", message + "\n")
            self.text.see("end")
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            callback()
        try:
            exists = bool(self.winfo_exists())
        except tk.TclError:
            return
        if exists:
            self.after(100, self._drain_log)

    def _cancel_and_close(self) -> None:
        self.ctx.cancel_requested.set()
        if self.ctx.task_record is not None and self.ctx.task_record.status == TaskStatus.RUNNING:
            TaskStateMachine(self.ctx.task_record).transition(TaskStatus.CANCEL_REQUESTED)
        self.ctx.emit(tr("updater.status.cancelling"))
        self.destroy()

    def _worker(self) -> None:
        try:
            run_update(self.ctx)
            if self.ctx.task_record is not None and self.ctx.task_record.is_active:
                TaskStateMachine(self.ctx.task_record).transition(TaskStatus.COMPLETED)
            if self.ctx.stager_path is not None:
                self.ctx.emit(tr("updater.status.finishing"))
                subprocess.Popen(
                    [sys.executable, str(self.ctx.stager_path)],
                    cwd=str(self.ctx.app_dir),
                    close_fds=True,
                )
                self._dispatch_ui(lambda: self.after(500, self.destroy))
            else:
                self.ctx.emit(tr("updater.status.restarting"))
                subprocess.Popen(self.ctx.restart_cmd, cwd=str(self.ctx.app_dir), close_fds=True)
                self._dispatch_ui(lambda: self.after(700, self.destroy))
        except Exception as exc:
            self.ctx.emit(tr("updater.status.failed"))
            try:
                _restore_backups(self.ctx)
                self.ctx.emit(tr("updater.status.restored"))
            except Exception as rollback_exc:
                self.ctx.emit(tr("updater.status.restore_failed"))
                if self.ctx.task_record is not None and self.ctx.task_record.is_active:
                    TaskStateMachine(self.ctx.task_record).transition(TaskStatus.FAILED, error=str(rollback_exc))
                self._dispatch_ui(self._enable_close)
                self._dispatch_ui(
                    lambda: messagebox.showerror(
                        tr("updater.rollback_failed_title"),
                        tr("updater.rollback_failed_body"),
                        parent=self,
                    ),
                )
                return
            if self.ctx.cancel_requested.is_set():
                if self.ctx.task_record is not None and self.ctx.task_record.is_active:
                    if self.ctx.task_record.status == TaskStatus.CANCEL_REQUESTED:
                        TaskStateMachine(self.ctx.task_record).transition(TaskStatus.CANCELING)
                    TaskStateMachine(self.ctx.task_record).transition(TaskStatus.CANCELED)
                self._dispatch_ui(self._finish_cancelled)
            else:
                if self.ctx.task_record is not None and self.ctx.task_record.is_active:
                    TaskStateMachine(self.ctx.task_record).transition(TaskStatus.FAILED, error=str(exc))
                self._dispatch_ui(lambda err=exc: self._finish_failed(err))

    def _finish_cancelled(self) -> None:
        messagebox.showinfo(tr("updater.cancelled_title"), tr("updater.cancelled_body"), parent=self)
        self.destroy()

    def _finish_failed(self, exc: Exception) -> None:
        self._enable_close()
        messagebox.showerror(tr("updater.failed_title"), tr("updater.failed_body"), parent=self)

    def _enable_close(self) -> None:
        self.button.configure(text=tr("updater.close"), state="normal", command=self.destroy)
        self.protocol("WM_DELETE_WINDOW", self.destroy)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-cache", required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--restart-cmd", required=True)
    parser.add_argument("--expected-version-id", default="0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from app_settings import load_app_settings

        set_current_language(load_app_settings(create_if_missing=False).language)
    except Exception:
        set_current_language(DEFAULT_LANGUAGE)
    manifest = json.loads(Path(args.manifest_cache).read_text(encoding="utf-8"))
    lag_decision = evaluate_update_lag(manifest)
    if lag_decision is not None and lag_decision.blocks_in_app_update:
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(
            tr("update.blocked_title"),
            tr("update.blocked_body"),
        )
        root.destroy()
        return 0
    if _manifest_external_download_only(manifest):
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            tr("updater.manual_title"),
            tr("updater.manual_body"),
            parent=root,
        )
        root.destroy()
        return
    restart_cmd = json.loads(args.restart_cmd)
    ctx = UpdateContext(manifest=manifest, app_dir=Path(args.app_dir).resolve(), restart_cmd=restart_cmd)
    app = UpdaterWindow(ctx)
    app.mainloop()


if __name__ == "__main__":
    main()
