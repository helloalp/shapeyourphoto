from __future__ import annotations

import argparse
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "src"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from analyzer import analyze_image
from app_settings import ANALYSIS_CONCURRENCY_HIGH, ANALYSIS_CONCURRENCY_LOW, ANALYSIS_CONCURRENCY_MEDIUM, resolve_analysis_worker_plan
from analysis.core import is_supported_image
from models import AnalysisResult
from similar_detector import detect_similar_groups


DEFAULT_MODES = ("single", ANALYSIS_CONCURRENCY_LOW, ANALYSIS_CONCURRENCY_MEDIUM, ANALYSIS_CONCURRENCY_HIGH)
DEFAULT_REPORT_DIR = Path("benchmark_reports")
DEFAULT_MANIFEST_PATH = Path("test") / "manifest.json"
STAGE_LABELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("image_open", ("image_open",)),
    ("exif_transpose", ("exif_transpose",)),
    ("resize", ("resize", "working_resize")),
    ("array_convert", ("array_convert",)),
    ("exposure", ("exposure",)),
    ("color", ("color",)),
    ("sharpness", ("sharpness",)),
    ("noise", ("noise",)),
    ("portrait", ("face_detect", "portrait_region_build")),
    ("quality_stats", ("quality_stats",)),
    ("cleanup_candidate", ("cleanup_candidate",)),
)


def _format_ms(value: float) -> str:
    if value >= 1000.0:
        return f"{value / 1000.0:.2f}s"
    return f"{value:.0f}ms"


def _test_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted((path for path in root.iterdir() if path.is_file() and is_supported_image(path)), key=lambda path: path.name.casefold())


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Manifest unreadable, skipped: {path} ({exc})")
        return None
    if not isinstance(payload, dict):
        print(f"Manifest is not a JSON object, skipped: {path}")
        return None
    return payload


def _resolve_workers(mode: str, image_count: int) -> tuple[str, int, int, str]:
    if mode == "single":
        return "single", 1, 1, "single-thread baseline"
    plan = resolve_analysis_worker_plan(image_count, mode, 0)
    return plan.mode, plan.requested_workers, plan.actual_workers, plan.reason


def _stage_totals(results: dict[Path, AnalysisResult], similar_ms: float) -> list[tuple[str, float]]:
    totals: dict[str, float] = {}
    for result in results.values():
        timings = result.perf_timings
        for label, keys in STAGE_LABELS:
            totals[label] = totals.get(label, 0.0) + sum(float(timings.get(key, 0.0)) for key in keys)
    totals["similar_detection"] = similar_ms
    return [(label, value) for label, value in sorted(totals.items(), key=lambda item: item[1], reverse=True) if value > 0.0]


def _manifest_expectations(manifest: dict[str, object] | None) -> dict[str, dict[str, object]]:
    if not manifest:
        return {}
    images = manifest.get("images", [])
    if not isinstance(images, list):
        return {}
    expectations: dict[str, dict[str, object]] = {}
    for item in images:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename", "")).strip()
        if filename:
            expectations[filename] = item
    return expectations


def _compare_manifest(
    manifest: dict[str, object] | None,
    results: dict[Path, AnalysisResult],
    similar_members: set[str],
) -> list[dict[str, object]]:
    expectations = _manifest_expectations(manifest)
    comparisons: list[dict[str, object]] = []
    for path, result in sorted(results.items(), key=lambda item: item[0].name.casefold()):
        expected = expectations.get(path.name)
        if not expected:
            continue
        actual_issues = [issue.code for issue in result.issues]
        expected_issues = [str(value) for value in expected.get("expected_issues", []) if str(value)]
        not_expected = [str(value) for value in expected.get("not_expected_issues", []) if str(value)]
        expected_cleanup = expected.get("cleanup_candidate")
        expected_similar = expected.get("similar_group")
        notes: list[str] = []
        missing_issues = [code for code in expected_issues if code not in actual_issues]
        unexpected_issues = [code for code in not_expected if code in actual_issues]
        cleanup_actual = bool(result.cleanup_candidates)
        similar_actual = path.name in similar_members
        if missing_issues:
            notes.append("missing expected issues: " + ", ".join(missing_issues))
        if unexpected_issues:
            notes.append("unexpected issues present: " + ", ".join(unexpected_issues))
        if isinstance(expected_cleanup, bool) and expected_cleanup != cleanup_actual:
            notes.append(f"cleanup expected {expected_cleanup}, got {cleanup_actual}")
        if isinstance(expected_similar, bool) and expected_similar != similar_actual:
            notes.append(f"similar expected {expected_similar}, got {similar_actual}")
        comparisons.append(
            {
                "filename": path.name,
                "scene_type": expected.get("scene_type", ""),
                "actual_issues": actual_issues,
                "expected_issues": expected_issues,
                "cleanup_candidate": cleanup_actual,
                "similar_group": similar_actual,
                "passed": not notes,
                "notes": notes,
            }
        )
    return comparisons


