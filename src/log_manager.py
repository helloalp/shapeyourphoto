from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import zipfile

from paths import is_frozen, resource_path, user_data_dir


def _base_data_dir() -> Path:
    if is_frozen():
        return user_data_dir()
    return resource_path("data")


LOG_DIR = _base_data_dir() / "logs"


def ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def cleanup_old_logs(retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0
    for path in ensure_log_dir().glob("*.log"):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def current_log_path() -> Path:
    day = datetime.now().strftime("%Y%m%d")
    return ensure_log_dir() / f"shapeyourphoto-{day}.log"


def append_log_line(line: str) -> None:
    path = current_log_path()
    with path.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(line.rstrip("\n") + "\n")


def export_logs_bundle(console_dump: str, *, days: int = 7) -> Path:
    log_dir = ensure_log_dir()
    export_dir = _base_data_dir() / "log_exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle = export_dir / f"shapeyourphoto-logs-{stamp}.zip"
    cutoff = datetime.now() - timedelta(days=max(1, days))
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("console-current.txt", console_dump)
        for path in sorted(log_dir.glob("*.log")):
            try:
                if datetime.fromtimestamp(path.stat().st_mtime) >= cutoff:
                    archive.write(path, f"logs/{path.name}")
            except OSError:
                continue
    return bundle
