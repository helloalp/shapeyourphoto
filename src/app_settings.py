from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from paths import migrate_legacy_file
from ui.language import DEFAULT_LANGUAGE, normalize_language

SETTINGS_PATH = migrate_legacy_file("app_settings.json")
SETTINGS_SCHEMA_VERSION = 7
DEFAULT_SCAN_IGNORE_PREFIXES = ["_repair"]
DEFAULT_SCAN_IGNORE_SUFFIXES: list[str] = []
DEFAULT_SCAN_IGNORE_CONTAINS: list[str] = []
FIXED_UPDATE_MANIFEST_URL = "https://helloalp.top/shapeyourphoto/updates/manifest.json"
FIXED_CLOUD_MESSAGES_URL = "https://helloalp.top/shapeyourphoto/updates/messages.json"
DEFAULT_UPDATE_MANIFEST_URL = FIXED_UPDATE_MANIFEST_URL
DEFAULT_CLOUD_MESSAGES_URL = FIXED_CLOUD_MESSAGES_URL

SCAN_MODE_ASK = "ask"
SCAN_MODE_ALL = "all"
SCAN_MODE_CURRENT_ONLY = "current_only"
SCAN_MODE_SUBDIRS_ONLY = "subdirs_only"

ANALYSIS_CONCURRENCY_AUTO = "auto"
ANALYSIS_CONCURRENCY_LOW = "low"
ANALYSIS_CONCURRENCY_MEDIUM = "medium"
ANALYSIS_CONCURRENCY_HIGH = "high"
ANALYSIS_CONCURRENCY_EXTREME = "extreme"
ANALYSIS_CONCURRENCY_CUSTOM = "custom"

ANALYSIS_CONCURRENCY_OPTIONS: list[tuple[str, str]] = [
    (ANALYSIS_CONCURRENCY_AUTO, "自动"),
    (ANALYSIS_CONCURRENCY_LOW, "低"),
    (ANALYSIS_CONCURRENCY_MEDIUM, "中"),
    (ANALYSIS_CONCURRENCY_HIGH, "高"),
    (ANALYSIS_CONCURRENCY_EXTREME, "极高"),
    (ANALYSIS_CONCURRENCY_CUSTOM, "自定义同时处理数量"),
]
ANALYSIS_CONCURRENCY_LABELS = {value: label for value, label in ANALYSIS_CONCURRENCY_OPTIONS}

GPU_ACCELERATION_OFF = "off"
GPU_ACCELERATION_AUTO = "auto"
GPU_ACCELERATION_ON = "on"

GPU_ACCELERATION_OPTIONS: list[tuple[str, str]] = [
    (GPU_ACCELERATION_OFF, "关闭"),
    (GPU_ACCELERATION_AUTO, "自动"),
    (GPU_ACCELERATION_ON, "开启"),
]
GPU_ACCELERATION_LABELS = {value: label for value, label in GPU_ACCELERATION_OPTIONS}

CONSOLE_TIME_24H = "24h"
CONSOLE_TIME_12H = "12h"
CONSOLE_TIME_24H_TZ = "24h_tz"
CONSOLE_TIME_ELAPSED = "elapsed"

CONSOLE_TIME_MODE_OPTIONS: list[tuple[str, str]] = [
    (CONSOLE_TIME_24H, "24 小时制 [20:28:14]"),
    (CONSOLE_TIME_12H, "12 小时制 [08:28:14 PM]"),
    (CONSOLE_TIME_24H_TZ, "24 小时制 + 时区 [20:28:14 UTC+09:00]"),
    (CONSOLE_TIME_ELAPSED, "启动后经过时间 [T+00:20:28]"),
]
CONSOLE_TIME_MODE_LABELS = {value: label for value, label in CONSOLE_TIME_MODE_OPTIONS}