def _run_mode(paths: list[Path], mode: str, manifest: dict[str, object] | None = None) -> dict[str, object]:
    mode_name, requested_workers, actual_workers, reason = _resolve_workers(mode, len(paths))
    started = time.perf_counter()
    results: dict[Path, AnalysisResult] = {}
    errors: dict[Path, str] = {}
    with ThreadPoolExecutor(max_workers=actual_workers) as pool:
        futures = {}
        for path in paths:
            queued_at = time.perf_counter()

            def job(p: Path = path, queued: float = queued_at) -> AnalysisResult:
                job_started = time.perf_counter()
                result = analyze_image(p)
                job_finished = time.perf_counter()
                result.perf_timings["worker_queue_wait"] = (job_started - queued) * 1000.0
                result.perf_timings["worker_wall_time"] = (job_finished - job_started) * 1000.0
                return result

            futures[pool.submit(job)] = path
        for future in as_completed(futures):
            path = futures[future]
            try:
                results[path] = future.result()
            except Exception as exc:
                errors[path] = str(exc)

    similar_started = time.perf_counter()
    similar_groups = detect_similar_groups(paths, results, max_workers=actual_workers)
    similar_ms = (time.perf_counter() - similar_started) * 1000.0
    similar_members = {path.name for group in similar_groups for path in group.paths}
    wall_ms = (time.perf_counter() - started) * 1000.0
    worker_cumulative_ms = sum(
        result.perf_timings.get("worker_wall_time", result.perf_timings.get("analyze_total", 0.0))
        for result in results.values()
    )
    queue_wait_ms = sum(result.perf_timings.get("worker_queue_wait", 0.0) for result in results.values())
    slow_images = sorted(results.values(), key=lambda result: result.perf_timings.get("worker_wall_time", 0.0), reverse=True)[:5]
    return {
        "mode": mode_name,
        "requested_workers": requested_workers,
        "actual_workers": actual_workers,
        "reason": reason,
        "images": len(paths),
        "success": len(results),
        "failed": len(errors),
        "wall_ms": wall_ms,
        "avg_wall_ms": wall_ms / max(1, len(paths)),
        "worker_cumulative_ms": worker_cumulative_ms,
        "parallel_efficiency": worker_cumulative_ms / max(1.0, wall_ms),
        "queue_wait_ms": queue_wait_ms,
        "avg_queue_wait_ms": queue_wait_ms / max(1, len(results)),
        "similar_ms": similar_ms,
        "similar_groups": len(similar_groups),
        "slow_stages": _stage_totals(results, similar_ms)[:5],
        "slow_images": [(result.path.name, result.perf_timings.get("worker_wall_time", 0.0)) for result in slow_images],
        "issues": sum(1 for result in results.values() if result.issues),
        "cleanup_candidates": sum(len(result.cleanup_candidates) for result in results.values()),
        "manifest_comparisons": _compare_manifest(manifest, results, similar_members),
    }


