from __future__ import annotations

import ctypes
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from analyzer import is_supported_image
from file_safety import get_file_safety_service
from app_settings import (
    DEFAULT_SCAN_IGNORE_CONTAINS,
    DEFAULT_SCAN_IGNORE_PREFIXES,
    DEFAULT_SCAN_IGNORE_SUFFIXES,
    normalize_scan_ignore_contains,
    normalize_scan_ignore_prefixes,
    normalize_scan_ignore_suffixes,
    scan_mode_label,
)


_OUTPUT_PATH_LOCK = threading.Lock()


@dataclass
class CleanupOperationResult:
    moved: int
    mode: str
    destination_label: str
    fallback_folder: Path | None = None


@dataclass
class ScanSummary:
    root: Path
    mode: str
    imported_count: int
    skipped_details: list["SkippedDirectoryDetail"]
    visited_files: int
    ignored_prefixes: list[str]
    ignored_suffixes: list[str] = field(default_factory=list)
    ignored_contains: list[str] = field(default_factory=list)
    canceled: bool = False

    @property
    def skipped_directory_count(self) -> int:
        return len(self.skipped_details)

    @property
    def skipped_directories(self) -> list[Path]:
        return [detail.path for detail in self.skipped_details]

    @property
    def skipped_prefix_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for detail in self.skipped_details:
            counts[detail.matched_rule] = counts.get(detail.matched_rule, 0) + 1
        return counts

    @property
    def mode_label(self) -> str:
        return scan_mode_label(self.mode)


@dataclass
class SkippedDirectoryDetail:
    root: Path
    path: Path
    reason: str
    location: str
    matched_prefix: str = ""
    rule_kind: str = "prefix"
    matched_rule: str = ""


@dataclass
class ScanResult:
    paths: list[Path]
    summary: ScanSummary


def _normalized_scan_mode(mode: str) -> str:
    normalized = (mode or "all").strip().lower()
    if normalized not in {"all", "current_only", "subdirs_only"}:
        return "all"
    return normalized


def _should_ignore_directory(
    name: str,
    ignored_prefixes: list[str],
    ignored_suffixes: list[str] | None = None,
    ignored_contains: list[str] | None = None,
) -> bool:
    return _matched_ignore_rule(name, ignored_prefixes, ignored_suffixes or [], ignored_contains or []) is not None


def _matched_ignored_prefix(name: str, ignored_prefixes: list[str]) -> str | None:
    lowered = name.casefold()
    for prefix in ignored_prefixes:
        if lowered.startswith(prefix.casefold()):
            return prefix
    return None


def _matched_ignore_rule(
    name: str,
    ignored_prefixes: list[str],
    ignored_suffixes: list[str],
    ignored_contains: list[str],
) -> tuple[str, str] | None:
    lowered = name.casefold()
    for prefix in ignored_prefixes:
        if lowered.startswith(prefix.casefold()):
            return "prefix", prefix
    for suffix in ignored_suffixes:
        if lowered.endswith(suffix.casefold()):
            return "suffix", suffix
    for token in ignored_contains:
        if token.casefold() in lowered:
            return "contains", token
    return None


def _rule_kind_label(kind: str) -> str:
    if kind == "suffix":
        return "后缀"
    if kind == "contains":
        return "包含"
    return "前缀"


