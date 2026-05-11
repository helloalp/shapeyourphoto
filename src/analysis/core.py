from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageOps

from models import AnalysisResult, Issue

from .common import (
    SUPPORTED_EXTENSIONS,
    add_timing,
    component_boxes,
    cleanup_binary_mask,
    describe_color_cast,
    edge_density,
    hue_entropy,
    hue_map,
    issue,
    local_range,
    masked_mean,
    masked_percentile,
    metric,
    sanitize_issues,
    saturation_map,
    skin_ratio,
    tile_sharpness,
)
from .discard import build_cleanup_candidates
from .portrait import analyze_portrait_regions, confirm_portrait, detect_portrait_regions


ANALYSIS_WORKING_MAX_SIDE = 4096


def _working_image_from_rgb(
    image: Image.Image,
    perf_timings: dict[str, float],
) -> tuple[Image.Image, tuple[int, int], tuple[int, int], bool]:
    import time

    original_size = image.size
    longest = max(original_size)
    if longest <= ANALYSIS_WORKING_MAX_SIDE:
        return image, original_size, original_size, False

    scale = ANALYSIS_WORKING_MAX_SIDE / float(longest)
    working_size = (
        max(1, int(round(original_size[0] * scale))),
        max(1, int(round(original_size[1] * scale))),
    )
    started_at = time.perf_counter()
    working = image.resize(working_size, Image.Resampling.BILINEAR)
    add_timing(perf_timings, "resize", started_at)
    return working, original_size, working_size, True


