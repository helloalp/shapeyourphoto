from __future__ import annotations

from collections.abc import Iterable

from repair_planner import REPAIR_METHOD_MAP
from ui.language import DEFAULT_LANGUAGE, get_current_language, normalize_language


ISSUE_CODE_LABELS_ZH = {
    "overexposed": "过曝 / 高光过亮",
    "underexposed": "欠曝 / 暗部不足",
    "low_contrast": "对比度偏低",
    "flat_tone": "层次偏平",
    "muted_colors": "色彩偏淡",
    "over_saturated": "色彩过饱和",
    "out_of_focus": "清晰度不足",
    "portrait_out_of_focus": "人像主体虚焦",
    "global_out_of_focus": "整张图片严重模糊",
    "severe_overexposed": "严重过度曝光",
    "severe_underexposed": "严重曝光不足",
    "high_noise": "噪点偏高",
    "color_cast": "色偏",
    "local_overexposure": "局部高光偏亮",
    "local_underexposure": "局部暗部偏沉",
    "haze_flat": "画面灰雾感",
}

ISSUE_CODE_LABELS_EN = {
    "overexposed": "Overexposed / highlights too bright",
    "underexposed": "Underexposed / shadows too dark",
    "low_contrast": "Low contrast",
    "flat_tone": "Flat tone",
    "muted_colors": "Muted colors",
    "over_saturated": "Oversaturated colors",
    "out_of_focus": "Not sharp enough",
    "portrait_out_of_focus": "Portrait subject out of focus",
    "global_out_of_focus": "Whole image severely blurred",
    "severe_overexposed": "Severely overexposed",
    "severe_underexposed": "Severely underexposed",
    "high_noise": "High noise",
    "color_cast": "Color cast",
    "local_overexposure": "Local highlights too bright",
    "local_underexposure": "Local shadows too dark",
    "haze_flat": "Hazy or flat image",
}

CLEANUP_REASON_LABELS_ZH = {
    "portrait_out_of_focus": "人像主体严重虚焦",
    "global_out_of_focus": "整张图片严重模糊",
    "severe_overexposed": "严重过度曝光",
    "severe_underexposed": "严重曝光不足",
}

CLEANUP_REASON_LABELS_EN = {
    "portrait_out_of_focus": "Portrait subject is severely out of focus",
    "global_out_of_focus": "Whole image is severely blurred",
    "severe_overexposed": "Severely overexposed",
    "severe_underexposed": "Severely underexposed",
}

SEVERITY_LABELS_ZH = {
    "low": "一般",
    "medium": "较严重",
    "high": "严重",
    "critical": "极其严重",
    "warning": "需留意",
    "severe": "严重",
}

SEVERITY_LABELS_EN = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "critical": "Critical",
    "warning": "Warning",
    "severe": "Severe",
}

STATUS_LABELS_ZH = {
    "pending": "待定",
    "selected": "已选",
    "current": "当前",
    "done": "已完成",
    "failed": "失败",
    "skipped": "已跳过",
}

STATUS_LABELS_EN = {
    "pending": "Pending",
    "selected": "Selected",
    "current": "Current",
    "done": "Done",
    "failed": "Failed",
    "skipped": "Skipped",
}

ISSUE_CODE_LABELS_JA = {
    "overexposed": "露出オーバー / ハイライト過多",
    "underexposed": "露出不足 / 暗部不足",
    "low_contrast": "コントラスト低め",
    "flat_tone": "階調が平坦",
    "muted_colors": "色が淡い",
    "over_saturated": "彩度が高すぎる",
    "out_of_focus": "シャープさ不足",
    "portrait_out_of_focus": "人物主体のピント不足",
    "global_out_of_focus": "画像全体が大きくぼけています",
    "severe_overexposed": "深刻な露出オーバー",
    "severe_underexposed": "深刻な露出不足",
    "high_noise": "ノイズ多め",
    "color_cast": "色かぶり",
    "local_overexposure": "局所的なハイライト過多",
    "local_underexposure": "局所的な暗部沈み",
    "haze_flat": "かすみ・抜け不足",
}