def _iter_scanned_paths(
    root: Path,
    *,
    mode: str,
    ignored_prefixes: list[str],
    ignored_suffixes: list[str] | None = None,
    ignored_contains: list[str] | None = None,
    progress_callback: Callable[[int, int, int, Path | None], None] | None = None,
    skip_callback: Callable[[SkippedDirectoryDetail], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> ScanResult:
    normalized_mode = _normalized_scan_mode(mode)
    ignored_suffixes = normalize_scan_ignore_suffixes(
        DEFAULT_SCAN_IGNORE_SUFFIXES if ignored_suffixes is None else ignored_suffixes
    )
    ignored_contains = normalize_scan_ignore_contains(
        DEFAULT_SCAN_IGNORE_CONTAINS if ignored_contains is None else ignored_contains
    )
    supported: list[Path] = []
    skipped_details: list[SkippedDirectoryDetail] = []
    seen_skipped: set[Path] = set()
    processed_files = 0
    discovered_files = 0

    def report_progress(current: Path | None = None) -> None:
        if progress_callback is not None:
            progress_callback(processed_files, max(processed_files, discovered_files), len(supported), current)

    def canceled() -> bool:
        return bool(cancel_event is not None and cancel_event.is_set())

    def can_import_file(path: Path) -> bool:
        return is_supported_image(path) and _matched_ignore_rule(
            path.name, ignored_prefixes, ignored_suffixes, ignored_contains
        ) is None

    def register_skip(path: Path, rule_kind: str, matched_rule: str) -> None:
        resolved = path.resolve()
        if resolved in seen_skipped:
            return
        seen_skipped.add(resolved)
        location = "root_child" if path.parent == root else "nested"
        kind_label = _rule_kind_label(rule_kind)
        detail = SkippedDirectoryDetail(
            root=root,
            path=path,
            location=location,
            matched_prefix=matched_rule if rule_kind == "prefix" else "",
            rule_kind=rule_kind,
            matched_rule=matched_rule,
            reason=f"名称符合忽略{kind_label}“{matched_rule}”，已跳过该文件夹和里面的图片。",
        )
        skipped_details.append(detail)
        if skip_callback is not None:
            skip_callback(detail)

    report_progress(None)

    matched_root_rule = _matched_ignore_rule(root.name, ignored_prefixes, ignored_suffixes, ignored_contains)
    if matched_root_rule is not None:
        register_skip(root, matched_root_rule[0], matched_root_rule[1])
        return ScanResult(
            paths=[],
            summary=ScanSummary(
                root=root,
                mode=normalized_mode,
                imported_count=0,
                skipped_details=skipped_details,
                visited_files=0,
                ignored_prefixes=list(ignored_prefixes),
                ignored_suffixes=list(ignored_suffixes),
                ignored_contains=list(ignored_contains),
                canceled=False,
            ),
        )

    if normalized_mode == "current_only":
        for child in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            if canceled():
                break
            if child.is_dir():
                matched_rule = _matched_ignore_rule(child.name, ignored_prefixes, ignored_suffixes, ignored_contains)
                if matched_rule is not None:
                    register_skip(child, matched_rule[0], matched_rule[1])
                continue
            if not child.is_file():
                continue
            discovered_files += 1
            processed_files += 1
            if can_import_file(child):
                supported.append(child)
            report_progress(child)
    else:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            if canceled():
                dirnames[:] = []
                break
            current_dir = Path(dirpath)
            kept_dirs: list[str] = []
            for dirname in sorted(dirnames, key=str.casefold):
                child_dir = current_dir / dirname
                matched_rule = _matched_ignore_rule(dirname, ignored_prefixes, ignored_suffixes, ignored_contains)
                if matched_rule is not None:
                    register_skip(child_dir, matched_rule[0], matched_rule[1])
                else:
                    kept_dirs.append(dirname)
            dirnames[:] = kept_dirs

            scan_files_here = not (normalized_mode == "subdirs_only" and current_dir == root)
            for filename in sorted(filenames, key=str.casefold):
                if canceled():
                    break
                child = current_dir / filename
                if not scan_files_here:
                    continue
                discovered_files += 1
                processed_files += 1
                if can_import_file(child):
                    supported.append(child)
                report_progress(child)

    supported.sort()
    return ScanResult(
        paths=supported,
        summary=ScanSummary(
            root=root,
            mode=normalized_mode,
            imported_count=len(supported),
            skipped_details=skipped_details,
            visited_files=processed_files,
            ignored_prefixes=list(ignored_prefixes),
            ignored_suffixes=list(ignored_suffixes),
            ignored_contains=list(ignored_contains),
            canceled=canceled(),
        ),
    )


def scan_image_paths(
    folder: str | Path,
    *,
    mode: str = "all",
    ignored_dir_prefixes: list[str] | tuple[str, ...] | None = None,
    ignored_dir_suffixes: list[str] | tuple[str, ...] | None = None,
    ignored_dir_contains: list[str] | tuple[str, ...] | None = None,
    skip_callback: Callable[[SkippedDirectoryDetail], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> list[Path]:
    root = Path(folder)
    result = _iter_scanned_paths(
        root,
        mode=mode,
        ignored_prefixes=normalize_scan_ignore_prefixes(list(DEFAULT_SCAN_IGNORE_PREFIXES if ignored_dir_prefixes is None else ignored_dir_prefixes)),
        ignored_suffixes=normalize_scan_ignore_suffixes(list(DEFAULT_SCAN_IGNORE_SUFFIXES if ignored_dir_suffixes is None else ignored_dir_suffixes)),
        ignored_contains=normalize_scan_ignore_contains(list(DEFAULT_SCAN_IGNORE_CONTAINS if ignored_dir_contains is None else ignored_dir_contains)),
        skip_callback=skip_callback,
        cancel_event=cancel_event,
    )
    return result.paths


def scan_image_paths_with_progress(
    folder: str | Path,
    progress_callback: Callable[[int, int, int, Path | None], None] | None = None,
    *,
    mode: str = "all",
    ignored_dir_prefixes: list[str] | tuple[str, ...] | None = None,
    ignored_dir_suffixes: list[str] | tuple[str, ...] | None = None,
    ignored_dir_contains: list[str] | tuple[str, ...] | None = None,
    skip_callback: Callable[[SkippedDirectoryDetail], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> ScanResult:
    root = Path(folder)
    return _iter_scanned_paths(
        root,
        mode=mode,
        ignored_prefixes=normalize_scan_ignore_prefixes(list(DEFAULT_SCAN_IGNORE_PREFIXES if ignored_dir_prefixes is None else ignored_dir_prefixes)),
        ignored_suffixes=normalize_scan_ignore_suffixes(list(DEFAULT_SCAN_IGNORE_SUFFIXES if ignored_dir_suffixes is None else ignored_dir_suffixes)),
        ignored_contains=normalize_scan_ignore_contains(list(DEFAULT_SCAN_IGNORE_CONTAINS if ignored_dir_contains is None else ignored_dir_contains)),
        progress_callback=progress_callback,
        skip_callback=skip_callback,
        cancel_event=cancel_event,
    )


def export_cleanup_list(paths: list[Path], base_folder: str | Path) -> Path:
    output_path = Path(base_folder) / "cleanup_list.txt"
    output_path.write_text("\n".join(str(path) for path in paths), encoding="utf-8")
    return output_path


def move_to_cleanup_folder(paths: list[Path], base_folder: str | Path) -> tuple[int, Path]:
    target_folder = Path(base_folder) / "_cleanup_candidates"
    target_folder.mkdir(parents=True, exist_ok=True)

    moved = 0
    for path in paths:
        destination = target_folder / path.name
        if destination.exists():
            stem = destination.stem
            suffix = destination.suffix
            index = 1
            while destination.exists():
                destination = target_folder / f"{stem}_{index}{suffix}"
                index += 1
        safety_result = get_file_safety_service(Path(base_folder)).move_to_quarantine(path, reason="cleanup candidate")
        if not safety_result.ok:
            raise OSError(safety_result.message)
        destination = safety_result.path or destination
        moved += 1

    return moved, target_folder


def _send_path_to_recycle_bin(path: Path) -> bool:
    if not path.exists():
        return False
    if ctypes.sizeof(ctypes.c_void_p) == 0:
        return False
    if not hasattr(ctypes, "windll") or not hasattr(ctypes.windll, "shell32"):
        return False

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    operation = SHFILEOPSTRUCTW()
    operation.wFunc = 3
    operation.pFrom = f"{str(path)}\0\0"
    operation.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    return result == 0 and not bool(operation.fAnyOperationsAborted)


def safe_cleanup_paths(paths: list[Path], base_folder: str | Path) -> CleanupOperationResult:
    existing_paths = [path for path in paths if path.exists()]
    if not existing_paths:
        return CleanupOperationResult(moved=0, mode="noop", destination_label="无可处理文件")

    recycled = 0
    fallback_needed = False
    pending_for_folder: list[Path] = []
    for path in existing_paths:
        if _send_path_to_recycle_bin(path):
            recycled += 1
        else:
            fallback_needed = True
            pending_for_folder.append(path)

    moved = recycled
    fallback_folder: Path | None = None
    if pending_for_folder:
        moved_to_folder, fallback_folder = move_to_cleanup_folder(pending_for_folder, base_folder)
        moved += moved_to_folder

    if recycled and not fallback_needed:
        return CleanupOperationResult(
            moved=moved,
            mode="recycle_bin",
            destination_label="系统回收站",
        )
    if fallback_folder is not None and recycled:
        return CleanupOperationResult(
            moved=moved,
            mode="mixed",
            destination_label=f"部分已移入回收站，其余移入 {fallback_folder}",
            fallback_folder=fallback_folder,
        )
    if fallback_folder is not None:
        return CleanupOperationResult(
            moved=moved,
            mode="quarantine_folder",
            destination_label=str(fallback_folder),
            fallback_folder=fallback_folder,
        )
    return CleanupOperationResult(moved=0, mode="noop", destination_label="无可处理文件")


def build_repaired_output_path(
    source_path: Path,
    base_folder: str | Path,
    output_folder_name: str,
    filename_suffix: str,
    overwrite_original: bool = False,
) -> Path:
    if overwrite_original:
        return source_path
    with _OUTPUT_PATH_LOCK:
        base_path = Path(base_folder)
        repair_root = base_path / output_folder_name
        try:
            relative = source_path.relative_to(base_path)
        except ValueError:
            relative = Path(source_path.name)

        output_dir = repair_root / relative.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = filename_suffix or "_fixed"
        candidate = output_dir / f"{source_path.stem}{suffix}{source_path.suffix}"
        if not candidate.exists():
            return candidate
        index = 1
        while True:
            numbered = output_dir / f"{source_path.stem}{suffix}_{index}{source_path.suffix}"
            if not numbered.exists():
                return numbered
            index += 1