def _scale_box_to_original(
    box: tuple[int, int, int, int],
    scale_x: float,
    scale_y: float,
    original_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    original_w, original_h = original_size
    x0, y0, x1, y1 = box
    return (
        max(0, min(original_w, int(round(x0 * scale_x)))),
        max(0, min(original_h, int(round(y0 * scale_y)))),
        max(0, min(original_w, int(round(x1 * scale_x)))),
        max(0, min(original_h, int(round(y1 * scale_y)))),
    )


def _scale_region_to_original(
    region: tuple[int, int, int, int] | None,
    scale_x: float,
    scale_y: float,
    original_size: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    if region is None:
        return None
    return _scale_box_to_original(region, scale_x, scale_y, original_size)


def _scale_boxes_to_original(
    boxes: list[tuple[int, int, int, int]],
    scale_x: float,
    scale_y: float,
    original_size: tuple[int, int],
) -> list[tuple[int, int, int, int]]:
    return [_scale_box_to_original(box, scale_x, scale_y, original_size) for box in boxes]


def _bright_component_stats(mask: np.ndarray) -> tuple[float, bool, float]:
    cleaned = cleanup_binary_mask(mask)
    components = component_boxes(cleaned)
    if not components:
        return 0.0, False, 0.0
    total = float(mask.shape[0] * mask.shape[1])
    best_ratio = 0.0
    border_touch = False
    best_rect = 0.0
    for x0, y0, x1, y1, area in components:
        ratio = area / max(1.0, total)
        if ratio < best_ratio:
            continue
        best_ratio = ratio
        border_touch = x0 <= 1 or y0 <= 1 or x1 >= mask.shape[1] - 1 or y1 >= mask.shape[0] - 1
        bw = max(1, x1 - x0)
        bh = max(1, y1 - y0)
        fill_ratio = area / max(1.0, bw * bh)
        aspect = bw / max(1.0, bh)
        best_rect = max(0.0, 1.0 - abs(aspect - 1.2) / 1.8) * min(1.0, fill_ratio / 0.74)
    return float(best_ratio), bool(border_touch), float(best_rect)


def _highlight_texture(gray: np.ndarray, highlight_mask: np.ndarray) -> float:
    if not np.any(highlight_mask):
        return 0.0
    values = gray[highlight_mask]
    if values.size < 32:
        return 0.0
    return float(np.percentile(values, 90) - np.percentile(values, 10))


def _classify_noise_profile(
    *,
    noise_score_raw: float,
    brightness: float,
    shadow_ratio: float,
    contrast: float,
    edge_density_value: float,
    neutral_ratio: float,
    blue_ratio: float,
    portrait_likely: bool,
    validated_face_boxes: list[tuple[int, int, int, int]],
    scene_type: str,
) -> tuple[float, str, str, bool, str, str]:
    profile = "generic"
    threshold = 0.0115
    detail = "当前噪点不明显。"
    suggestion = "普通图片无需额外降噪，保持原始纹理通常更稳妥。"

    night_like = brightness <= 0.30 and shadow_ratio >= 0.24
    indoor_shadow = brightness <= 0.44 and shadow_ratio >= 0.32
    portrait_scene = portrait_likely and bool(validated_face_boxes)
    smooth_sky = blue_ratio >= 0.14 and edge_density_value <= 0.09 and contrast <= 0.15
    architecture_texture = scene_type in {"architecture_scene", "architecture_vivid_scene"}

    if portrait_scene:
        profile = "portrait_protect"
        threshold = 0.0128 if edge_density_value >= 0.10 else 0.0120
        detail = "检测到人像场景，降噪需要优先保护脸部纹理与皮肤细节。"
        suggestion = "仅在颗粒明显时建议温和降噪，并结合脸部清晰度回退检查。"
    elif architecture_texture:
        profile = "architecture_texture"
        threshold = 0.0125
        detail = "检测到建筑/纹理场景，降噪需要优先保护边缘、文字和重复纹理。"
        suggestion = "仅建议保守降噪，避免墙面线条、文字和结构细节被抹糊。"
    elif smooth_sky:
        profile = "smooth_sky"
        threshold = 0.0101
        detail = "检测到低纹理天空或大面积纯净背景，这类区域更容易暴露颗粒噪点。"
        suggestion = "可对平滑背景做适度降噪，但仍需保留云层和边缘自然过渡。"
    elif night_like:
        profile = "night_high_iso"
        threshold = 0.0094
        detail = "检测到夜景/高 ISO 风格的暗场画面，阴影噪点更可能影响观感。"
        suggestion = "建议把降噪纳入修复链，并重点检查暗部颗粒与细节保留平衡。"
    elif indoor_shadow:
        profile = "indoor_shadow"
        threshold = 0.0100
        detail = "检测到暗部占比较高的室内或阴影场景，提亮后容易放大噪点。"
        suggestion = "若后续需要提亮阴影，建议同步做温和降噪，避免颗粒感进一步放大。"
    elif neutral_ratio >= 0.24 and edge_density_value <= 0.08:
        profile = "smooth_sky"
        threshold = 0.0106
        detail = "检测到大面积平滑中性区域，轻微颗粒也可能比较显眼。"
        suggestion = "可在不伤细节的前提下做轻度降噪。"

    severity = max(0.0, min(1.0, (noise_score_raw - threshold) / max(0.0035, threshold * 0.55)))
    recommended = severity >= 0.34 and profile != "generic" or severity >= 0.48
    if severity >= 0.68:
        level = "high"
    elif severity >= 0.34:
        level = "elevated"
    else:
        level = "low"
    return severity, level, profile, recommended, detail, suggestion


def _classify_scene(
    *,
    brightness: float,
    highlight_ratio: float,
    clipped_highlights: float,
    shadow_ratio: float,
    crushed_shadows: float,
    dyn_range: float,
    contrast: float,
    p95: float,
    p99: float,
    skin_ratio_value: float,
    neutral_ratio: float,
    hue_entropy_value: float,
    green_ratio: float,
    green_high_sat_ratio: float,
    blue_ratio: float,
    edge_density_value: float,
    window_component_ratio: float,
    window_border_touch: bool,
    window_rect_score: float,
    central_mean: float,
    top_central_mean: float,
    bottom_central_mean: float,
    portrait_likely: bool,
    portrait_type: str,
) -> tuple[str, str, str, list[str], list[str]]:
    tags: list[str] = []
    notes: list[str] = []
    scene_type = "generic_scene"
    exposure_type = "normal"
    highlight_recovery_type = "not_needed"

    high_contrast_window = (
        not portrait_likely
        and dyn_range >= 0.62
        and shadow_ratio >= 0.24
        and (
            (
                window_component_ratio >= 0.16
                and window_border_touch
                and window_rect_score >= 0.38
            )
            or (
                top_central_mean >= 0.42
                and bottom_central_mean <= 0.26
                and top_central_mean >= bottom_central_mean + 0.14
                and central_mean >= 0.28
                and p95 >= 0.84
            )
        )
    )
    silhouette_scene = high_contrast_window and brightness <= 0.34 and crushed_shadows >= 0.08
    low_key_scene = (
        not portrait_likely
        and not high_contrast_window
        and brightness <= 0.30
        and shadow_ratio >= 0.28
        and dyn_range >= 0.46
        and highlight_ratio <= 0.06
        and p95 <= 0.82
    )
    architecture_scene = (
        not portrait_likely
        and skin_ratio_value <= 0.012
        and neutral_ratio >= 0.18
        and edge_density_value >= 0.12
        and contrast >= 0.12
    )
    natural_vivid_scene = (
        green_ratio >= 0.08
        or blue_ratio >= 0.12
        or (green_high_sat_ratio >= 0.06 and hue_entropy_value >= 2.25)
    )
    if portrait_likely:
        scene_type = "portrait_scene"
    elif portrait_type == "artwork_face_context":
        scene_type = "artwork_scene"
        tags.append("artwork_face")
        notes.append("检测到画作/非真实人像上下文。")
    elif portrait_type in {"back_view_person_context", "side_back_view_person"}:
        scene_type = "people_context_scene"
        tags.append("back_view_person")
        notes.append("检测到背身或非正面人物上下文。")
    elif silhouette_scene:
        scene_type = "silhouette_scene"
        exposure_type = "silhouette_scene"
        tags.extend(["silhouette_scene", "suppress_global_shadow_lift"])
        notes.append("检测到高反差剪影/逆光氛围，不建议按普通欠曝自动提亮。")
    elif high_contrast_window:
        scene_type = "high_contrast_window_scene"
        exposure_type = "high_contrast_window_scene"
        tags.extend(["high_contrast_window_scene", "protect_window_highlights", "suppress_global_shadow_lift"])
        notes.append("检测到高反差窗景或室内外反差场景，不建议把暗部整体抬灰。")
    elif low_key_scene:
        scene_type = "low_key_scene"
        exposure_type = "low_key_scene"
        tags.extend(["low_key_scene", "suppress_global_shadow_lift"])
        notes.append("检测到低调氛围场景，暗部更可能是创作选择。")
    elif architecture_scene and natural_vivid_scene:
        scene_type = "architecture_vivid_scene"
    elif architecture_scene:
        scene_type = "architecture_scene"
    elif natural_vivid_scene:
        scene_type = "natural_vivid_scene"

    if clipped_highlights >= 0.018 and highlight_ratio >= 0.10:
        if blue_ratio >= 0.10 or neutral_ratio >= 0.22 or window_component_ratio >= 0.12:
            highlight_recovery_type = "unrecoverable_highlights"
            tags.extend(["unrecoverable_highlights", "avoid_gray_sky"])
            if scene_type in {"architecture_scene", "architecture_vivid_scene"}:
                notes.append("亮部更接近天空/白墙等不可恢复高光，应避免强压成灰。")
        else:
            highlight_recovery_type = "recoverable_highlights"
    elif highlight_ratio >= 0.06 and p99 >= 0.985:
        highlight_recovery_type = "recoverable_highlights"

    return scene_type, exposure_type, highlight_recovery_type, tags, notes


def _build_exposure_issues(
    *,
    brightness: float,
    highlight_ratio: float,
    clipped_highlights: float,
    shadow_ratio: float,
    crushed_shadows: float,
    dyn_range: float,
    contrast: float,
    p50: float,
    p95: float,
    p99: float,
    p999: float,
    portrait_likely: bool,
    portrait_data: dict[str, object],
    scene_type: str,
    exposure_type: str,
    highlight_recovery_type: str,
    highlight_texture: float,
) -> tuple[list[Issue], str, str, list[str]]:
    issues: list[Issue] = []
    diagnostic_notes: list[str] = []

    portrait_over_relief = 0.0
    if portrait_likely:
        portrait_scene_type = str(portrait_data["portrait_scene_type"])
        portrait_exposure_status = str(portrait_data["portrait_exposure_status"])
        highlight_clipping_ratio = float(portrait_data["highlight_clipping_ratio"])
        background_exposure_status = str(portrait_data["background_exposure_status"])
        if portrait_scene_type == "high_key_portrait" and portrait_exposure_status == "subject_normal":
            portrait_over_relief += 0.72 + highlight_clipping_ratio * 2.4
            if background_exposure_status == "high_key":
                portrait_over_relief += 0.18
        elif portrait_scene_type == "backlit_portrait" and portrait_exposure_status in {"subject_normal", "subject_dark"}:
            portrait_over_relief += 0.42 + highlight_clipping_ratio * 1.4
        elif portrait_exposure_status == "subject_bright":
            portrait_over_relief -= 0.18

    over_score = min(
        1.0,
        max(
            0.0,
            (clipped_highlights - 0.03) * 8.0
            + (highlight_ratio - 0.08) * 2.5
            + max(0.0, brightness - 0.84) * 1.8
            + max(0.0, p99 - 0.985) * 2.5
            + max(0.0, p999 - 0.995) * 1.5
            - portrait_over_relief,
        ),
    )
    if over_score >= 0.38:
        detail = f"亮部占比 {highlight_ratio:.1%}，高光裁切约 {clipped_highlights:.1%}，亮部细节已有损失风险。"
        suggestion = "建议适度降低曝光或高光，通常以回收约 0.3 到 1 EV 为起点更稳妥。"
        if portrait_likely and str(portrait_data["portrait_scene_type"]) == "backlit_portrait":
            detail = f"亮部占比 {highlight_ratio:.1%}，高光裁切约 {clipped_highlights:.1%}；当前更接近逆光人像，高亮背景对判断有明显干扰。"
            suggestion = "建议优先压低背景高光并保护主体层次，避免把逆光人像整体压灰。"
        elif highlight_recovery_type == "unrecoverable_highlights":
            detail = (
                f"亮部占比 {highlight_ratio:.1%}，高光裁切约 {clipped_highlights:.1%}；"
                f"高光纹理仅约 {highlight_texture:.3f}，更接近不可恢复亮部。"
            )
            suggestion = "建议避免强行 recover highlights；保持自然空气感通常比把天空或白墙压灰更稳妥。"
            diagnostic_notes.append("检测到不可恢复高光，已标记为避免强压。")
        issues.append(issue("overexposed", "过曝", over_score, detail, suggestion))

    low_key_relief = (
        max(0.0, dyn_range - 0.75) * 3.0
        + max(0.0, p95 - 0.84) * 4.5
        + max(0.0, highlight_ratio - 0.02) * 6.0
        + max(0.0, p99 - 0.96) * 4.0
    )
    portrait_under_relief = 0.0
    subject_dark_push = 0.0
    if portrait_likely:
        portrait_exposure_status = str(portrait_data["portrait_exposure_status"])
        face_luma_mean = portrait_data["face_luma_mean"]
        subject_luma_estimate = portrait_data["subject_luma_estimate"]
        background_luma_estimate = portrait_data["background_luma_estimate"]
        portrait_scene_type = str(portrait_data["portrait_scene_type"])
        if portrait_exposure_status == "subject_normal":
            portrait_under_relief += 0.50
            if face_luma_mean is not None:
                portrait_under_relief += max(0.0, float(face_luma_mean) - 0.38) * 1.45
            if subject_luma_estimate is not None and background_luma_estimate is not None:
                portrait_under_relief += max(0.0, float(subject_luma_estimate) - float(background_luma_estimate) - 0.10) * 1.75
            if portrait_scene_type == "high_key_portrait":
                portrait_under_relief += 0.22
        elif portrait_exposure_status == "subject_bright":
            portrait_under_relief += 0.62
        elif portrait_exposure_status == "subject_dark":
            subject_reference = face_luma_mean if face_luma_mean is not None else subject_luma_estimate
            if subject_reference is not None:
                subject_dark_push += max(0.0, 0.36 - float(subject_reference)) * 2.5
            if portrait_scene_type == "backlit_portrait":
                subject_dark_push += 0.10

    scene_under_relief = 0.0
    if exposure_type == "silhouette_scene":
        scene_under_relief += 0.92
    elif exposure_type == "high_contrast_window_scene":
        scene_under_relief += 0.78
    elif exposure_type == "low_key_scene":
        scene_under_relief += 0.60

    under_score = min(
        1.0,
        max(
            0.0,
            (crushed_shadows - 0.04) * 7.5
            + (shadow_ratio - 0.14) * 1.8
            + max(0.0, 0.24 - brightness) * 2.6
            + max(0.0, 0.18 - p50) * 2.2
            + subject_dark_push
            - low_key_relief
            - portrait_under_relief
            - scene_under_relief,
        ),
    )

    final_exposure_type = exposure_type
    if under_score >= 0.38 and exposure_type == "normal":
        final_exposure_type = "underexposed"
        detail = f"暗部占比 {shadow_ratio:.1%}，压黑区域 {crushed_shadows:.1%}，整体亮度偏低。"
        suggestion = "建议适度提亮暗部与中间调，同时保护高光，避免把黑色区域抬灰。"
        if portrait_likely and str(portrait_data["portrait_exposure_status"]) == "subject_dark":
            subject_value = portrait_data["subject_luma_estimate"]
            detail = f"暗部占比 {shadow_ratio:.1%}，压黑区域 {crushed_shadows:.1%}；主体亮度约 {0.0 if subject_value is None else float(subject_value):.3f}，人物主体也偏暗。"
            suggestion = "建议优先做保守的人像主体提亮与局部层次修复，避免把背景一并大幅抬亮。"
        issues.append(
            issue(
                "underexposed",
                "欠曝",
                under_score,
                detail,
                suggestion,
                meta={"severity": f"{under_score:.3f}"},
            )
        )
    elif exposure_type == "high_contrast_window_scene":
        diagnostic_notes.append("高反差窗景：暗部更像构图氛围，不建议按普通欠曝强修。")
    elif exposure_type == "silhouette_scene":
        diagnostic_notes.append("剪影场景：暗部更接近视觉表达，不建议自动整体提亮。")
    elif exposure_type == "low_key_scene":
        diagnostic_notes.append("低调场景：当前更接近保留氛围而非普通欠曝。")

    if final_exposure_type == "normal" and over_score >= 0.38:
        if highlight_recovery_type == "unrecoverable_highlights":
            final_exposure_type = "overexposed_unrecoverable"
        else:
            final_exposure_type = "overexposed_recoverable"
    return issues, final_exposure_type, highlight_recovery_type, diagnostic_notes


def _build_color_issues(
    *,
    mean_saturation: float,
    p90_saturation: float,
    mid_mean_saturation: float,
    mid_p90_saturation: float,
    high_sat_ratio: float,
    bright_high_sat_ratio: float,
    shadow_high_sat_ratio: float,
    green_ratio: float,
    green_high_sat_ratio: float,
    hue_entropy_value: float,
    contrast: float,
    dyn_range: float,
    hdr_hint: float,
    neutral_ratio: float,
    neutral_balance: float,
    rgb_balance: float,
    skin_ratio_value: float,
    scene_type: str,
    portrait_likely: bool,
    r_mean: float,
    g_mean: float,
    b_mean: float,
) -> tuple[list[Issue], str]:
    issues: list[Issue] = []
    color_type = "balanced"

    cast_relief = max(0.0, hue_entropy_value - 0.62) * 0.9 + max(0.0, high_sat_ratio - 0.18) * 0.65 + max(0.0, 0.10 - neutral_ratio) * 0.35
    cast_score = min(1.0, max(0.0, (neutral_balance - 0.06) * 4.0 - cast_relief))
    if cast_score >= 0.36:
        bias_name, detail, suggestion, meta = describe_color_cast(r_mean, g_mean, b_mean, rgb_balance)
        issues.append(issue("color_cast", "偏色", cast_score, f"{detail} 当前主要表现为 {bias_name}。", suggestion, meta=meta))

    restrained_scene_relief = 0.0
    if scene_type in {"high_contrast_window_scene", "silhouette_scene", "low_key_scene", "architecture_scene", "artwork_scene"}:
        restrained_scene_relief += 0.30
    if 0.15 <= mean_saturation <= 0.24 and p90_saturation >= 0.42:
        restrained_scene_relief += 0.24
    if hue_entropy_value >= 2.18:
        restrained_scene_relief += 0.12
    if green_ratio >= 0.06:
        restrained_scene_relief += 0.10
    portrait_relief = max(0.0, skin_ratio_value - 0.018) * 2.2 + max(0.0, neutral_ratio - 0.10) * 0.35 + max(0.0, 0.16 - rgb_balance) * 0.25
    muted_color_score = min(
        1.0,
        max(
            0.0,
            (0.19 - mean_saturation) * 4.0 + (0.36 - p90_saturation) * 1.8 + max(0.0, 0.20 - contrast) * 0.6 - portrait_relief - restrained_scene_relief,
        ),
    )
    if muted_color_score >= 0.42:
        issues.append(
            issue(
                "muted_colors",
                "色彩寡淡",
                muted_color_score,
                f"平均饱和度 {mean_saturation:.3f} 偏低，画面色彩层次较弱。",
                "建议采用更保守的 scene-aware vibrance，只提升低饱和区域并保护天空、肤色与中性色。",
            )
        )
        color_type = "muted_problem"
    elif restrained_scene_relief >= 0.24 and mean_saturation <= 0.24:
        color_type = "restrained_natural"

    vivid_scene_relief = max(0.0, hue_entropy_value - 0.72) * 1.1 + max(0.0, dyn_range - 0.62) * 0.35 + hdr_hint * 0.24 + max(0.0, 0.09 - neutral_balance) * 1.2
    if scene_type in {"architecture_scene", "architecture_vivid_scene", "natural_vivid_scene"}:
        vivid_scene_relief += 0.26
    foliage_shadow_relief = max(0.0, green_ratio - 0.22) * 1.6 + max(0.0, green_high_sat_ratio - 0.12) * 1.8 + max(0.0, shadow_high_sat_ratio - 0.18) * 1.3 + max(0.0, 0.02 - bright_high_sat_ratio) * 6.0
    over_saturation_score = min(
        1.0,
        max(
            0.0,
            (mid_mean_saturation - 0.33) * 2.4
            + (mid_p90_saturation - 0.82) * 1.9
            + (bright_high_sat_ratio - 0.018) * 8.0
            + (high_sat_ratio - 0.14) * 0.68
            - vivid_scene_relief
            - foliage_shadow_relief,
        ),
    )
    if over_saturation_score >= 0.46:
        issues.append(
            issue(
                "over_saturated",
                "过饱和",
                over_saturation_score,
                f"中间调饱和度 {mid_mean_saturation:.3f} 偏高，亮部高饱和区域占比 {bright_high_sat_ratio:.1%}，颜色可能过于浓重。",
                "建议适度回收饱和度并保护高光，避免鲜艳区域出现脏色或天空失真。",
            )
        )
        color_type = "oversaturated_problem"
    elif color_type == "balanced" and (scene_type in {"natural_vivid_scene", "architecture_vivid_scene"} or high_sat_ratio >= 0.10):
        color_type = "natural_vivid"

    return issues, color_type


def analyze_image(path: str | Path, progress_callback: Callable[[int, int, str], None] | None = None) -> AnalysisResult:
    image_path = Path(path)
    perf_timings: dict[str, float] = {}
    analyze_started_at = np.float64(0.0)
    import time

    analyze_started_at = time.perf_counter()
    if progress_callback is not None:
        progress_callback(1, 5, "读取图像")
    image_read_started_at = time.perf_counter()
    with Image.open(image_path) as img:
        add_timing(perf_timings, "image_open", image_read_started_at)
        started_at = time.perf_counter()
        transposed = ImageOps.exif_transpose(img)
        add_timing(perf_timings, "exif_transpose", started_at)
        started_at = time.perf_counter()
        rgb_full = transposed.convert("RGB")
        add_timing(perf_timings, "image_convert", started_at)
    add_timing(perf_timings, "image_read", image_read_started_at)

    rgb, original_size, working_size, resized_for_analysis = _working_image_from_rgb(rgb_full, perf_timings)
    if resized_for_analysis:
        rgb_full.close()
    original_width, original_height = original_size
    scale_x = original_width / max(1, working_size[0])
    scale_y = original_height / max(1, working_size[1])

    basic_stats_started_at = time.perf_counter()
    started_at = time.perf_counter()
    arr = np.asarray(rgb, dtype=np.float32)
    gray = (arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114) / 255.0
    add_timing(perf_timings, "array_convert", started_at)

    if progress_callback is not None:
        progress_callback(2, 5, "统计亮度、主体与背景")
    started_at = time.perf_counter()
    brightness = float(np.mean(gray))
    highlight_ratio = float(np.mean(gray >= 0.96))
    clipped_highlights = float(np.mean(gray >= 0.985))
    shadow_ratio = float(np.mean(gray <= 0.08))
    crushed_shadows = float(np.mean(gray <= 0.03))
    contrast = float(np.std(gray))
    dyn_range = float(np.percentile(gray, 95) - np.percentile(gray, 5))
    scene_detail = float(np.var(gray))
    p50 = float(np.percentile(gray, 50))
    p95 = float(np.percentile(gray, 95))
    p99 = float(np.percentile(gray, 99))
    p999 = float(np.percentile(gray, 99.9))
    add_timing(perf_timings, "exposure", started_at)

    started_at = time.perf_counter()
    local_dyn = local_range(gray)
    _, sharp_p90, sharp_max = tile_sharpness(gray)
    add_timing(perf_timings, "sharpness", started_at)

    started_at = time.perf_counter()
    r_mean = float(np.mean(arr[:, :, 0])) / 255.0
    g_mean = float(np.mean(arr[:, :, 1])) / 255.0
    b_mean = float(np.mean(arr[:, :, 2])) / 255.0
    rgb_balance = max(abs(r_mean - g_mean), abs(g_mean - b_mean), abs(r_mean - b_mean))
    saturation = saturation_map(arr)
    hue = hue_map(arr)
    mean_saturation = float(np.mean(saturation))
    high_sat_ratio = float(np.mean(saturation >= 0.82))
    p90_saturation = float(np.percentile(saturation, 90))
    midtone_mask = (gray > 0.22) & (gray < 0.78)
    bright_mask = gray > 0.45
    shadow_mask = gray < 0.25
    green_dominant_mask = (arr[:, :, 1] > arr[:, :, 0] * 1.08) & (arr[:, :, 1] > arr[:, :, 2] * 1.08)
    blue_dominant_mask = (arr[:, :, 2] > arr[:, :, 0] * 1.04) & (arr[:, :, 2] > arr[:, :, 1] * 1.02) & (gray > 0.34)
    mid_mean_saturation = masked_mean(saturation, midtone_mask, mean_saturation)
    mid_p90_saturation = masked_percentile(saturation, midtone_mask, 90, p90_saturation)
    bright_high_sat_ratio = float(np.mean(bright_mask & (saturation >= 0.82)))
    shadow_high_sat_ratio = float(np.mean(shadow_mask & (saturation >= 0.72)))
    green_ratio = float(np.mean(green_dominant_mask))
    green_high_sat_ratio = float(np.mean(green_dominant_mask & (saturation >= 0.82)))
    blue_ratio = float(np.mean(blue_dominant_mask))
    central_slice = gray[:, gray.shape[1] // 4 : gray.shape[1] * 3 // 4]
    central_mean = float(np.mean(central_slice)) if central_slice.size else brightness
    top_central_mean = float(np.mean(central_slice[: central_slice.shape[0] // 2, :])) if central_slice.size else brightness
    bottom_central_mean = float(np.mean(central_slice[central_slice.shape[0] // 2 :, :])) if central_slice.size else brightness
    skin_ratio_value = skin_ratio(arr)
    hue_entropy_value = hue_entropy(hue, saturation)
    neutral_mask = (saturation < 0.18) & (gray > 0.18) & (gray < 0.88)
    neutral_ratio = float(np.mean(neutral_mask))
    neutral_balance = rgb_balance
    if np.any(neutral_mask):
        neutral_r = float(np.mean(arr[:, :, 0][neutral_mask])) / 255.0
        neutral_g = float(np.mean(arr[:, :, 1][neutral_mask])) / 255.0
        neutral_b = float(np.mean(arr[:, :, 2][neutral_mask])) / 255.0
        neutral_balance = max(abs(neutral_r - neutral_g), abs(neutral_g - neutral_b), abs(neutral_r - neutral_b))
    hdr_hint = 1.0 if "HDR" in image_path.name.upper() else 0.0
    add_timing(perf_timings, "color", started_at)
    add_timing(perf_timings, "basic_stats", basic_stats_started_at)

    started_at = time.perf_counter()
    portrait_detect = detect_portrait_regions(rgb)
    add_timing(perf_timings, "face_detect", started_at)
    raw_face_candidates = list(portrait_detect["raw_face_candidates"])
    validated_face_boxes = list(portrait_detect["validated_face_boxes"])
    face_confidences = list(portrait_detect["face_confidences"])
    face_candidates = list(portrait_detect["face_candidates"])
    portrait_type = str(portrait_detect.get("portrait_type", "non_portrait"))
    rejected_face_count = int(portrait_detect.get("rejected_face_count", len([item for item in face_candidates if not item.accepted])))
    portrait_likely, portrait_rejection_reason = confirm_portrait(
        rgb.size,
        raw_face_candidates,
        validated_face_boxes,
        face_confidences,
        skin_ratio_value,
        float(portrait_detect["central_skin_ratio"]),
        portrait_type,
    )

    started_at = time.perf_counter()
    portrait_data = analyze_portrait_regions(
        arr,
        gray,
        saturation,
        validated_face_boxes,
        face_confidences,
        raw_face_candidates,
        face_candidates,
        portrait_likely,
        portrait_rejection_reason or str(portrait_detect.get("portrait_rejection_reason", "")),
        portrait_type,
        portrait_detect.get("people_context_box"),
    )
    add_timing(perf_timings, "portrait_region_build", started_at)

    if progress_callback is not None:
        progress_callback(3, 5, "计算锐度、色彩与人像特征")
    started_at = time.perf_counter()
    noise_probe = gray - np.clip((gray + np.roll(gray, 1, 0) + np.roll(gray, -1, 0) + np.roll(gray, 1, 1) + np.roll(gray, -1, 1)) / 5.0, 0.0, 1.0)
    noise_scale_correction = np.sqrt(max(working_size) / max(1, max(original_size)))
    noise_score_raw = float(np.std(noise_probe)) * min(1.0, max(0.0, noise_scale_correction))
    add_timing(perf_timings, "noise", started_at)
    started_at = time.perf_counter()
    edge_density_value = edge_density(gray)
    window_component_ratio, window_border_touch, window_rect_score = _bright_component_stats(gray >= 0.74)
    highlight_texture = _highlight_texture(gray, gray >= 0.90)
    add_timing(perf_timings, "quality_stats", started_at)

    issues: list[Issue] = []
    if progress_callback is not None:
        progress_callback(4, 5, "判定问题标签与修复建议")

    started_at = time.perf_counter()
    scene_type, scene_exposure_type, highlight_recovery_type, scene_tags, scene_notes = _classify_scene(
        brightness=brightness,
        highlight_ratio=highlight_ratio,
        clipped_highlights=clipped_highlights,
        shadow_ratio=shadow_ratio,
        crushed_shadows=crushed_shadows,
        dyn_range=dyn_range,
        contrast=contrast,
        p95=p95,
        p99=p99,
        skin_ratio_value=skin_ratio_value,
        neutral_ratio=neutral_ratio,
        hue_entropy_value=hue_entropy_value,
        green_ratio=green_ratio,
        green_high_sat_ratio=green_high_sat_ratio,
        blue_ratio=blue_ratio,
        edge_density_value=edge_density_value,
        window_component_ratio=window_component_ratio,
        window_border_touch=window_border_touch,
        window_rect_score=window_rect_score,
        central_mean=central_mean,
        top_central_mean=top_central_mean,
        bottom_central_mean=bottom_central_mean,
        portrait_likely=portrait_likely,
        portrait_type=portrait_type,
    )
    add_timing(perf_timings, "scene_classify", started_at)

    started_at = time.perf_counter()
    noise_severity, noise_level, denoise_profile, denoise_recommended, noise_detail, noise_suggestion = _classify_noise_profile(
        noise_score_raw=noise_score_raw,
        brightness=brightness,
        shadow_ratio=shadow_ratio,
        contrast=contrast,
        edge_density_value=edge_density_value,
        neutral_ratio=neutral_ratio,
        blue_ratio=blue_ratio,
        portrait_likely=portrait_likely,
        validated_face_boxes=validated_face_boxes,
        scene_type=scene_type,
    )

    exposure_issues, exposure_type, highlight_recovery_type, exposure_notes = _build_exposure_issues(
        brightness=brightness,
        highlight_ratio=highlight_ratio,
        clipped_highlights=clipped_highlights,
        shadow_ratio=shadow_ratio,
        crushed_shadows=crushed_shadows,
        dyn_range=dyn_range,
        contrast=contrast,
        p50=p50,
        p95=p95,
        p99=p99,
        p999=p999,
        portrait_likely=portrait_likely,
        portrait_data=portrait_data,
        scene_type=scene_type,
        exposure_type=scene_exposure_type,
        highlight_recovery_type=highlight_recovery_type,
        highlight_texture=highlight_texture,
    )
    issues.extend(exposure_issues)
    if noise_severity >= 0.38:
        issues.append(
            issue(
                "high_noise",
                "噪点偏高",
                noise_severity,
                f"{noise_detail} 当前噪声指标约 {noise_score_raw:.4f}，推荐降噪策略：{denoise_profile}。",
                noise_suggestion,
            )
        )
        if denoise_recommended:
            scene_notes.append(f"检测到适合纳入统一修复链的降噪场景：{denoise_profile}")

    texture_ready = scene_detail >= 0.0025 or dyn_range >= 0.20
    blur_score = min(1.0, max(0.0, (0.0012 - sharp_p90) / 0.0012 * 0.8 + (0.00018 - sharp_max) / 0.00018 * 0.2))
    if texture_ready and blur_score >= 0.42:
        issues.append(
            issue(
                "out_of_focus",
                "失焦/模糊",
                blur_score,
                f"局部锐度不足，清晰度 P90={sharp_p90:.4f}，峰值={sharp_max:.4f}，画面可能存在对焦或抖动问题。",
                "建议优先保留原图；自动修复只能做轻微锐化，无法真正恢复失焦细节。",
            )
        )

    portrait_focus_score = 0.0
    if portrait_likely and validated_face_boxes:
        face_sharpness_mean = portrait_data.get("face_sharpness_mean")
        subject_sharpness = portrait_data.get("subject_sharpness")
        background_sharpness = portrait_data.get("background_sharpness")
        face_context_sharpness = portrait_data.get("face_context_sharpness")
        reference_candidates = [float(value) for value in [face_context_sharpness, background_sharpness, subject_sharpness] if value is not None]
        reference_sharpness = max(reference_candidates, default=0.0)
        if face_sharpness_mean is not None:
            face_sharpness_value = float(face_sharpness_mean)
            sharpness_gap_ratio = reference_sharpness / max(face_sharpness_value, 1e-6)
            subject_gap_ratio = float(subject_sharpness) / max(face_sharpness_value, 1e-6) if subject_sharpness is not None else sharpness_gap_ratio
            base_face_blur = max(0.0, 0.00105 - face_sharpness_value) / 0.00105
            background_priority = max(0.0, sharpness_gap_ratio - 1.18) / 1.85
            subject_priority = max(0.0, subject_gap_ratio - 1.06) / 1.55
            blur_support = max(0.0, blur_score - 0.20) * 0.60
            portrait_focus_score = min(1.0, base_face_blur * 0.62 + background_priority * 0.26 + subject_priority * 0.16 + blur_support)
            if portrait_focus_score >= 0.58 and (face_sharpness_value <= 0.0010 or sharpness_gap_ratio >= 1.35):
                issues.append(
                    issue(
                        "portrait_out_of_focus",
                        "人像主体虚焦",
                        portrait_focus_score,
                        f"有效真人脸部锐度约 {face_sharpness_value:.4f}，主体/背景参考锐度约 {reference_sharpness:.4f}，清晰度差约 {sharpness_gap_ratio:.2f}x；人物脸部明显未对焦。",
                        "不适合保留 / 建议删除；自动锐化无法恢复脸部失焦细节。",
                        meta={
                            "cleanup_candidate": "true",
                            "cleanup_reason_code": "portrait_out_of_focus",
                            "cleanup_reason_text": "真实正面人像脸部严重虚焦，保留价值很低。",
                            "cleanup_severity": "high",
                            "cleanup_confidence": f"{portrait_focus_score:.3f}",
                        },
                    )
                )

    low_contrast_score = min(1.0, max(0.0, (0.16 - contrast) * 4.0 + max(0.0, 0.33 - dyn_range)))
    if low_contrast_score >= 0.36:
        issues.append(
            issue(
                "low_contrast",
                "低对比度",
                low_contrast_score,
                f"整体对比度 {contrast:.3f}、动态范围 {dyn_range:.3f} 偏低，画面层次不够通透。",
                "建议轻微提升中间调对比和局部层次，避免把高光压脏或把阴影抬灰。",
            )
        )

    color_issues, color_type = _build_color_issues(
        mean_saturation=mean_saturation,
        p90_saturation=p90_saturation,
        mid_mean_saturation=mid_mean_saturation,
        mid_p90_saturation=mid_p90_saturation,
        high_sat_ratio=high_sat_ratio,
        bright_high_sat_ratio=bright_high_sat_ratio,
        shadow_high_sat_ratio=shadow_high_sat_ratio,
        green_ratio=green_ratio,
        green_high_sat_ratio=green_high_sat_ratio,
        hue_entropy_value=hue_entropy_value,
        contrast=contrast,
        dyn_range=dyn_range,
        hdr_hint=hdr_hint,
        neutral_ratio=neutral_ratio,
        neutral_balance=neutral_balance,
        rgb_balance=rgb_balance,
        skin_ratio_value=skin_ratio_value,
        scene_type=scene_type,
        portrait_likely=portrait_likely,
        r_mean=r_mean,
        g_mean=g_mean,
        b_mean=b_mean,
    )
    issues.extend(color_issues)
    add_timing(perf_timings, "issue_build", started_at)

    if progress_callback is not None:
        progress_callback(5, 5, "生成指标与最终结果")
    metrics = [
        metric("平均亮度", brightness, f"{brightness:.3f}", "#8fc18d"),
        metric("高光占比", highlight_ratio, f"{highlight_ratio:.1%}", "#efb65a"),
        metric("高光剪切", clipped_highlights, f"{clipped_highlights:.1%}", "#e47b43"),
        metric("暗部占比", shadow_ratio, f"{shadow_ratio:.1%}", "#7189d8"),
        metric("暗部压死", crushed_shadows, f"{crushed_shadows:.1%}", "#4f66ad"),
        metric("全局对比度", contrast, f"{contrast:.3f}", "#8d6aca", max_value=0.45),
        metric("动态范围", dyn_range, f"{dyn_range:.3f}", "#58b4b2"),
        metric("局部层次", local_dyn, f"{local_dyn:.3f}", "#59a36b"),
        metric("局部锐度P90", sharp_p90, f"{sharp_p90:.4f}", "#d16b6b", max_value=0.012),
        metric("局部锐度峰值", sharp_max, f"{sharp_max:.4f}", "#b24e4e", max_value=0.022),
        metric("通道偏差", rgb_balance, f"{rgb_balance:.3f}", "#c98745", max_value=0.28),
        metric("中性偏差", neutral_balance, f"{neutral_balance:.3f}", "#ad7b45", max_value=0.18),
        metric("平均饱和度", mean_saturation, f"{mean_saturation:.3f}", "#c96d7e", max_value=0.6),
        metric("中间调饱和度", mid_mean_saturation, f"{mid_mean_saturation:.3f}", "#c05b70", max_value=0.6),
        metric("高饱和占比", high_sat_ratio, f"{high_sat_ratio:.1%}", "#b95773"),
        metric("亮部高饱和", bright_high_sat_ratio, f"{bright_high_sat_ratio:.1%}", "#b04e68", max_value=0.18),
        metric("色相分布", hue_entropy_value, f"{hue_entropy_value:.3f}", "#9f6ac9"),
        metric("肤色占比", skin_ratio_value, f"{skin_ratio_value:.1%}", "#cc8c73", max_value=0.2),
        metric("raw人脸候选", float(len(raw_face_candidates)), str(len(raw_face_candidates)), "#b38f5b", max_value=8.0),
        metric("有效真人人脸", float(len(validated_face_boxes)), str(len(validated_face_boxes)), "#8f9d51", max_value=6.0),
        metric("拒绝候选数", float(rejected_face_count), str(rejected_face_count), "#ad6f5f", max_value=8.0),
        metric("脸部亮度", float(portrait_data["face_luma_mean"] or 0.0), "-" if portrait_data["face_luma_mean"] is None else f"{float(portrait_data['face_luma_mean']):.3f}", "#d98b72"),
        metric("脸部锐度", float(portrait_data["face_sharpness_mean"] or 0.0), "-" if portrait_data["face_sharpness_mean"] is None else f"{float(portrait_data['face_sharpness_mean']):.4f}", "#cf7f60", max_value=0.006),
        metric("主体亮度", float(portrait_data["subject_luma_estimate"] or 0.0), "-" if portrait_data["subject_luma_estimate"] is None else f"{float(portrait_data['subject_luma_estimate']):.3f}", "#74a6c7"),
        metric("主体锐度", float(portrait_data["subject_sharpness"] or 0.0), "-" if portrait_data["subject_sharpness"] is None else f"{float(portrait_data['subject_sharpness']):.4f}", "#6798bf", max_value=0.006),
        metric("背景亮度", float(portrait_data["background_luma_estimate"] or 0.0), "-" if portrait_data["background_luma_estimate"] is None else f"{float(portrait_data['background_luma_estimate']):.3f}", "#62788f"),
        metric("背景锐度", float(portrait_data["background_sharpness"] or 0.0), "-" if portrait_data["background_sharpness"] is None else f"{float(portrait_data['background_sharpness']):.4f}", "#5f7389", max_value=0.006),
        metric("高光裁切比", float(portrait_data["highlight_clipping_ratio"]), f"{float(portrait_data['highlight_clipping_ratio']):.1%}", "#d9b36f", max_value=0.15),
        metric("主体背景分离", float(portrait_data["subject_background_separation"]), f"{float(portrait_data['subject_background_separation']):.3f}", "#6d9fc7", max_value=0.35),
        metric("人像失焦风险", portrait_focus_score, f"{portrait_focus_score:.2f}", "#c96363"),
        metric("噪声指标", noise_score_raw, f"{noise_score_raw:.4f}", "#7c9db7", max_value=0.05),
    ]

    perf_notes: list[str] = []
    if resized_for_analysis:
        perf_notes.append(f"working image {original_width}x{original_height} -> {working_size[0]}x{working_size[1]}")
    if perf_timings.get("face_detect", 0.0) > 75.0:
        perf_notes.append("人脸候选筛选耗时较长")
    if perf_timings.get("portrait_region_build", 0.0) > 45.0:
        perf_notes.append("人像区域构建耗时较长")
    if perf_timings.get("analyze_total", 0.0) > 260.0:
        perf_notes.append("分析耗时较长")
    if len(validated_face_boxes) >= 3:
        perf_notes.append("检测到多人像区域")
    issues = sanitize_issues(issues)
    overall = max((item.score for item in issues), default=0.0)
    started_at = time.perf_counter()
    cleanup_candidates = build_cleanup_candidates(image_path, issues)
    add_timing(perf_timings, "cleanup_candidate", started_at)
    perf_timings["analyze_total"] = (time.perf_counter() - analyze_started_at) * 1000.0
    if perf_timings.get("analyze_total", 0.0) > 260.0 and "分析耗时较长" not in perf_notes:
        perf_notes.append("分析耗时较长")

    diagnostic_tags = list(dict.fromkeys(list(portrait_data["diagnostic_tags"]) + scene_tags))
    diagnostic_notes = list(dict.fromkeys(list(portrait_data["diagnostic_notes"]) + scene_notes + exposure_notes))
    if highlight_recovery_type == "unrecoverable_highlights" and "avoid_gray_sky" not in diagnostic_tags:
        diagnostic_tags.append("avoid_gray_sky")

    scaled_raw_face_candidates = _scale_boxes_to_original(raw_face_candidates, scale_x, scale_y, original_size)
    scaled_validated_face_boxes = _scale_boxes_to_original(validated_face_boxes, scale_x, scale_y, original_size)
    scaled_subject_boxes = _scale_boxes_to_original(list(portrait_data.get("subject_boxes", [])), scale_x, scale_y, original_size)
    scaled_face_candidates = list(face_candidates)
    for candidate in scaled_face_candidates:
        candidate.box = _scale_box_to_original(candidate.box, scale_x, scale_y, original_size)
    scaled_face_stats = list(portrait_data.get("face_stats", []))
    for face_stat in scaled_face_stats:
        face_stat.box = _scale_box_to_original(face_stat.box, scale_x, scale_y, original_size)
    scaled_face_region = _scale_region_to_original(portrait_data["face_region"], scale_x, scale_y, original_size)
    scaled_subject_region = _scale_region_to_original(portrait_data["subject_region"], scale_x, scale_y, original_size)
    scaled_background_region = _scale_region_to_original(portrait_data["background_region"], scale_x, scale_y, original_size)
    scaled_highlight_region = _scale_region_to_original(portrait_data["highlight_region"], scale_x, scale_y, original_size)

    return AnalysisResult(
        path=image_path,
        width=original_width,
        height=original_height,
        overall_score=overall,
        issues=issues,
        metrics=metrics,
        face_count=len(raw_face_candidates),
        raw_face_count=len(raw_face_candidates),
        face_boxes=scaled_validated_face_boxes,
        raw_face_candidates=scaled_raw_face_candidates,
        validated_face_boxes=scaled_validated_face_boxes,
        validated_face_count=len(validated_face_boxes),
        rejected_face_count=rejected_face_count,
        face_confidence=float(max(face_confidences, default=0.0)),
        face_confidences=face_confidences,
        face_candidates=scaled_face_candidates,
        subject_boxes=scaled_subject_boxes,
        face_stats=scaled_face_stats,
        face_region=scaled_face_region,
        subject_region=scaled_subject_region,
        background_region=scaled_background_region,
        highlight_region=scaled_highlight_region,
        portrait_likely=portrait_likely,
        portrait_type=portrait_type,
        portrait_scene_type=str(portrait_data["portrait_scene_type"]),
        scene_type=scene_type,
        face_luma_median=portrait_data["face_luma_median"],
        face_luma_mean=portrait_data["face_luma_mean"],
        face_saturation_mean=portrait_data["face_saturation_mean"],
        face_sharpness_mean=portrait_data.get("face_sharpness_mean"),
        subject_luma_estimate=portrait_data["subject_luma_estimate"],
        subject_saturation_mean=portrait_data["subject_saturation_mean"],
        subject_sharpness=portrait_data.get("subject_sharpness"),
        background_luma_estimate=portrait_data["background_luma_estimate"],
        background_saturation_mean=portrait_data["background_saturation_mean"],
        background_sharpness=portrait_data.get("background_sharpness"),
        face_exposure_status=str(portrait_data["face_exposure_status"]),
        subject_exposure_status=str(portrait_data["subject_exposure_status"]),
        background_exposure_status=str(portrait_data["background_exposure_status"]),
        portrait_exposure_status=str(portrait_data["portrait_exposure_status"]),
        exposure_type=exposure_type,
        highlight_recovery_type=highlight_recovery_type,
        portrait_focus_score=portrait_focus_score,
        highlight_clipping_ratio=float(portrait_data["highlight_clipping_ratio"]),
        subject_background_separation=float(portrait_data["subject_background_separation"]),
        portrait_repair_policy=str(portrait_data["portrait_repair_policy"]),
        color_type=color_type,
        noise_score=noise_score_raw,
        noise_level=noise_level,
        denoise_profile=denoise_profile,
        denoise_recommended=denoise_recommended,
        exposure_warning_reason=str(portrait_data["exposure_warning_reason"]),
        diagnostic_tags=diagnostic_tags,
        diagnostic_notes=diagnostic_notes,
        portrait_rejection_reason=str(portrait_data.get("portrait_rejection_reason", portrait_rejection_reason)),
        cleanup_candidates=cleanup_candidates,
        perf_timings=perf_timings,
        perf_notes=perf_notes,
    )


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS
