from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROTECTED_TOP_LEVEL = {
    ".git",
    ".github",
    "assets",
    "benchmark_reports",
    "build",
    "data",
    "docs",
    "private_docs",
    "src",
    "test",
    "tmp",
    "tools",
    "_cleanup_candidates",
    "_repair",
    "_repair_canceled_outputs",
    "_repair_cancel_backups",
    "_update_removed_files",
}


def path_within(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False

ROOT_KEEP_FILES = {
    ".gitignore",
    "app_settings.json",
    "README.md",
    "ShapeYourPhoto.exe",
    "usage_stats.json",
}

LEGACY_ROOT_FILES = {
    "app.py",
    "app.pyw",
    "CHANGELOG.md",
    "requirements.txt",
    "start.bat",
}

LEGACY_ENTRY_FILES = {
    "start_app.bat",
    "start_app.vbs",
    "setup_deps.bat",
    "start_app.py",
    "start_app.pyw",
}


@dataclass
class LegacyCleanupItem:
    path: str
    destination: str
    reason: str


@dataclass
class LegacyCleanupReport:
    moved: list[LegacyCleanupItem] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    manifest_path: str = ""


def _candidate_reason(root: Path, path: Path) -> str | None:
    name = path.name
    if name in ROOT_KEEP_FILES:
        return None
    if name in PROTECTED_TOP_LEVEL:
        return None
    if name in LEGACY_ROOT_FILES:
        return "root compatibility file moved to the organized project layout"
    if name in LEGACY_ENTRY_FILES:
        return "旧启动入口已移入隔离目录"
    if path.is_dir() and name == "__pycache__":
        return "旧运行缓存已移入隔离目录"
    if path.is_file() and path.suffix.lower() in {".py", ".pyw"} and (root / "src" / name).exists():
        return "旧根目录模块已由 src 目录接管"
    return None


def scan_legacy_candidates(root: Path) -> tuple[list[tuple[Path, str]], list[str]]:
    candidates: list[tuple[Path, str]] = []
    skipped: list[str] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        reason = _candidate_reason(root, child)
        if reason is None:
            continue
        if child.name in PROTECTED_TOP_LEVEL:
            skipped.append(f"{child.name}: 受保护目录已保留")
            continue
        candidates.append((child, reason))
    return candidates, skipped


def quarantine_legacy_files(root: str | Path) -> LegacyCleanupReport:
    app_root = Path(root).resolve()
    candidates, skipped = scan_legacy_candidates(app_root)
    report = LegacyCleanupReport(skipped=skipped)
    if not candidates:
        return report

    quarantine_root = app_root / "data" / "update_quarantine" / "legacy_cleanup" / time.strftime("%Y%m%d-%H%M%S")
    quarantine_root.mkdir(parents=True, exist_ok=True)
    if not path_within(app_root, quarantine_root):
        raise RuntimeError("旧文件隔离目录不在应用目录内")

    for source, reason in candidates:
        if not source.exists():
            continue
        if not path_within(app_root, source):
            report.skipped.append(f"{source}: 路径不在应用目录内")
            continue
        destination = quarantine_root / source.name
        index = 1
        while destination.exists():
            destination = quarantine_root / f"{source.stem}_{index}{source.suffix}"
            index += 1
        shutil.move(str(source), str(destination))
        report.moved.append(
            LegacyCleanupItem(
                path=str(source.relative_to(app_root)),
                destination=str(destination.relative_to(app_root)),
                reason=reason,
            )
        )

    manifest = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "moved": [asdict(item) for item in report.moved],
        "skipped": report.skipped,
    }
    manifest_path = quarantine_root / "legacy_cleanup_report.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report.manifest_path = str(manifest_path.relative_to(app_root))
    return report
