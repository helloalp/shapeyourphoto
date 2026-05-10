from __future__ import annotations

import argparse
import json
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

from cloud_security import path_within, sha256_file


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

    def emit(self, message: str) -> None:
        self.log.put(message)


def _read_url_to_file(url: str, target: Path, ctx: UpdateContext) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"", "file"}:
        source = Path(urllib.request.url2pathname(parsed.path if parsed.scheme == "file" else url))
        shutil.copy2(source, target)
        return
    with urllib.request.urlopen(url, timeout=20) as response, target.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        copied = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            copied += len(chunk)
            if total:
                ctx.emit(f"downloaded {copied}/{total} bytes")
            if ctx.cancel_requested.is_set():
                ctx.emit("cancel requested; finishing current safe point before rollback")


def _safe_zip_extract(zip_path: Path, target_dir: Path, ctx: UpdateContext) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            name = member.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            parts = [part for part in Path(name).parts if part not in {"", "."}]
            if len(parts) > 1 and parts[0].lower().startswith("shapeyourphoto"):
                relative = Path(*parts[1:])
            else:
                relative = Path(*parts)
            if any(part == ".." for part in relative.parts):
                raise RuntimeError(f"unsafe zip path: {name}")
            destination = target_dir / relative
            if not path_within(target_dir, destination):
                raise RuntimeError(f"zip path escapes target: {name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    ctx.emit("package extracted and zip-slip checks passed")


def _managed_paths(manifest: dict) -> list[Path]:
    raw = manifest.get("managed_files") or manifest.get("files") or []
    if isinstance(raw, dict):
        raw = raw.keys()
    paths: list[Path] = []
    for item in raw:
        path = Path(str(item).replace("\\", "/"))
        if path.parts and path.parts[0] not in PROTECTED_TOP_LEVEL and ".." not in path.parts:
            paths.append(path)
    return paths


def _deleted_paths(manifest: dict) -> list[Path]:
    raw = manifest.get("deleted_paths") or manifest.get("delete") or []
    paths: list[Path] = []
    for item in raw:
        path = Path(str(item).replace("\\", "/"))
        if path.parts and path.parts[0] not in PROTECTED_TOP_LEVEL and ".." not in path.parts:
            paths.append(path)
    return paths


def _backup_path(ctx: UpdateContext, relative: Path, backup_root: Path) -> None:
    source = ctx.app_dir / relative
    if not source.exists():
        return
    if not path_within(ctx.app_dir, source):
        raise RuntimeError(f"refusing backup outside app dir: {relative}")
    backup = backup_root / relative
    backup.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, backup, dirs_exist_ok=True)
    else:
        shutil.copy2(source, backup)
    ctx.backups.append((relative, backup))


def _restore_backups(ctx: UpdateContext) -> None:
    for relative, backup in reversed(ctx.backups):
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


def _replace_files(ctx: UpdateContext, extracted_root: Path, backup_root: Path) -> None:
    managed = _managed_paths(ctx.manifest)
    if not managed:
        managed = [path.relative_to(extracted_root) for path in extracted_root.rglob("*") if path.is_file()]
    for relative in managed:
        if ctx.cancel_requested.is_set():
            raise RuntimeError("update cancelled by user")
        source = extracted_root / relative
        target = ctx.app_dir / relative
        if not source.exists() or not source.is_file():
            ctx.emit(f"managed file absent in package, skipped: {relative}")
            continue
        if not path_within(ctx.app_dir, target):
            raise RuntimeError(f"refusing write outside app dir: {relative}")
        _backup_path(ctx, relative, backup_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        ctx.emit(f"updated {relative}")


def _quarantine_deleted(ctx: UpdateContext) -> None:
    deleted = _deleted_paths(ctx.manifest)
    if not deleted:
        return
    root = ctx.app_dir / "data" / "update_quarantine" / time.strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=True)
    ctx.quarantine_root = root
    for relative in deleted:
        target = ctx.app_dir / relative
        if not target.exists():
            continue
        if not path_within(ctx.app_dir, target):
            raise RuntimeError(f"refusing delete outside app dir: {relative}")
        if target.parts and relative.parts[0] in PROTECTED_TOP_LEVEL:
            ctx.emit(f"protected path not quarantined: {relative}")
            continue
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(destination))
        ctx.emit(f"quarantined removed path {relative}")


def run_update(ctx: UpdateContext) -> None:
    package_url = str(ctx.manifest.get("package_url") or ctx.manifest.get("url") or "")
    expected_hash = str(ctx.manifest.get("sha256") or "").lower()
    expected_size = int(ctx.manifest.get("package_size") or 0)
    if not package_url or not expected_hash:
        raise RuntimeError("manifest missing package_url or sha256")
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
        ctx.emit("downloading update package")
        _read_url_to_file(package_url, package_path, ctx)
        if expected_size and package_path.stat().st_size != expected_size:
            raise RuntimeError("package size mismatch")
        actual_hash = sha256_file(package_path)
        if actual_hash.lower() != expected_hash:
            raise RuntimeError("package sha256 mismatch")
        ctx.emit("package sha256 verified")
        _safe_zip_extract(package_path, extract_dir, ctx)
        _replace_files(ctx, extract_dir, backup_root)
        _quarantine_deleted(ctx)
        success = True
    finally:
        if success:
            try:
                shutil.rmtree(tmp_dir)
            except Exception as exc:
                ctx.emit(f"temporary update work dir kept for inspection: {tmp_dir} ({exc})")
        else:
            ctx.emit(f"temporary update work dir kept for rollback: {tmp_dir}")
    ctx.emit("update completed")


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
            self.ctx.emit("user confirmed cancellation; rollback will run at next safe point")

    def _worker(self) -> None:
        try:
            run_update(self.ctx)
            self.ctx.emit("restarting ShapeYourPhoto")
            subprocess.Popen(self.ctx.restart_cmd, cwd=str(self.ctx.app_dir), close_fds=True)
            self.after(700, self.destroy)
        except Exception as exc:
            self.ctx.emit(f"update failed: {exc}")
            try:
                _restore_backups(self.ctx)
                self.ctx.emit("rollback completed")
            except Exception as rollback_exc:
                self.ctx.emit(f"rollback failed: {rollback_exc}")
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "回滚失败",
                        f"更新失败且回滚未完全成功：\n{rollback_exc}\n\n请从完整安装包恢复程序目录。",
                        parent=self,
                    ),
                )
                return
            self.after(0, lambda: messagebox.showerror("更新失败", f"已中止并尽量回滚：\n{exc}", parent=self))


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
