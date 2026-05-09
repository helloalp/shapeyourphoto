from __future__ import annotations

import csv
import ctypes
import json
import shutil
from ctypes import wintypes
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app_metadata import APP_VERSION
from models import RepairRecord, SessionStats
from paths import migrate_legacy_file, user_data_dir


DATA_DIR = user_data_dir()
STATS_PATH = DATA_DIR / "usage_stats.dpapi"
LEGACY_STATS_PATH = migrate_legacy_file("usage_stats.json")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_available() -> bool:
    return hasattr(ctypes, "windll") and hasattr(ctypes.windll, "crypt32")


def _blob_from_bytes(data: bytes) -> DATA_BLOB:
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    blob._buffer = buffer  # type: ignore[attr-defined]
    return blob


def _bytes_from_blob(blob: DATA_BLOB) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        try:
            ctypes.windll.kernel32.LocalFree(blob.pbData)
        except Exception:
            pass


def _encrypt(data: bytes) -> bytes:
    if not _dpapi_available():
        raise RuntimeError("当前系统不可用 DPAPI，统计数据不会伪装成已加密存储。")
    in_blob = _blob_from_bytes(data)
    out_blob = DATA_BLOB()
    description = "ShapeYourPhoto usage stats"
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        description,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()
    return _bytes_from_blob(out_blob)


def _decrypt(data: bytes) -> bytes:
    if not _dpapi_available():
        raise RuntimeError("当前系统不可用 DPAPI，无法读取加密统计数据。")
    in_blob = _blob_from_bytes(data)
    out_blob = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()
    return _bytes_from_blob(out_blob)


def _stats_from_payload(payload: object) -> SessionStats:
    if not isinstance(payload, dict):
        return SessionStats()
    return SessionStats(
        analyzed_images=int(payload.get("analyzed_images", 0)),
        analyzed_bytes=int(payload.get("analyzed_bytes", 0)),
        repaired_images=int(payload.get("repaired_images", 0)),
        repaired_bytes=int(payload.get("repaired_bytes", 0)),
        issue_images=int(payload.get("issue_images", 0)),
        issue_points=[(str(ts), float(val)) for ts, val in payload.get("issue_points", [])],
        repair_attempted_images=int(payload.get("repair_attempted_images", 0)),
        skipped_images=int(payload.get("skipped_images", 0)),
        noop_images=int(payload.get("noop_images", 0)),
        rollback_images=int(payload.get("rollback_images", 0)),
        cleanup_candidate_images=int(payload.get("cleanup_candidate_images", 0)),
        similar_group_count=int(payload.get("similar_group_count", 0)),
        analysis_runs=int(payload.get("analysis_runs", 0)),
        repair_runs=int(payload.get("repair_runs", 0)),
        analysis_wall_ms_total=float(payload.get("analysis_wall_ms_total", 0.0)),
        repair_wall_ms_total=float(payload.get("repair_wall_ms_total", 0.0)),
        last_run_at=str(payload.get("last_run_at", "")),
        daily_counts={
            str(day): {str(k): int(v) for k, v in values.items()}
            for day, values in dict(payload.get("daily_counts", {})).items()
            if isinstance(values, dict)
        },
        version_counts={
            str(version): {str(k): int(v) for k, v in values.items()}
            for version, values in dict(payload.get("version_counts", {})).items()
            if isinstance(values, dict)
        },
    )


def load_stats() -> SessionStats:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if STATS_PATH.exists() and _dpapi_available():
        try:
            raw = _decrypt(STATS_PATH.read_bytes())
            return _stats_from_payload(json.loads(raw.decode("utf-8")))
        except Exception:
            return SessionStats()
    stats = _load_legacy_stats()
    if LEGACY_STATS_PATH.exists() and _dpapi_available():
        try:
            save_stats(stats)
            marker = LEGACY_STATS_PATH.with_name(
                f"{LEGACY_STATS_PATH.stem}.migrated-{datetime.now().strftime('%Y%m%d-%H%M%S')}{LEGACY_STATS_PATH.suffix}"
            )
            shutil.copy2(LEGACY_STATS_PATH, marker)
        except Exception:
            pass
    return stats