UI_DENSITY_STANDARD = "standard"
UI_DENSITY_COMFORTABLE = "comfortable"
UI_DENSITY_HIGH_DETAIL = "high_detail"

UI_DENSITY_OPTIONS: list[tuple[str, str]] = [
    (UI_DENSITY_STANDARD, "标准"),
    (UI_DENSITY_COMFORTABLE, "舒展"),
    (UI_DENSITY_HIGH_DETAIL, "高清细节"),
]
UI_DENSITY_LABELS = {value: label for value, label in UI_DENSITY_OPTIONS}

SCAN_MODE_OPTIONS: list[tuple[str, str]] = [
    (SCAN_MODE_ASK, "每次询问"),
    (SCAN_MODE_ALL, "扫描全部，包含子文件夹"),
    (SCAN_MODE_CURRENT_ONLY, "只扫描当前文件夹"),
    (SCAN_MODE_SUBDIRS_ONLY, "只扫描所有子文件夹"),
]
SCAN_MODE_LABELS = {value: label for value, label in SCAN_MODE_OPTIONS}

REPAIR_SUMMARY_FILTER_ALL = "all"
REPAIR_SUMMARY_FILTER_REPAIRED = "repaired"
REPAIR_SUMMARY_FILTER_SKIPPED = "skipped"
REPAIR_SUMMARY_FILTER_FAILED = "failed"
REPAIR_SUMMARY_FILTER_FORCED_UNSAVED = "forced_unsaved"
REPAIR_SUMMARY_FILTER_FORCED_SAVED = "forced_saved"
REPAIR_SUMMARY_FILTER_DISCARD_RELATED = "discard_related"
REPAIR_SUMMARY_FILTER_ROLLBACK_NOOP = "rollback_noop"

REPAIR_SUMMARY_FILTER_OPTIONS: list[tuple[str, str]] = [
    (REPAIR_SUMMARY_FILTER_ALL, "全部"),
    (REPAIR_SUMMARY_FILTER_REPAIRED, "已修复"),
    (REPAIR_SUMMARY_FILTER_SKIPPED, "已跳过"),
    (REPAIR_SUMMARY_FILTER_FAILED, "失败"),
    (REPAIR_SUMMARY_FILTER_FORCED_UNSAVED, "强制尝试但未保存"),
    (REPAIR_SUMMARY_FILTER_FORCED_SAVED, "强制尝试后保存"),
    (REPAIR_SUMMARY_FILTER_DISCARD_RELATED, "不适合保留相关"),
    (REPAIR_SUMMARY_FILTER_ROLLBACK_NOOP, "回退或未保存"),
]
REPAIR_SUMMARY_FILTER_LABELS = {value: label for value, label in REPAIR_SUMMARY_FILTER_OPTIONS}


def scan_mode_label(mode: str) -> str:
    return SCAN_MODE_LABELS.get(normalize_default_scan_mode(mode), str(mode or SCAN_MODE_ASK))


def repair_summary_filter_label(filter_id: str) -> str:
    return REPAIR_SUMMARY_FILTER_LABELS.get(
        normalize_repair_summary_filter(filter_id),
        REPAIR_SUMMARY_FILTER_LABELS[REPAIR_SUMMARY_FILTER_ALL],
    )


def _normalize_rule_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    if values is None or not isinstance(values, (list, tuple)):
        values = []
    for raw_value in list(values):
        value = str(raw_value).strip()
        if not value:
            continue
        lowered = value.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(value)
    return ordered


def normalize_scan_ignore_prefixes(prefixes: list[str] | tuple[str, ...] | None) -> list[str]:
    ordered = _normalize_rule_list(prefixes)
    seen = {value.casefold() for value in ordered}
    if "_repair".casefold() not in seen:
        ordered.insert(0, "_repair")
    return ordered or list(DEFAULT_SCAN_IGNORE_PREFIXES)


def normalize_scan_ignore_suffixes(suffixes: list[str] | tuple[str, ...] | None) -> list[str]:
    return _normalize_rule_list(suffixes)


