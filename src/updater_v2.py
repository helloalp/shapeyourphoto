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


DOWNLOAD_TIMEOUT = 5
ROLLBACK_TIMEOUT_SECONDS = 30
USER_AGENT = f"ShapeYourPhotoUpdater/{APP_VERSION} (version_id={APP_VERSION_ID}; {platform.system() or 'Unknown'})"

PROTECTED_TOP_LEVEL = {
    ".git",
    ".github",
    "benchmark_reports",
    "data",
    "private_docs",
    "test",
    "tmp",
    "_cleanup_candidates",
    "_repair_canceled_outputs",
    "_repair_cancel_backups",
    "_update_removed_files",
}


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
                chunk = src.read(1024 * 256)
                if not chunk:
                    break
                dst.write(chunk)
                if ctx.cancel_requested.is_set():
                    raise RuntimeError("用户已取消更新")
        return
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response, target.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        copied = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            copied += len(chunk)
            if total:
                ctx.emit(f"已下载 {copied}/{total} 字节")
            if ctx.cancel_requested.is_set():
                ctx.emit("已收到取消请求，正在回到可安全退出的状态")
                raise RuntimeError("用户已取消更新")


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
    ctx.emit("更新包已解压并通过路径检查")


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
            ctx.emit(f"更新包缺少文件，已跳过：{relative}")
            continue
        if not path_within(ctx.app_dir, target):
            raise RuntimeError(f"写入路径超出应用目录：{relative}")
        _backup_path(ctx, relative, backup_root)
        if _is_deferred_replacement(relative):
            ctx.deferred_replacements.append((relative, source))
            ctx.emit(f"已准备稍后更新：{relative}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        ctx.emit(f"已更新：{relative}")


def _apply_moves(ctx: UpdateContext, backup_root: Path) -> None:
    for source_relative, target_relative in _move_specs(ctx.manifest):
        if ctx.cancel_requested.is_set():
            raise RuntimeError("update cancelled")
        source = ctx.app_dir / source_relative
        target = ctx.app_dir / target_relative
        if not source.exists():
            continue
        if target.exists():
            ctx.emit(f"move skipped because target exists: {source_relative} -> {target_relative}")
            continue
        if not path_within(ctx.app_dir, source) or not path_within(ctx.app_dir, target):
            raise RuntimeError(f"move path escapes app dir: {source_relative} -> {target_relative}")
        _backup_path(ctx, source_relative, backup_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        ctx.emit(f"moved legacy path: {source_relative} -> {target_relative}")


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
            ctx.emit(f"受保护路径已保留：{relative}")
            continue
        if relative in deferred or _is_deferred_deletion(relative):
            ctx.deferred_deletions.append(relative)
            ctx.emit(f"deferred cleanup prepared: {relative}")
            continue
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(destination))
        ctx.emit(f"已移出旧文件：{relative}")


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
        ctx.emit("正在下载更新包")
        _read_url_to_file(package_url, package_path, ctx)
        if ctx.cancel_requested.is_set():
            raise RuntimeError("用户已取消更新")
        if expected_size and package_path.stat().st_size != expected_size:
            raise RuntimeError("更新包大小校验失败")
        actual_hash = sha256_file(package_path)
        if actual_hash.lower() != expected_hash:
            raise RuntimeError("更新包校验失败")
        ctx.emit("更新包校验通过")
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
            except Exception as exc:
                ctx.emit(f"临时更新文件保留用于检查：{tmp_dir}（{exc}）")
        elif success:
            ctx.emit("部分更新将在当前更新器退出后完成")
        else:
            ctx.emit(f"临时更新文件已保留：{tmp_dir}")
    ctx.emit("更新完成")


class UpdaterWindow(tk.Tk):
    def __init__(self, ctx: UpdateContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.title("ShapeYourPhoto Updater")
        self.geometry("720x460")
        self.minsize(620, 380)
        self.protocol("WM_DELETE_WINDOW", self._confirm_cancel)
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(outer, text="ShapeYourPhoto 正在更新", font=("Microsoft YaHei UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.text = tk.Text(outer, wrap="word", height=14, padx=10, pady=10)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=1, column=0, sticky="nsew", pady=(12, 10))
        scroll.grid(row=1, column=1, sticky="ns", pady=(12, 10))
        self.button = ttk.Button(outer, text="取消更新", command=self._confirm_cancel)
        self.button.grid(row=2, column=0, sticky="e")
        self.after(100, self._drain_log)
        threading.Thread(target=self._worker, daemon=True).start()

    def _drain_log(self) -> None:
        while True:
            try:
                message = self.ctx.log.get_nowait()
            except queue.Empty:
                break
            self.text.insert("end", message + "\n")
            self.text.see("end")
        self.after(100, self._drain_log)

    def _confirm_cancel(self) -> None:
        if messagebox.askyesno("确定取消吗？", "确定取消更新吗？确认前更新进程会继续执行。", parent=self):
            self.ctx.cancel_requested.set()
            self.button.configure(state="disabled")
            self.ctx.emit("正在取消更新，请稍候")

    def _worker(self) -> None:
        try:
            run_update(self.ctx)
            if self.ctx.stager_path is not None:
                self.ctx.emit("正在启动更新收尾程序")
                subprocess.Popen(
                    [sys.executable, str(self.ctx.stager_path)],
                    cwd=str(self.ctx.app_dir),
                    close_fds=True,
                )
                self.after(500, self.destroy)
            else:
                self.ctx.emit("正在重新启动 ShapeYourPhoto")
                subprocess.Popen(self.ctx.restart_cmd, cwd=str(self.ctx.app_dir), close_fds=True)
                self.after(700, self.destroy)
        except Exception as exc:
            self.ctx.emit(f"更新未完成：{exc}")
            try:
                _restore_backups(self.ctx)
                self.ctx.emit("已恢复到更新前状态")
            except Exception as rollback_exc:
                self.ctx.emit(f"恢复失败：{rollback_exc}")
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "回滚失败",
                        f"更新失败且回滚未完全成功：\n{rollback_exc}\n\n请从完整安装包恢复程序目录。",
                        parent=self,
                    ),
                )
                return
            if self.ctx.cancel_requested.is_set():
                self.after(0, self._finish_cancelled)
            else:
                self.after(0, lambda err=exc: self._finish_failed(err))

    def _finish_cancelled(self) -> None:
        messagebox.showinfo("更新已取消", "更新已取消，程序已尽量恢复到更新前状态。", parent=self)
        self.destroy()

    def _finish_failed(self, exc: Exception) -> None:
        messagebox.showerror("更新失败", f"已中止并尽量回滚：\n{exc}", parent=self)
        self.button.configure(text="关闭", state="normal", command=self.destroy)
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
    manifest = json.loads(Path(args.manifest_cache).read_text(encoding="utf-8"))
    restart_cmd = json.loads(args.restart_cmd)
    ctx = UpdateContext(manifest=manifest, app_dir=Path(args.app_dir).resolve(), restart_cmd=restart_cmd)
    app = UpdaterWindow(ctx)
    app.mainloop()


if __name__ == "__main__":
    main()
