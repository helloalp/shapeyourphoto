from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from models import SessionStats
from paths import migrate_legacy_file


STATS_PATH = migrate_legacy_file("usage_stats.json")


def load_stats() -> SessionStats:
    if not STATS_PATH.exists():
        return SessionStats()
    try:
        payload = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return SessionStats()
    return SessionStats(
        analyzed_images=int(payload.get("analyzed_images", 0)),
        analyzed_bytes=int(payload.get("analyzed_bytes", 0)),
        repaired_images=int(payload.get("repaired_images", 0)),
        repaired_bytes=int(payload.get("repaired_bytes", 0)),
        issue_images=int(payload.get("issue_images", 0)),
        issue_points=[(str(ts), float(val)) for ts, val in payload.get("issue_points", [])],
    )


def save_stats(stats: SessionStats) -> None:
    STATS_PATH.write_text(json.dumps(asdict(stats), ensure_ascii=False, indent=2), encoding="utf-8")


def record_analysis(stats: SessionStats, *, image_bytes: int, has_issue: bool) -> SessionStats:
    stats.analyzed_images += 1
    stats.analyzed_bytes += max(0, image_bytes)
    if has_issue:
        stats.issue_images += 1
    rate = stats.issue_images / max(1, stats.analyzed_images)
    stats.issue_points.append((datetime.now().isoformat(timespec="seconds"), rate))
    stats.issue_points = stats.issue_points[-200:]
    return stats


def record_repair(stats: SessionStats, *, image_bytes: int) -> SessionStats:
    stats.repaired_images += 1
    stats.repaired_bytes += max(0, image_bytes)
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