def _latest_previous_report(report_dir: Path, root: Path) -> dict[str, object] | None:
    if not report_dir.exists():
        return None
    resolved_root = str(root.resolve())
    reports = sorted(report_dir.glob("benchmark-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for report in reports:
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("root") == resolved_root:
            return payload
    return None


def _first_mode_result(report: dict[str, object], mode: str) -> dict[str, object] | None:
    modes = report.get("modes", [])
    if not isinstance(modes, list):
        return None
    for item in modes:
        if isinstance(item, dict) and item.get("mode") == mode:
            return item
    return modes[0] if modes and isinstance(modes[0], dict) else None


def _build_comparison(previous: dict[str, object] | None, current_modes: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    if not previous:
        return {}
    comparison: dict[str, dict[str, float]] = {}
    for current in current_modes:
        mode = str(current.get("mode", ""))
        old = _first_mode_result(previous, mode)
        if old is None:
            continue
        comparison[mode] = {
            "wall_ms_delta": float(current.get("wall_ms", 0.0)) - float(old.get("wall_ms", 0.0)),
            "issues_delta": float(current.get("issues", 0)) - float(old.get("issues", 0)),
            "cleanup_candidates_delta": float(current.get("cleanup_candidates", 0)) - float(old.get("cleanup_candidates", 0)),
            "similar_groups_delta": float(current.get("similar_groups", 0)) - float(old.get("similar_groups", 0)),
        }
    return comparison


def _write_reports(report_dir: Path, report: dict[str, object]) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = str(report["run_id"])
    json_path = report_dir / f"benchmark-{timestamp}.json"
    md_path = report_dir / f"benchmark-{timestamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_format_markdown_report(report), encoding="utf-8")
    return json_path, md_path


def _format_markdown_report(report: dict[str, object]) -> str:
    lines = [
        "# ShapeYourPhoto Benchmark Report",
        "",
        f"- Run: `{report['run_id']}`",
        f"- Time: `{report['run_time']}`",
        f"- Root: `{report['root']}`",
        f"- Images: `{report['images']}`",
        f"- Manifest: `{report.get('manifest_path') or 'not found'}`",
        "",
        "## Modes",
        "",
        "| mode | workers | wall | avg/img | worker cumulative | avg queue/img | issues | cleanup | similar |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report.get("modes", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"| {item['mode']} | {item['requested_workers']}/{item['actual_workers']} | "
            f"{_format_ms(float(item['wall_ms']))} | {_format_ms(float(item['avg_wall_ms']))} | "
            f"{_format_ms(float(item['worker_cumulative_ms']))} | {_format_ms(float(item.get('avg_queue_wait_ms', 0.0)))} | {item['issues']} | "
            f"{item['cleanup_candidates']} | {item['similar_groups']} |"
        )
        lines.append("")
        lines.append("Slow stages top 5: " + " | ".join(f"{label} {_format_ms(value)}" for label, value in item["slow_stages"]))
        lines.append("Slow images top 5: " + " | ".join(f"{name} {_format_ms(value)}" for name, value in item["slow_images"]))
        manifest_items = [entry for entry in item.get("manifest_comparisons", []) if isinstance(entry, dict)]
        if manifest_items:
            failed = [entry for entry in manifest_items if not entry.get("passed")]
            lines.append(f"Manifest checks: {len(manifest_items) - len(failed)}/{len(manifest_items)} passed")
            for entry in failed[:10]:
                lines.append(f"- {entry['filename']}: " + "; ".join(str(note) for note in entry.get("notes", [])))
        lines.append("")
    comparison = report.get("comparison_to_previous", {})
    if comparison:
        lines.extend(["## Comparison To Previous", ""])
        for mode, values in comparison.items():
            if isinstance(values, dict):
                lines.append(
                    f"- `{mode}`: wall {_format_ms(float(values['wall_ms_delta']))}, "
                    f"issues {values['issues_delta']:+.0f}, cleanup {values['cleanup_candidates_delta']:+.0f}, "
                    f"similar {values['similar_groups_delta']:+.0f}"
                )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark local real test images under /test.")
    parser.add_argument("--root", default="test", help="Local test image folder. Defaults to ./test.")
    parser.add_argument("--modes", default=",".join(DEFAULT_MODES), help="Comma-separated modes: single,low,medium,high.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Ignored local report directory.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Optional local manifest JSON.")
    args = parser.parse_args()

    root = Path(args.root)
    paths = _test_images(root)
    if not paths:
        print(f"No local test images found in {root.resolve()}; skipped.")
        return 0

    modes = [mode.strip().lower() for mode in args.modes.split(",") if mode.strip()]
    report_dir = Path(args.report_dir)
    previous_report = _latest_previous_report(report_dir, root)
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    mode_results: list[dict[str, object]] = []
    print(f"Local test image benchmark: root={root.resolve()} images={len(paths)}")
    print("mode | workers(requested/actual) | wall | avg wall/img | worker cumulative | efficiency | avg queue/img | queue cumulative | similar | groups | issues | cleanup")
    for mode in modes:
        result = _run_mode(paths, mode, manifest)
        mode_results.append(result)
        reason = f" ({result['reason']})" if result["reason"] else ""
        print(
            f"{result['mode']} | {result['requested_workers']}/{result['actual_workers']}{reason} | "
            f"{_format_ms(float(result['wall_ms']))} | {_format_ms(float(result['avg_wall_ms']))} | "
            f"{_format_ms(float(result['worker_cumulative_ms']))} | {float(result['parallel_efficiency']):.2f}x | "
            f"{_format_ms(float(result['avg_queue_wait_ms']))} | {_format_ms(float(result['queue_wait_ms']))} | "
            f"{_format_ms(float(result['similar_ms']))} | "
            f"{result['similar_groups']} | {result['issues']} | {result['cleanup_candidates']}"
        )
        print("  slow stages top5: " + " | ".join(f"{label} {_format_ms(value)}" for label, value in result["slow_stages"]))
        print("  slow images top5: " + " | ".join(f"{name} {_format_ms(value)}" for name, value in result["slow_images"]))
        manifest_items = [entry for entry in result["manifest_comparisons"] if isinstance(entry, dict)]
        if manifest_items:
            passed = sum(1 for entry in manifest_items if entry.get("passed"))
            print(f"  manifest checks: {passed}/{len(manifest_items)} passed")
    report = {
        "run_id": run_id,
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "root": str(root.resolve()),
        "images": len(paths),
        "modes": mode_results,
        "manifest_path": str(manifest_path.resolve()) if manifest is not None else "",
        "comparison_to_previous": _build_comparison(previous_report, mode_results),
    }
    json_path, md_path = _write_reports(report_dir, report)
    print(f"Report written: {json_path.resolve()}")
    print(f"Report written: {md_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
