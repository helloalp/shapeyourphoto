from __future__ import annotations

import os


FILTER_OPTIONS = [
    "全部",
    "仅问题图",
    "过曝",
    "欠曝",
    "低对比",
    "色彩寡淡",
    "过饱和",
    "虚焦",
    "噪点偏高",
    "色偏",
    "人像主体虚焦",
]

ANALYSIS_PROGRESS_STEPS = 5
DEFAULT_ANALYSIS_WORKERS = max(1, min(12, os.cpu_count() or 4))
DEFAULT_REPAIR_WORKERS = max(1, min(4, max(1, (os.cpu_count() or 4) // 2)))
ANALYSIS_TIMING_LABELS = [
    ("读取图片", ("image_read",)),
    ("打开图片", ("image_open",)),
    ("EXIF 方向处理", ("exif_transpose",)),
    ("转换色彩模式", ("image_convert",)),
    ("生成工作尺寸", ("resize", "working_resize")),
    ("像素数组转换", ("array_convert",)),
    ("Native GPU 亮度统计", ("gpu_luma_stats",)),
    ("曝光", ("exposure",)),
    ("色彩", ("color",)),
    ("清晰度", ("sharpness",)),
    ("噪点", ("noise",)),
    ("场景判断", ("scene_classify",)),
    ("人脸/人像/质量/问题生成", ("face_detect", "portrait_region_build", "quality_stats", "issue_build")),
    ("人像区域", ("face_detect", "portrait_region_build")),
    ("不适合保留判断", ("cleanup_candidate",)),
]
ANALYSIS_BATCH_TIMING_LABELS = ANALYSIS_TIMING_LABELS + [
    ("相似图检测", ("similar_detection",)),
    ("缩略图/预览/UI", ("thumbnail", "preview", "ui_refresh", "UI_update", "ui_update")),
    ("Console 刷新", ("console_flush",)),
]
REPAIR_TIMING_LABELS = [
    ("生成修复方案", ("planner",)),
    ("读取图片", ("image_read",)),
    ("执行修复操作", ("candidate_generation", "op:auto_tone", "op:recover_highlights", "op:lift_shadows", "op:boost_contrast", "op:boost_vibrance", "op:reduce_saturation", "op:warm_up", "op:cool_down", "op:add_magenta", "op:add_green", "op:boost_clarity", "op:reduce_noise", "op:portrait_local_face_enhance", "op:portrait_subject_midcontrast", "op:portrait_dark_clothing_detail", "op:protect_high_key_background")),
    ("候选评分/蒙版", ("candidate_scoring", "mask_build", "mask_feather")),
    ("保存输出", ("save_output",)),
    ("保留元数据", ("metadata_preserve",)),
]


class AnalysisCanceled(Exception):
    pass