def normalize_scan_ignore_contains(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return _normalize_rule_list(values)


def normalize_default_scan_mode(mode: str | None) -> str:
    normalized = str(mode or SCAN_MODE_ASK).strip().lower()
    allowed = {value for value, _label in SCAN_MODE_OPTIONS}
    return normalized if normalized in allowed else SCAN_MODE_ASK


def normalize_repair_summary_filter(filter_id: str | None) -> str:
    normalized = str(filter_id or REPAIR_SUMMARY_FILTER_ALL).strip().lower()
    allowed = {value for value, _label in REPAIR_SUMMARY_FILTER_OPTIONS}
    return normalized if normalized in allowed else REPAIR_SUMMARY_FILTER_ALL


def normalize_analysis_concurrency_mode(mode: str | None) -> str:
    normalized = str(mode or ANALYSIS_CONCURRENCY_AUTO).strip().lower()
    allowed = {value for value, _label in ANALYSIS_CONCURRENCY_OPTIONS}
    return normalized if normalized in allowed else ANALYSIS_CONCURRENCY_AUTO


def normalize_analysis_custom_workers(value: object) -> int:
    try:
        workers = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(max_analysis_workers(), workers))


def max_analysis_workers(*, cpu_count: int | None = None) -> int:
    cpus = max(1, int(cpu_count or os.cpu_count() or 4))
    return max(2, min(32, cpus * 2))


@dataclass(frozen=True)
class AnalysisWorkerPlan:
    mode: str
    requested_workers: int
    actual_workers: int
    reason: str = ""