CLEANUP_REASON_LABELS_JA = {
    "portrait_out_of_focus": "人物主体のピントが大きく外れています",
    "global_out_of_focus": "画像全体が大きくぼけています",
    "severe_overexposed": "深刻な露出オーバー",
    "severe_underexposed": "深刻な露出不足",
}

STATUS_LABELS_JA = {
    "pending": "保留中",
    "selected": "選択済み",
    "current": "現在",
    "done": "完了",
    "failed": "失敗",
    "skipped": "スキップ済み",
}

SCENE_TYPE_LABELS_ZH = {
    "generic_scene": "普通场景",
    "portrait_scene": "人像场景",
    "artwork_scene": "画作/海报人脸场景",
    "people_context_scene": "人物背景/侧背场景",
    "silhouette_scene": "剪影场景",
    "high_contrast_window_scene": "高反差窗景",
    "low_key_scene": "低调氛围场景",
    "architecture_scene": "建筑/结构场景",
    "architecture_vivid_scene": "高饱和建筑场景",
    "natural_vivid_scene": "自然高饱和场景",
    "water_sky_landscape_scene": "天空/水面风景",
    "foliage_scene": "绿植场景",
    "hazy_scene": "灰雾低通透场景",
}

SCENE_TYPE_LABELS_EN = {
    "generic_scene": "General scene",
    "portrait_scene": "Portrait scene",
    "artwork_scene": "Artwork/poster face scene",
    "people_context_scene": "People context scene",
    "silhouette_scene": "Silhouette scene",
    "high_contrast_window_scene": "High-contrast window scene",
    "low_key_scene": "Low-key scene",
    "architecture_scene": "Architecture/structure scene",
    "architecture_vivid_scene": "Vivid architecture scene",
    "natural_vivid_scene": "Naturally vivid scene",
    "water_sky_landscape_scene": "Sky/water landscape",
    "foliage_scene": "Foliage scene",
    "hazy_scene": "Hazy low-clarity scene",
}

SCENE_TYPE_LABELS_JA = {
    "generic_scene": "一般シーン",
    "portrait_scene": "人物シーン",
    "artwork_scene": "絵画/ポスター人物シーン",
    "people_context_scene": "人物文脈シーン",
    "silhouette_scene": "シルエットシーン",
    "high_contrast_window_scene": "高コントラスト窓景",
    "low_key_scene": "ローキーシーン",
    "architecture_scene": "建築/構造シーン",
    "architecture_vivid_scene": "鮮やかな建築シーン",
    "natural_vivid_scene": "自然な高彩度シーン",
    "water_sky_landscape_scene": "空/水面の風景",
    "foliage_scene": "緑の多いシーン",
    "hazy_scene": "かすみ・低明瞭シーン",
}

PORTRAIT_TYPE_LABELS_ZH = {
    "non_portrait": "非人像",
    "real_multi_portrait": "多人真实人像",
    "real_frontal_portrait": "正面真实人像",
    "real_near_frontal_portrait": "近正面真实人像",
    "artwork_face_context": "画作/海报人脸",
    "side_back_view_person": "侧背身人物",
    "back_view_person_context": "背身人物",
}

PORTRAIT_TYPE_LABELS_EN = {
    "non_portrait": "Non-portrait",
    "real_multi_portrait": "Real multi-person portrait",
    "real_frontal_portrait": "Real frontal portrait",
    "real_near_frontal_portrait": "Real near-frontal portrait",
    "artwork_face_context": "Artwork/poster face",
    "side_back_view_person": "Side/back-view person",
    "back_view_person_context": "Back-view person",
}

