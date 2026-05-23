from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from cloud_security import path_within


@dataclass
class FileSafetyResult:
    ok: bool
    path: Path | None = None
    backup: Path | None = None
    message: str = ""
    rolled_back: bool = False
    log_entries: list[dict[str, object]] = field(default_factory=list)


class FileSafetyService:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or Path.cwd()).resolve()
        self.state_dir = self.base_dir / "data" / "file_safety"
        self.quarantine_dir = self.state_dir / "quarantine"
        self.log_path = self.state_dir / "operations.jsonl"

    def _ensure_state(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, action: str, **payload: object) -> dict[str, object]:
        self._ensure_state()
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action, **payload}
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return entry

    def _assert_safe_path(self, path: Path) -> Path:
        resolved = path.resolve()
        if ".." in path.parts:
            raise ValueError(f"unsafe path traversal: {path}")
        return resolved

    def unique_path(self, target: Path) -> Path:
        target = self._assert_safe_path(target)
        if not target.exists():
            return target
        stem = target.stem
        suffix = target.suffix
        index = 1
        while True:
            candidate = target.with_name(f"{stem}-{index}{suffix}")
            if not candidate.exists():
                return candidate
            index += 1

    def atomic_save_image(self, image, target: Path, fmt: str, save_kwargs: dict[str, object]) -> FileSafetyResult:
        target = self._assert_safe_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.stem}.", suffix=f"{target.suffix}.tmp", dir=str(target.parent))
        os.close(fd)
        temp_path = Path(temp_name)
        entries: list[dict[str, object]] = []
        try:
            image.save(temp_path, fmt, **save_kwargs)
            os.replace(temp_path, target)
            entries.append(self._log("atomic_save", target=str(target), fmt=fmt))
            return FileSafetyResult(True, path=target, message="saved", log_entries=entries)
        except Exception as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            entries.append(self._log("atomic_save_failed", target=str(target), error=str(exc)))
            return FileSafetyResult(False, path=target, message=str(exc), log_entries=entries)

    def transactional_overwrite(
        self,
        target: Path,
        writer,
        *,
        keep_user_backup: bool = False,
        visible_backup_dir: Path | None = None,
    ) -> FileSafetyResult:
        target = self._assert_safe_path(target)
        if not target.exists() or not target.is_file():
            return FileSafetyResult(False, path=target, message="target missing")
        self._ensure_state()
        txn_dir = self.state_dir / "transactions" / time.strftime("%Y%m%d-%H%M%S")
        txn_dir.mkdir(parents=True, exist_ok=True)
        txn_backup = txn_dir / target.name
        entries: list[dict[str, object]] = []
        try:
            shutil.copy2(target, txn_backup)
            user_backup: Path | None = None
            if keep_user_backup:
                backup_root = visible_backup_dir or target.parent / ".metadata-bak"
                backup_root.mkdir(parents=True, exist_ok=True)
                user_backup = self.unique_path(backup_root / target.name)
                shutil.copy2(target, user_backup)
                entries.append(self._log("visible_backup", target=str(target), backup=str(user_backup)))
            writer(target)
            try:
                txn_backup.unlink(missing_ok=True)
                txn_dir.rmdir()
            except Exception:
                pass
            entries.append(self._log("transactional_overwrite", target=str(target), backup=str(user_backup or "")))
            return FileSafetyResult(True, path=target, backup=user_backup, message="saved", log_entries=entries)
        except Exception as exc:
            rolled_back = False
            try:
                if txn_backup.exists():
                    shutil.copy2(txn_backup, target)
                    rolled_back = True
            except Exception:
                rolled_back = False
            entries.append(self._log("transactional_overwrite_failed", target=str(target), error=str(exc), rolled_back=rolled_back))
            return FileSafetyResult(False, path=target, backup=txn_backup, message=str(exc), rolled_back=rolled_back, log_entries=entries)

    def move_to_quarantine(self, path: Path, *, reason: str = "quarantine") -> FileSafetyResult:
        source = self._assert_safe_path(path)
        if not source.exists():
            return FileSafetyResult(False, path=source, message="source missing")
        self._ensure_state()
        destination = self.unique_path(self.quarantine_dir / source.name)
        if not path_within(self.quarantine_dir, destination):
            raise ValueError(f"quarantine path escaped: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(source), str(destination))
            entry = self._log("quarantine", source=str(source), destination=str(destination), reason=reason)
            return FileSafetyResult(True, path=destination, message="quarantined", log_entries=[entry])
        except Exception as exc:
            entry = self._log("quarantine_failed", source=str(source), error=str(exc), reason=reason)
            return FileSafetyResult(False, path=source, message=str(exc), log_entries=[entry])


_DEFAULT_SERVICE: FileSafetyService | None = None


def get_file_safety_service(base_dir: Path | None = None) -> FileSafetyService:
    global _DEFAULT_SERVICE
    if base_dir is not None:
        return FileSafetyService(base_dir)
    if _DEFAULT_SERVICE is None:
        _DEFAULT_SERVICE = FileSafetyService(Path.cwd())
    return _DEFAULT_SERVICE