def resolve_analysis_worker_plan(
    total_images: int,
    mode: str | None,
    custom_workers: object = 0,
    *,
    cpu_count: int | None = None,
) -> AnalysisWorkerPlan:
    total = max(1, int(total_images or 1))
    cpus = max(1, int(cpu_count or os.cpu_count() or 4))
    normalized_mode = normalize_analysis_concurrency_mode(mode)
    notes: list[str] = []

    limit = max_analysis_workers(cpu_count=cpus)

    if normalized_mode == ANALYSIS_CONCURRENCY_LOW:
        requested = max(1, min(2, cpus // 2 or 1))
    elif normalized_mode == ANALYSIS_CONCURRENCY_MEDIUM:
        requested = max(1, min(6, max(2, cpus // 2)))
    elif normalized_mode == ANALYSIS_CONCURRENCY_HIGH:
        requested = max(1, min(16, max(2, cpus + 2)))
    elif normalized_mode == ANALYSIS_CONCURRENCY_EXTREME:
        requested = max(2, min(limit, cpus * 2))
    elif normalized_mode == ANALYSIS_CONCURRENCY_CUSTOM:
        custom = normalize_analysis_custom_workers(custom_workers)
        if custom <= 0:
            requested = max(1, min(12, max(2, cpus)))
            notes.append("custom worker value is empty; using auto default")
        else:
            requested = min(custom, limit)
            if custom > limit:
                notes.append(f"limited by this computer ({limit})")
    else:
        requested = max(1, min(12, max(2, cpus)))

    actual = min(requested, total)
    if actual < requested:
        notes.append(f"limited by image count ({total})")
    return AnalysisWorkerPlan(
        mode=normalized_mode,
        requested_workers=requested,
        actual_workers=max(1, actual),
        reason="; ".join(notes),
    )


def normalize_gpu_acceleration_mode(mode: str | None) -> str:
    normalized = str(mode or GPU_ACCELERATION_OFF).strip().lower()
    allowed = {value for value, _label in GPU_ACCELERATION_OPTIONS}
    return normalized if normalized in allowed else GPU_ACCELERATION_OFF


def normalize_console_time_mode(mode: str | None) -> str:
    normalized = str(mode or CONSOLE_TIME_24H).strip().lower()
    allowed = {value for value, _label in CONSOLE_TIME_MODE_OPTIONS}
    return normalized if normalized in allowed else CONSOLE_TIME_24H


def normalize_theme_id(value: object) -> str:
    try:
        from ui.themes import normalize_theme_id as _normalize_theme_id
    except Exception:
        return "classic_green"
    return _normalize_theme_id(value)


def normalize_ui_density(value: object) -> str:
    normalized = str(value or UI_DENSITY_STANDARD).strip().lower()
    allowed = {value for value, _label in UI_DENSITY_OPTIONS}
    return normalized if normalized in allowed else UI_DENSITY_STANDARD


def normalize_settings_schema_version(value: object) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError):
        return SETTINGS_SCHEMA_VERSION
    return version if version > 0 else SETTINGS_SCHEMA_VERSION


@dataclass
class AppSettings:
    settings_schema_version: int = SETTINGS_SCHEMA_VERSION
    scan_ignore_prefixes: list[str] = field(default_factory=lambda: list(DEFAULT_SCAN_IGNORE_PREFIXES))
    scan_ignore_suffixes: list[str] = field(default_factory=lambda: list(DEFAULT_SCAN_IGNORE_SUFFIXES))
    scan_ignore_contains: list[str] = field(default_factory=lambda: list(DEFAULT_SCAN_IGNORE_CONTAINS))
    default_scan_mode: str = SCAN_MODE_ASK
    repair_summary_default_filter: str = REPAIR_SUMMARY_FILTER_ALL
    analysis_concurrency_mode: str = ANALYSIS_CONCURRENCY_AUTO
    analysis_custom_workers: int = 0
    gpu_acceleration_mode: str = GPU_ACCELERATION_OFF
    console_time_mode: str = CONSOLE_TIME_24H
    theme_id: str = "classic_green"
    ui_density: str = UI_DENSITY_STANDARD
    language: str = DEFAULT_LANGUAGE
    auto_check_updates: bool = True


def default_app_settings() -> AppSettings:
    return AppSettings()


def migrate_settings(old_version: int, data: dict[str, object]) -> dict[str, object]:
    migrated = dict(data)
    if old_version < 1:
        migrated["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    if old_version < 2:
        migrated.setdefault("console_time_mode", CONSOLE_TIME_24H)
        migrated.setdefault("theme_id", "classic_green")
    if old_version < 3:
        migrated.setdefault("auto_check_updates", True)
    if old_version < 4:
        migrated.pop("update_manifest_url", None)
        migrated.pop("cloud_messages_url", None)
    if old_version < 5:
        migrated.setdefault("language", DEFAULT_LANGUAGE)
    if old_version < 6:
        migrated.setdefault("scan_ignore_suffixes", list(DEFAULT_SCAN_IGNORE_SUFFIXES))
        migrated.setdefault("scan_ignore_contains", list(DEFAULT_SCAN_IGNORE_CONTAINS))
        migrated.setdefault("ui_density", UI_DENSITY_STANDARD)
    if old_version < 7:
        if migrated.get("analysis_concurrency_mode") == "very_high":
            migrated["analysis_concurrency_mode"] = ANALYSIS_CONCURRENCY_EXTREME
    return migrated


def validate_settings_payload(payload: object) -> AppSettings:
    if not isinstance(payload, dict):
        payload = {}
    old_version = normalize_settings_schema_version(payload.get("settings_schema_version", 0))
    payload = migrate_settings(old_version, payload)
    return AppSettings(
        settings_schema_version=SETTINGS_SCHEMA_VERSION,
        scan_ignore_prefixes=normalize_scan_ignore_prefixes(payload.get("scan_ignore_prefixes", DEFAULT_SCAN_IGNORE_PREFIXES)),
        scan_ignore_suffixes=normalize_scan_ignore_suffixes(
            payload.get("scan_ignore_suffixes", DEFAULT_SCAN_IGNORE_SUFFIXES)
        ),
        scan_ignore_contains=normalize_scan_ignore_contains(
            payload.get("scan_ignore_contains", DEFAULT_SCAN_IGNORE_CONTAINS)
        ),
        default_scan_mode=normalize_default_scan_mode(payload.get("default_scan_mode", SCAN_MODE_ASK)),
        repair_summary_default_filter=normalize_repair_summary_filter(
            payload.get("repair_summary_default_filter", REPAIR_SUMMARY_FILTER_ALL)
        ),
        analysis_concurrency_mode=normalize_analysis_concurrency_mode(
            payload.get("analysis_concurrency_mode", ANALYSIS_CONCURRENCY_AUTO)
        ),
        analysis_custom_workers=normalize_analysis_custom_workers(payload.get("analysis_custom_workers", 0)),
        gpu_acceleration_mode=normalize_gpu_acceleration_mode(payload.get("gpu_acceleration_mode", GPU_ACCELERATION_OFF)),
        console_time_mode=normalize_console_time_mode(payload.get("console_time_mode", CONSOLE_TIME_24H)),
        theme_id=normalize_theme_id(payload.get("theme_id", "classic_green")),
        ui_density=normalize_ui_density(payload.get("ui_density", UI_DENSITY_STANDARD)),
        language=normalize_language(payload.get("language", DEFAULT_LANGUAGE)),
        auto_check_updates=True,
    )


def settings_to_payload(settings: AppSettings) -> dict[str, object]:
    return asdict(validate_settings_payload(asdict(settings)))


def _backup_broken_settings(settings_path: Path, raw_text: str, report_warning: Callable[[str], None] | None) -> None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = settings_path.with_name(f"{settings_path.stem}.broken-{timestamp}{settings_path.suffix}")
    try:
        backup_path.write_text(raw_text, encoding="utf-8")
        if report_warning is not None:
            report_warning(f"app_settings.json 已损坏，已备份为：{backup_path.name}")
    except Exception as exc:
        if report_warning is not None:
            report_warning(f"app_settings.json 已损坏，但备份失败：{exc}")


def load_app_settings(
    *,
    settings_path: str | Path = SETTINGS_PATH,
    report_warning: Callable[[str], None] | None = None,
    create_if_missing: bool = True,
) -> AppSettings:
    path = Path(settings_path)
    defaults = default_app_settings()
    if not path.exists():
        if create_if_missing:
            save_app_settings(defaults, settings_path=path, report_warning=report_warning)
            if report_warning is not None:
                report_warning("app_settings.json 不存在，已按默认设置创建。")
        return defaults

    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except Exception as exc:
        raw_text = ""
        try:
            raw_text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        _backup_broken_settings(path, raw_text, report_warning)
        if report_warning is not None:
            report_warning(f"app_settings.json 读取失败，已回退默认设置：{exc}")
        if create_if_missing:
            save_app_settings(defaults, settings_path=path, report_warning=report_warning)
        return defaults

    settings = validate_settings_payload(payload)
    if create_if_missing:
        try:
            normalized_payload = settings_to_payload(settings)
            current_payload = payload if isinstance(payload, dict) else {}
            if normalized_payload != current_payload:
                save_app_settings(settings, settings_path=path, report_warning=report_warning)
        except Exception as exc:
            if report_warning is not None:
                report_warning(f"规范化设置文件失败，将继续使用内存设置：{exc}")
    return settings


def save_app_settings(
    settings: AppSettings,
    *,
    settings_path: str | Path = SETTINGS_PATH,
    report_warning: Callable[[str], None] | None = None,
) -> None:
    path = Path(settings_path)
    normalized = validate_settings_payload(asdict(settings))
    try:
        path.write_text(json.dumps(asdict(normalized), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        if report_warning is not None:
            report_warning(f"保存 app_settings.json 失败：{exc}")
        raise