EXPOSURE_TYPE_LABELS_ZH = {
    "normal": "曝光正常",
    "underexposed": "欠曝",
    "overexposed_recoverable": "过曝但可尝试恢复",
    "overexposed_unrecoverable": "过曝且高光不可恢复",
    "silhouette_scene": "剪影曝光",
    "high_contrast_window_scene": "高反差窗景曝光",
    "low_key_scene": "低调曝光",
}

EXPOSURE_TYPE_LABELS_EN = {
    "normal": "Normal exposure",
    "underexposed": "Underexposed",
    "overexposed_recoverable": "Overexposed but recoverable",
    "overexposed_unrecoverable": "Overexposed with unrecoverable highlights",
    "silhouette_scene": "Silhouette exposure",
    "high_contrast_window_scene": "High-contrast window exposure",
    "low_key_scene": "Low-key exposure",
}

COLOR_TYPE_LABELS_ZH = {
    "balanced": "色彩平衡",
    "muted_problem": "色彩偏淡",
    "restrained_natural": "自然克制色彩",
    "oversaturated_problem": "色彩过饱和",
    "natural_vivid": "自然高饱和",
}

COLOR_TYPE_LABELS_EN = {
    "balanced": "Balanced color",
    "muted_problem": "Muted color",
    "restrained_natural": "Restrained natural color",
    "oversaturated_problem": "Oversaturated color",
    "natural_vivid": "Naturally vivid color",
}

PORTRAIT_SCENE_LABELS_ZH = {
    "non_portrait": "非人像",
    "normal_portrait": "普通人像",
    "multi_person_portrait": "多人像",
    "backlit_portrait": "逆光人像",
    "high_key_portrait": "高调背景人像",
    "dark_background_portrait": "暗背景人像",
}

PORTRAIT_SCENE_LABELS_EN = {
    "non_portrait": "Non-portrait",
    "normal_portrait": "Normal portrait",
    "multi_person_portrait": "Multi-person portrait",
    "backlit_portrait": "Backlit portrait",
    "high_key_portrait": "High-key background portrait",
    "dark_background_portrait": "Dark background portrait",
}

REPAIR_POLICY_LABELS_ZH = {
    "standard": "标准修复",
    "gentle_subject_lift_protect_background": "轻提主体并保护背景",
    "gentle_subject_lift": "轻提主体",
    "protect_face_and_high_key_background": "保护面部与高调背景",
    "protect_face_highlights": "保护面部高光",
    "local_subject_preserve_dark_background": "局部增强主体并保留暗背景",
    "local_subject_enhance_protect_high_key_background": "局部增强主体并保护高调背景",
    "local_portrait_enhance_only": "仅做人像局部增强",
}

REPAIR_POLICY_LABELS_EN = {
    "standard": "Standard repair",
    "gentle_subject_lift_protect_background": "Gentle subject lift with background protection",
    "gentle_subject_lift": "Gentle subject lift",
    "protect_face_and_high_key_background": "Protect face and high-key background",
    "protect_face_highlights": "Protect facial highlights",
    "local_subject_preserve_dark_background": "Local subject enhancement with dark background preserved",
    "local_subject_enhance_protect_high_key_background": "Local subject enhancement with high-key background protection",
    "local_portrait_enhance_only": "Local portrait enhancement only",
}

OUTCOME_LABELS_ZH = {
    "normal_saved": "正常修复并保存",
    "forced_saved": "强制尝试后保存",
    "forced_rollback": "强制尝试后回退",
    "forced_skip_unsuitable": "强制尝试后仍跳过",
    "discard_candidate_skipped": "不适合保留图片已跳过",
    "normal_skipped": "未保存新图片",
    "failed": "失败",
    "skipped": "已跳过",
    "rollback": "已回退",
    "noop": "未保存新图片",
}

