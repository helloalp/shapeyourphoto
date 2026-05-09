from __future__ import annotations

from collections.abc import Iterable

from app_settings import (
    ANALYSIS_CONCURRENCY_LABELS,
    CONSOLE_TIME_MODE_LABELS,
    GPU_ACCELERATION_LABELS,
    SCAN_MODE_LABELS,
)
from repair_planner import REPAIR_METHOD_MAP


ISSUE_CODE_LABELS = {
    "overexposed": "过曝 / 高光过亮",
    "underexposed": "欠曝 / 暗部不足",
    "low_contrast": "对比度偏低",
    "flat_tone": "层次偏平",
    "muted_colors": "色彩偏淡",
    "over_saturated": "色彩过饱和",
    "out_of_focus": "清晰度不足",
    "portrait_out_of_focus": "人像主体虚焦",
    "high_noise": "噪点偏高",
    "color_cast": "色偏",
}

SCENE_TYPE_LABELS = {
    "generic_scene": "普通场景",
    "portrait_scene": "人像场景",
    "artwork_scene": "画作/海报人脸场景",
    "people_context_scene": "人物背影/侧背场景",
    "silhouette_scene": "剪影场景",
    "high_contrast_window_scene": "高反差窗景",
    "low_key_scene": "低调氛围场景",
    "architecture_scene": "建筑/结构场景",
    "architecture_vivid_scene": "高饱和建筑场景",
    "natural_vivid_scene": "自然高饱和场景",
}

PORTRAIT_TYPE_LABELS = {
    "non_portrait": "非人像",
    "real_multi_portrait": "多人真实人像",
    "real_frontal_portrait": "正面真实人像",
    "real_near_frontal_portrait": "近正面真实人像",
    "artwork_face_context": "画作/海报人脸",
    "side_back_view_person": "侧背身人物",
    "back_view_person_context": "背身人物",
}

EXPOSURE_TYPE_LABELS = {
    "normal": "曝光正常",
    "underexposed": "欠曝",
    "overexposed_recoverable": "过曝但可尝试恢复",
    "overexposed_unrecoverable": "过曝且高光不可恢复",
    "silhouette_scene": "剪影曝光",
    "high_contrast_window_scene": "高反差窗景曝光",
    "low_key_scene": "低调曝光",
}

COLOR_TYPE_LABELS = {
    "balanced": "色彩平衡",
    "muted_problem": "色彩偏淡",
    "restrained_natural": "自然克制色彩",
    "oversaturated_problem": "色彩过饱和",
    "natural_vivid": "自然高饱和",
}

PORTRAIT_SCENE_LABELS = {
    "non_portrait": "非人像",
    "normal_portrait": "普通人像",
    "multi_person_portrait": "多人像",
    "backlit_portrait": "逆光人像",
    "high_key_portrait": "高调背景人像",
    "dark_background_portrait": "暗背景人像",
}

REPAIR_POLICY_LABELS = {
    "standard": "标准修复",
    "gentle_subject_lift_protect_background": "轻提主体并保护背景",
    "gentle_subject_lift": "轻提主体",
    "protect_face_and_high_key_background": "保护面部与高调背景",
    "protect_face_highlights": "保护面部高光",
    "local_subject_preserve_dark_background": "局部增强主体并保留暗背景",
    "local_subject_enhance_protect_high_key_background": "局部增强主体并保护高调背景",
    "local_portrait_enhance_only": "仅做人像局部增强",
}

OUTCOME_LABELS = {
    "normal_saved": "正常修复并保存",
    "forced_saved": "强制尝试后保存",
    "forced_rollback": "强制尝试后回退",
    "forced_skip_unsuitable": "强制尝试后仍跳过",
    "discard_candidate_skipped": "清理候选默认跳过",
    "normal_skipped": "常规跳过 / no-op",
    "failed": "失败",
    "skipped": "已跳过",
    "rollback": "已回退",
    "noop": "无收益 no-op",
}

PERF_STAGE_LABELS = {
    "image_read": "读取图片",
    "image_open": "打开图片",
    "exif_transpose": "应用 EXIF 方向",
    "image_convert": "转换色彩模式",
    "resize": "生成工作尺寸",
    "working_resize": "生成工作尺寸",
    "array_convert": "像素数组转换",
    "basic_stats": "基础统计",
    "exposure": "曝光分析",
    "color": "色彩分析",
    "sharpness": "清晰度分析",
    "noise": "噪点分析",
    "scene_classify": "场景判断",
    "face_detect": "人脸候选检测",
    "portrait_region_build": "人像区域构建",
    "quality_stats": "质量统计",
    "issue_build": "问题与建议生成",
    "cleanup_candidate": "清理候选判断",
    "similar_detection": "相似图检测",
    "ui_refresh": "UI 刷新",
    "UI_update": "UI 刷新",
    "console_flush": "Console 刷新",
    "planner": "生成修复方案",
    "candidate_generation": "生成修复候选",
    "candidate_scoring": "候选评分",
    "mask_build": "构建局部蒙版",
    "mask_feather": "蒙版羽化",
    "save_output": "保存输出",
    "metadata_preserve": "保留元数据",
}


def display_name(kind: str, value: object, *, unknown_prefix: str = "未知类型") -> str:
    raw = "" if value is None else str(value)
    tables = {
        "issue": ISSUE_CODE_LABELS,
        "scene_type": SCENE_TYPE_LABELS,
        "portrait_type": PORTRAIT_TYPE_LABELS,
        "portrait_scene_type": PORTRAIT_SCENE_LABELS,
        "exposure_type": EXPOSURE_TYPE_LABELS,
        "color_type": COLOR_TYPE_LABELS,
        "repair_policy": REPAIR_POLICY_LABELS,
        "outcome": OUTCOME_LABELS,
        "scan_mode": SCAN_MODE_LABELS,
        "worker": ANALYSIS_CONCURRENCY_LABELS,
        "gpu": GPU_ACCELERATION_LABELS,
        "console_time_mode": CONSOLE_TIME_MODE_LABELS,
        "perf_stage": PERF_STAGE_LABELS,
    }
    if kind == "repair_method":
        method = REPAIR_METHOD_MAP.get(raw)
        return method.label if method is not None else _unknown(unknown_prefix, raw)
    table = tables.get(kind, {})
    return table.get(raw, _unknown(unknown_prefix, raw))


def display_names(kind: str, values: Iterable[object]) -> list[str]:
    return [display_name(kind, value) for value in values]


def issue_display(issue) -> str:
    code = getattr(issue, "code", "")
    label = getattr(issue, "label", "")
    mapped = display_name("issue", code)
    if mapped.startswith("未知类型") and label:
        return str(label)
    return mapped


def _unknown(prefix: str, raw: str) -> str:
    return f"{prefix}（{raw}）" if raw else prefix