def _load_legacy_stats() -> SessionStats:
    if not LEGACY_STATS_PATH.exists():
        return SessionStats()
    try:
        payload = json.loads(LEGACY_STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return SessionStats()
    return _stats_from_payload(payload)


def save_stats(stats: SessionStats) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload_text = json.dumps(asdict(stats), ensure_ascii=False, indent=2)
    if _dpapi_available():
        encrypted = _encrypt(payload_text.encode("utf-8"))
        STATS_PATH.write_bytes(encrypted)
        return
    LEGACY_STATS_PATH.write_text(payload_text, encoding="utf-8")


def _bump_bucket(stats: SessionStats, key: str, amount: int = 1, *, version: str = APP_VERSION) -> None:
    now = datetime.now()
    stats.last_run_at = now.isoformat(timespec="seconds")
    day = now.date().isoformat()
    stats.daily_counts.setdefault(day, {})
    stats.daily_counts[day][key] = stats.daily_counts[day].get(key, 0) + amount
    stats.version_counts.setdefault(version, {})
    stats.version_counts[version][key] = stats.version_counts[version].get(key, 0) + amount


def record_analysis(stats: SessionStats, *, image_bytes: int, has_issue: bool, cleanup_candidate_count: int = 0) -> SessionStats:
    stats.analyzed_images += 1
    stats.analyzed_bytes += max(0, image_bytes)
    if has_issue:
        stats.issue_images += 1
    if cleanup_candidate_count:
        stats.cleanup_candidate_images += 1
    rate = stats.issue_images / max(1, stats.analyzed_images)
    stats.issue_points.append((datetime.now().isoformat(timespec="seconds"), rate))
    stats.issue_points = stats.issue_points[-200:]
    _bump_bucket(stats, "analyzed", 1)
    if has_issue:
        _bump_bucket(stats, "issues", 1)
    if cleanup_candidate_count:
        _bump_bucket(stats, "cleanup_candidates", 1)
    return stats


def record_analysis_batch(stats: SessionStats, *, wall_ms: float, similar_groups: int = 0) -> SessionStats:
    stats.analysis_runs += 1
    stats.analysis_wall_ms_total += max(0.0, float(wall_ms))
    stats.similar_group_count += max(0, int(similar_groups))
    _bump_bucket(stats, "analysis_runs", 1)
    if similar_groups:
        _bump_bucket(stats, "similar_groups", int(similar_groups))
    return stats


def record_repair(stats: SessionStats, *, image_bytes: int) -> SessionStats:
    stats.repaired_images += 1
    stats.repaired_bytes += max(0, image_bytes)
    _bump_bucket(stats, "repaired", 1)
    return stats


def record_repair_batch(
    stats: SessionStats,
    records: list[RepairRecord],
    *,
    failed_count: int,
    wall_ms: float,
) -> SessionStats:
    stats.repair_runs += 1
    stats.repair_wall_ms_total += max(0.0, float(wall_ms))
    stats.repair_attempted_images += len(records) + max(0, int(failed_count))
    skipped = [record for record in records if not record.saved_output]
    stats.skipped_images += len(skipped)
    stats.noop_images += sum(1 for record in skipped if "no-op" in (record.skipped_reason or "").lower())
    stats.rollback_images += sum(1 for record in records if "rollback" in record.outcome_category or "回退" in (record.skipped_reason or ""))
    if skipped:
        _bump_bucket(stats, "skipped", len(skipped))
    if failed_count:
        _bump_bucket(stats, "failed", int(failed_count))
    _bump_bucket(stats, "repair_runs", 1)
    return stats


def export_stats_report(stats: SessionStats, output_path: str | Path) -> Path:
    path = Path(output_path)
    rows = [
        ("analyzed_images", stats.analyzed_images),
        ("analyzed_bytes", stats.analyzed_bytes),
        ("repaired_images", stats.repaired_images),
        ("repaired_bytes", stats.repaired_bytes),
        ("issue_images", stats.issue_images),
        ("issue_rate", stats.issue_images / max(1, stats.analyzed_images)),
        ("repair_attempted_images", stats.repair_attempted_images),
        ("skipped_images", stats.skipped_images),
        ("noop_images", stats.noop_images),
        ("rollback_images", stats.rollback_images),
        ("cleanup_candidate_images", stats.cleanup_candidate_images),
        ("similar_group_count", stats.similar_group_count),
        ("average_analysis_wall_ms", stats.average_analysis_wall_ms()),
        ("average_repair_wall_ms", stats.average_repair_wall_ms()),
        ("last_run_at", stats.last_run_at),
    ]
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)
        writer.writerow([])
        writer.writerow(["timestamp", "issue_rate"])
        for ts, rate in stats.issue_points:
            writer.writerow([ts, f"{rate:.6f}"])
    return path