OUTCOME_LABELS_EN = {
    "normal_saved": "Repaired and saved",
    "forced_saved": "Saved after forced attempt",
    "forced_rollback": "Rolled back after forced attempt",
    "forced_skip_unsuitable": "Still skipped after forced attempt",
    "discard_candidate_skipped": "Unsuitable image skipped",
    "normal_skipped": "No new image saved",
    "failed": "Failed",
    "skipped": "Skipped",
    "rollback": "Rolled back",
    "noop": "No new image saved",
}

SCAN_MODE_LABELS_ZH = {
    "ask": "每次询问",
    "all": "扫描全部，包含子文件夹",
    "current_only": "只扫描当前文件夹",
    "subdirs_only": "只扫描子文件夹",
}

SCAN_MODE_LABELS_EN = {
    "ask": "Ask each time",
    "all": "Scan all, including subfolders",
    "current_only": "Scan current folder only",
    "subdirs_only": "Scan subfolders only",
}

WORKER_LABELS_ZH = {
    "auto": "自动",
    "low": "低",
    "medium": "中",
    "high": "高",
    "extreme": "极高",
    "custom": "自定义同时处理数量",
}

WORKER_LABELS_EN = {
    "auto": "Auto",
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "extreme": "Extreme",
    "custom": "Custom worker count",
}

GPU_LABELS_ZH = {"off": "关闭", "auto": "自动", "on": "开启"}
GPU_LABELS_EN = {"off": "Off", "auto": "Auto", "on": "On"}
GPU_LABELS_JA = {"off": "オフ", "auto": "自動", "on": "オン"}

CONSOLE_TIME_MODE_LABELS_ZH = {
    "24h": "24 小时制 [20:28:14]",
    "12h": "12 小时制 [08:28:14 PM]",
    "24h_tz": "24 小时制 + 时区 [20:28:14 UTC+09:00]",
    "elapsed": "启动后经过时间 [T+00:20:28]",
}

CONSOLE_TIME_MODE_LABELS_EN = {
    "24h": "24-hour time [20:28:14]",
    "12h": "12-hour time [08:28:14 PM]",
    "24h_tz": "24-hour time + timezone [20:28:14 UTC+09:00]",
    "elapsed": "Elapsed since launch [T+00:20:28]",
}

PERF_STAGE_LABELS_ZH = {
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
    "cleanup_candidate": "不适合保留判断",
    "similar_detection": "相似图检测",
    "ui_refresh": "界面刷新",
    "UI_update": "界面刷新",
    "console_flush": "Console 刷新",
    "planner": "生成修复方案",
    "candidate_generation": "生成修复方案",
    "candidate_scoring": "选择修复方案",
    "mask_build": "构建局部蒙版",
    "mask_feather": "蒙版羽化",
    "save_output": "保存输出",
    "metadata_preserve": "保留元数据",
}

PERF_STAGE_LABELS_EN = {
    "image_read": "Read image",
    "image_open": "Open image",
    "exif_transpose": "Apply EXIF orientation",
    "image_convert": "Convert color mode",
    "resize": "Build working size",
    "working_resize": "Build working size",
    "array_convert": "Convert pixel array",
    "basic_stats": "Basic statistics",
    "exposure": "Exposure analysis",
    "color": "Color analysis",
    "sharpness": "Sharpness analysis",
    "noise": "Noise analysis",
    "scene_classify": "Scene classification",
    "face_detect": "Face candidate detection",
    "portrait_region_build": "Build portrait region",
    "quality_stats": "Quality statistics",
    "issue_build": "Build issues and suggestions",
    "cleanup_candidate": "Unsuitable image check",
    "similar_detection": "Similar image detection",
    "ui_refresh": "UI refresh",
    "UI_update": "UI refresh",
    "console_flush": "Console refresh",
    "planner": "Build repair plan",
    "candidate_generation": "Build repair plan",
    "candidate_scoring": "Choose repair candidate",
    "mask_build": "Build local mask",
    "mask_feather": "Feather mask",
    "save_output": "Save output",
    "metadata_preserve": "Preserve metadata",
}

REPAIR_METHOD_LABELS_EN = {
    "auto_tone": "Auto tone correction",
    "recover_highlights": "Recover highlights",
    "lift_shadows": "Lift shadows",
    "boost_contrast": "Boost contrast",
    "boost_vibrance": "Boost natural saturation",
    "reduce_saturation": "Reduce saturation",
    "boost_clarity": "Boost clarity",
    "reduce_noise": "Adaptive noise reduction",
    "cool_down": "Cool down / reduce warm cast",
    "warm_up": "Warm up / reduce cool cast",
    "add_magenta": "Add magenta / reduce green cast",
    "add_green": "Add green / reduce magenta cast",
    "portrait_local_face_enhance": "Local face enhancement",
    "portrait_subject_midcontrast": "Portrait midtone contrast",
    "portrait_dark_clothing_detail": "Dark clothing detail enhancement",
    "protect_high_key_background": "Protect high-key background",
    "dehaze_midtones": "Light dehaze",
    "protect_sky_water": "Protect sky and water",
    "foliage_balance": "Foliage color balance",
}

REPAIR_METHOD_LABELS_JA = {
    "auto_tone": "自動階調補正",
    "recover_highlights": "ハイライト回復",
    "lift_shadows": "暗部を持ち上げる",
    "boost_contrast": "コントラスト強化",
    "boost_vibrance": "自然な彩度を強化",
    "reduce_saturation": "彩度を下げる",
    "boost_clarity": "明瞭度を強化",
    "reduce_noise": "適応ノイズ低減",
    "cool_down": "色温度を下げる / 暖色かぶりを抑える",
    "warm_up": "色温度を上げる / 寒色かぶりを抑える",
    "add_magenta": "マゼンタを補う / 緑かぶりを抑える",
    "add_green": "緑を補う / マゼンタかぶりを抑える",
    "portrait_local_face_enhance": "顔の局所強化",
    "portrait_subject_midcontrast": "人物中間調コントラスト",
    "portrait_dark_clothing_detail": "暗い服のディテール強化",
    "protect_high_key_background": "ハイキー背景を保護",
    "dehaze_midtones": "軽いかすみ除去",
    "protect_sky_water": "空と水面を保護",
    "foliage_balance": "緑の色バランス",
}

_TABLES = {
    DEFAULT_LANGUAGE: {
        "issue": ISSUE_CODE_LABELS_ZH,
        "cleanup_reason": CLEANUP_REASON_LABELS_ZH,
        "severity": SEVERITY_LABELS_ZH,
        "status": STATUS_LABELS_ZH,
        "scene_type": SCENE_TYPE_LABELS_ZH,
        "portrait_type": PORTRAIT_TYPE_LABELS_ZH,
        "portrait_scene_type": PORTRAIT_SCENE_LABELS_ZH,
        "exposure_type": EXPOSURE_TYPE_LABELS_ZH,
        "color_type": COLOR_TYPE_LABELS_ZH,
        "repair_policy": REPAIR_POLICY_LABELS_ZH,
        "outcome": OUTCOME_LABELS_ZH,
        "scan_mode": SCAN_MODE_LABELS_ZH,
        "worker": WORKER_LABELS_ZH,
        "gpu": GPU_LABELS_ZH,
        "console_time_mode": CONSOLE_TIME_MODE_LABELS_ZH,
        "perf_stage": PERF_STAGE_LABELS_ZH,
    },
    "en_US": {
        "issue": ISSUE_CODE_LABELS_EN,
        "cleanup_reason": CLEANUP_REASON_LABELS_EN,
        "severity": SEVERITY_LABELS_EN,
        "status": STATUS_LABELS_EN,
        "scene_type": SCENE_TYPE_LABELS_EN,
        "portrait_type": PORTRAIT_TYPE_LABELS_EN,
        "portrait_scene_type": PORTRAIT_SCENE_LABELS_EN,
        "exposure_type": EXPOSURE_TYPE_LABELS_EN,
        "color_type": COLOR_TYPE_LABELS_EN,
        "repair_policy": REPAIR_POLICY_LABELS_EN,
        "outcome": OUTCOME_LABELS_EN,
        "scan_mode": SCAN_MODE_LABELS_EN,
        "worker": WORKER_LABELS_EN,
        "gpu": GPU_LABELS_EN,
        "console_time_mode": CONSOLE_TIME_MODE_LABELS_EN,
        "perf_stage": PERF_STAGE_LABELS_EN,
    },
    "ja_JP": {
        "issue": ISSUE_CODE_LABELS_JA,
        "cleanup_reason": CLEANUP_REASON_LABELS_JA,
        "severity": {
            "low": "低",
            "medium": "中",
            "high": "高",
            "critical": "重大",
            "warning": "注意",
            "severe": "深刻",
        },
        "status": STATUS_LABELS_JA,
        "scene_type": SCENE_TYPE_LABELS_JA,
        "portrait_type": PORTRAIT_TYPE_LABELS_EN,
        "portrait_scene_type": PORTRAIT_SCENE_LABELS_EN,
        "exposure_type": EXPOSURE_TYPE_LABELS_EN,
        "color_type": COLOR_TYPE_LABELS_EN,
        "repair_policy": REPAIR_POLICY_LABELS_EN,
        "outcome": OUTCOME_LABELS_EN,
        "scan_mode": {
            "ask": "毎回確認",
            "all": "すべてスキャン（サブフォルダーを含む）",
            "current_only": "現在のフォルダーのみ",
            "subdirs_only": "サブフォルダーのみ",
        },
        "worker": {
            "auto": "自動",
            "low": "低",
            "medium": "中",
            "high": "高",
            "extreme": "極高",
            "custom": "同時処理数を指定",
        },
        "gpu": GPU_LABELS_JA,
        "console_time_mode": CONSOLE_TIME_MODE_LABELS_EN,
        "perf_stage": PERF_STAGE_LABELS_EN,
    },
}

_UNKNOWN_PREFIX = {
    DEFAULT_LANGUAGE: "未知类型",
    "en_US": "Unknown type",
    "ja_JP": "不明な種類",
}


def _language_tables() -> dict[str, dict[str, str]]:
    return _TABLES.get(normalize_language(get_current_language()), _TABLES[DEFAULT_LANGUAGE])


def _table(kind: str) -> dict[str, str]:
    return _language_tables().get(kind, {})


def display_name(kind: str, value: object, *, unknown_prefix: str | None = None) -> str:
    raw = "" if value is None else str(value)
    lang = normalize_language(get_current_language())
    prefix = unknown_prefix or _UNKNOWN_PREFIX.get(lang, _UNKNOWN_PREFIX[DEFAULT_LANGUAGE])
    if kind == "repair_method":
        if lang == "en_US" and raw in REPAIR_METHOD_LABELS_EN:
            return REPAIR_METHOD_LABELS_EN[raw]
        if lang == "ja_JP" and raw in REPAIR_METHOD_LABELS_JA:
            return REPAIR_METHOD_LABELS_JA[raw]
        method = REPAIR_METHOD_MAP.get(raw)
        return method.label if method is not None else _unknown(prefix, raw)
    table = _table(kind)
    return table.get(raw, _unknown(prefix, raw))


def display_names(kind: str, values: Iterable[object]) -> list[str]:
    return [display_name(kind, value) for value in values]


def issue_display(issue) -> str:
    code = getattr(issue, "code", "")
    label = getattr(issue, "label", "")
    raw = "" if code is None else str(code)
    table = _table("issue")
    if raw in table:
        return table[raw]
    return str(label) if label else _unknown(_UNKNOWN_PREFIX[DEFAULT_LANGUAGE], raw)


def _unknown(prefix: str, raw: str) -> str:
    return f"{prefix}（{raw}）" if raw else prefix
