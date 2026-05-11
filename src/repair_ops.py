from __future__ import annotations

import time

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from models import AnalysisResult


def as_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0


def from_array(array: np.ndarray) -> Image.Image:
    clipped = np.clip(array, 0.0, 1.0)
    return Image.fromarray((clipped * 255.0).astype(np.uint8), mode="RGB")


def luma_map(array: np.ndarray) -> np.ndarray:
    return array[:, :, 0] * 0.299 + array[:, :, 1] * 0.587 + array[:, :, 2] * 0.114


def saturation_map(array: np.ndarray) -> np.ndarray:
    maxc = np.max(array, axis=2)
    minc = np.min(array, axis=2)
    return np.divide(maxc - minc, np.maximum(maxc, 1e-6), out=np.zeros_like(maxc), where=maxc > 1e-6)


def hue_map(array: np.ndarray) -> np.ndarray:
    r = array[:, :, 0]
    g = array[:, :, 1]
    b = array[:, :, 2]
    maxc = np.max(array, axis=2)
    minc = np.min(array, axis=2)
    delta = maxc - minc
    hue = np.zeros_like(maxc)

    mask = delta > 1e-6
    rmask = mask & (maxc == r)
    gmask = mask & (maxc == g)
    bmask = mask & (maxc == b)
    hue[rmask] = ((g[rmask] - b[rmask]) / delta[rmask]) % 6.0
    hue[gmask] = ((b[gmask] - r[gmask]) / delta[gmask]) + 2.0
    hue[bmask] = ((r[bmask] - g[bmask]) / delta[bmask]) + 4.0
    return hue / 6.0


def skin_like_mask(array: np.ndarray) -> np.ndarray:
    r = array[:, :, 0] * 255.0
    g = array[:, :, 1] * 255.0
    b = array[:, :, 2] * 255.0
    luma = luma_map(array)
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    return (
        (r >= 92.0)
        & (g >= 38.0)
        & (b >= 18.0)
        & (r > g)
        & (r > b)
        & (np.abs(r - g) >= 10.0)
        & ((maxc - minc) >= 10.0)
        & (cb >= 76.0)
        & (cb <= 128.0)
        & (cr >= 132.0)
        & (cr <= 178.0)
        & (luma >= 0.18)
        & (luma <= 0.92)
    )


def skin_redness_map(array: np.ndarray) -> np.ndarray:
    red = array[:, :, 0]
    green = array[:, :, 1]
    blue = array[:, :, 2]
    return np.clip(red - (green * 0.6 + blue * 0.4), 0.0, 1.0)


def _add_timing(perf_timings: dict[str, float] | None, key: str, started_at: float) -> None:
    if perf_timings is None:
        return
    perf_timings[key] = perf_timings.get(key, 0.0) + (time.perf_counter() - started_at) * 1000.0


def _get_runtime_cache(result: AnalysisResult | None) -> dict[str, object] | None:
    if result is None:
        return None
    cache = getattr(result, "_runtime_cache", None)
    if cache is None:
        cache = {}
        setattr(result, "_runtime_cache", cache)
    return cache


def _issue_score(result: AnalysisResult | None, code: str, default: float = 0.0) -> float:
    if result is None:
        return default
    issue = next((item for item in result.issues if item.code == code), None)
    return issue.score if issue is not None else default


def _has_tag(result: AnalysisResult | None, tag: str) -> bool:
    if result is None:
        return False
    return tag in result.diagnostic_tags


def _box_mask(size: tuple[int, int], box: tuple[int, int, int, int] | None) -> np.ndarray:
    width, height = size
    mask = np.zeros((height, width), dtype=np.float32)
    if box is None:
        return mask
    x0, y0, x1, y1 = box
    x0 = max(0, min(width, x0))
    x1 = max(0, min(width, x1))
    y0 = max(0, min(height, y0))
    y1 = max(0, min(height, y1))
    if x1 <= x0 or y1 <= y0:
        return mask
    mask[y0:y1, x0:x1] = 1.0
    return mask


def _scale_box(
    box: tuple[int, int, int, int],
    source_size: tuple[int, int],
    target_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    src_w, src_h = source_size
    dst_w, dst_h = target_size
    if src_w <= 0 or src_h <= 0:
        return box
    x0, y0, x1, y1 = box
    return (
        int(round(x0 * dst_w / src_w)),
        int(round(y0 * dst_h / src_h)),
        int(round(x1 * dst_w / src_w)),
        int(round(y1 * dst_h / src_h)),
    )


def _mask_to_size(mask: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    width, height = size
    if mask.shape == (height, width):
        return np.clip(mask, 0.0, 1.0)
    image = Image.fromarray((np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8), mode="L")
    resized = image.resize((width, height), Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float32) / 255.0


def _expand_crop_box(
    box: tuple[int, int, int, int] | None,
    size: tuple[int, int],
    *,
    pad_x_ratio: float,
    pad_y_ratio: float,
    min_pad: int = 24,
) -> tuple[int, int, int, int] | None:
    if box is None:
        return None
    width, height = size
    x0, y0, x1, y1 = box
    bw = max(1, x1 - x0)
    bh = max(1, y1 - y0)
    pad_x = max(min_pad, int(round(bw * pad_x_ratio)))
    pad_y = max(min_pad, int(round(bh * pad_y_ratio)))
    return (
        max(0, x0 - pad_x),
        max(0, y0 - pad_y),
        min(width, x1 + pad_x),
        min(height, y1 + pad_y),
    )


def _feather_mask(mask: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return np.clip(mask, 0.0, 1.0)
    image = Image.fromarray((np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8), mode="L")
    blurred = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.asarray(blurred, dtype=np.float32) / 255.0


def build_region_masks(
    result: AnalysisResult | None,
    size: tuple[int, int],
    *,
    perf_timings: dict[str, float] | None = None,
    working_max_side: int = 720,
) -> dict[str, np.ndarray]:
    cache = _get_runtime_cache(result)
    cache_key = ("region_masks", size, working_max_side)
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        if isinstance(cached, dict):
            return cached

    width, height = size
    max_side = max(width, height)
    if max_side > working_max_side:
        scale = working_max_side / max_side
        working_size = (
            max(48, int(round(width * scale))),
            max(48, int(round(height * scale))),
        )
    else:
        working_size = size
    work_w, work_h = working_size
    source_size = (result.width, result.height) if result is not None else size

    started_at = time.perf_counter()
    face_mask = np.zeros((work_h, work_w), dtype=np.float32)
    if result is not None:
        face_boxes = result.validated_face_boxes or result.face_boxes
        if face_boxes:
            for box in face_boxes:
                face_mask = np.maximum(face_mask, _box_mask(working_size, _scale_box(box, source_size, working_size)))
        elif result.face_region is not None:
            face_mask = np.maximum(face_mask, _box_mask(working_size, _scale_box(result.face_region, source_size, working_size)))

    subject_mask = np.zeros((work_h, work_w), dtype=np.float32)
    if result is not None and result.subject_boxes:
        for box in result.subject_boxes:
            subject_mask = np.maximum(subject_mask, _box_mask(working_size, _scale_box(box, source_size, working_size)))
    elif result is not None and result.subject_region is not None:
        subject_mask = _box_mask(working_size, _scale_box(result.subject_region, source_size, working_size))
    if not np.any(subject_mask) and np.any(face_mask):
        subject_mask = face_mask.copy()
    if np.any(subject_mask) and np.any(face_mask):
        subject_mask = np.maximum(subject_mask, face_mask)

    background_mask = np.clip(1.0 - subject_mask, 0.0, 1.0)
    highlight_mask = np.zeros((work_h, work_w), dtype=np.float32)
    if result is not None and result.highlight_region is not None:
        highlight_mask = _box_mask(working_size, _scale_box(result.highlight_region, source_size, working_size))
    if not np.any(highlight_mask):
        highlight_mask = background_mask.copy()
    _add_timing(perf_timings, "mask_build", started_at)

    started_at = time.perf_counter()
    face_mask = _feather_mask(face_mask, max(2.0, min(work_w, work_h) * 0.006))
    subject_mask = _feather_mask(subject_mask, max(4.0, min(work_w, work_h) * 0.012))
    background_mask = _feather_mask(background_mask, max(5.0, min(work_w, work_h) * 0.014))
    highlight_mask = _feather_mask(highlight_mask, max(6.0, min(work_w, work_h) * 0.016))
    _add_timing(perf_timings, "mask_feather", started_at)

    face_mask = _mask_to_size(face_mask, size)
    subject_mask = _mask_to_size(subject_mask, size)
    background_mask = _mask_to_size(background_mask, size)
    highlight_mask = _mask_to_size(highlight_mask, size)

    subject_only = np.clip(subject_mask - face_mask * 0.82, 0.0, 1.0)
    masks = {
        "face": face_mask,
        "subject": subject_mask,
        "subject_only": subject_only,
        "background": background_mask,
        "highlight": highlight_mask,
    }
    if cache is not None:
        cache[cache_key] = masks
    return masks


def _blend_arrays(base: np.ndarray, enhanced: np.ndarray, alpha_mask: np.ndarray) -> np.ndarray:
    alpha = np.clip(alpha_mask, 0.0, 1.0)[..., None]
    return base * (1.0 - alpha) + enhanced * alpha


def recover_highlights(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    arr = as_array(image)
    luma = luma_map(arr)
    threshold = 0.72
    if result is not None and result.portrait_likely and result.portrait_scene_type in {"high_key_portrait", "backlit_portrait"}:
        threshold = 0.82
    if result is not None and result.highlight_recovery_type == "unrecoverable_highlights":
        threshold = max(threshold, 0.86)
    mask = np.clip((luma - threshold) / max(0.10, 1.0 - threshold), 0.0, 1.0)
    strength = 0.08 + min(1.0, strength_scale) * 0.10
    if result is not None and result.highlight_recovery_type == "unrecoverable_highlights":
        strength = min(strength, 0.045)
    target_luma = np.clip(luma - mask * strength, 0.0, 1.0)
    ratio = np.divide(target_luma, np.maximum(luma, 1e-5), out=np.ones_like(luma), where=luma > 1e-5)
    arr = np.clip(arr * ratio[:, :, None], 0.0, 1.0)
    return from_array(arr)


def lift_shadows(image: Image.Image, result: AnalysisResult | None, strength_scale: float = 1.0) -> Image.Image:
    arr = as_array(image)
    luma = luma_map(arr)

    severity = 0.58
    if result is not None:
        under_issue = next((issue for issue in result.issues if issue.code == "underexposed"), None)
        if under_issue is not None:
            severity = max(severity, under_issue.score)

    portrait_subject_ok = _has_tag(result, "portrait_subject_ok") or (
        result is not None and result.portrait_exposure_status == "subject_normal"
    )
    dark_background_portrait = portrait_subject_ok and _has_tag(result, "dark_background")
    scene_guard = result is not None and result.exposure_type in {"high_contrast_window_scene", "silhouette_scene", "low_key_scene"}
    if portrait_subject_ok:
        severity = min(severity, 0.36)
    if scene_guard:
        severity = min(severity, 0.12)

    severity *= 0.72 + min(1.0, strength_scale) * 0.55
    gamma = max(0.64, 0.84 - severity * 0.12)
    lifted = np.power(np.clip(arr, 0.0, 1.0), gamma)

    mid_shadow_mask = np.clip((luma - 0.035) / 0.22, 0.0, 1.0) * np.clip((0.78 - luma) / 0.42, 0.0, 1.0)
    mid_shadow_mask = np.sqrt(np.clip(mid_shadow_mask * (1.30 + severity * 0.35), 0.0, 1.0))[..., None]

    result_arr = arr * (1.0 - mid_shadow_mask) + lifted * mid_shadow_mask
    lift_gain = 0.06 + severity * 0.04
    if portrait_subject_ok:
        lift_gain = min(lift_gain, 0.05)
    result_arr = result_arr + mid_shadow_mask * lift_gain * (1.0 - result_arr)

    deep_black_mask = np.clip((0.12 - luma) / 0.12, 0.0, 1.0)[..., None]
    black_guard = 0.18 + (0.08 if portrait_subject_ok else 0.0) + (0.08 if dark_background_portrait else 0.0)
    result_arr = result_arr * (1.0 - deep_black_mask * black_guard)
    if dark_background_portrait:
        preserve_dark = np.clip((0.20 - luma) / 0.20, 0.0, 1.0)[..., None] * 0.24
        result_arr = result_arr * (1.0 - preserve_dark) + arr * preserve_dark
    if scene_guard:
        atmosphere_guard = np.clip((0.28 - luma) / 0.28, 0.0, 1.0)[..., None] * 0.34
        result_arr = result_arr * (1.0 - atmosphere_guard) + arr * atmosphere_guard

    highlight_guard = np.clip((luma - 0.70) / 0.30, 0.0, 1.0)[..., None]
    result_arr = result_arr * (1.0 - highlight_guard * (0.06 + (0.04 if portrait_subject_ok else 0.0)))
    return from_array(result_arr)


def cool_down(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    arr = as_array(image)
    strength = (0.04 + _issue_score(result, "color_cast", 0.3) * 0.04) * (0.80 + min(1.0, strength_scale) * 0.40)
    arr[:, :, 0] *= 1.0 - strength
    arr[:, :, 1] *= 0.99
    arr[:, :, 2] *= 1.0 + strength * 0.85
    return from_array(arr)


def warm_up(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    arr = as_array(image)
    strength = (0.04 + _issue_score(result, "color_cast", 0.3) * 0.04) * (0.80 + min(1.0, strength_scale) * 0.40)
    arr[:, :, 0] *= 1.0 + strength
    arr[:, :, 2] *= 1.0 - strength
    return from_array(arr)


def add_magenta(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    arr = as_array(image)
    strength = (0.04 + _issue_score(result, "color_cast", 0.3) * 0.05) * (0.80 + min(1.0, strength_scale) * 0.40)
    arr[:, :, 1] *= 1.0 - strength
    arr[:, :, 0] *= 1.0 + strength * 0.45
    arr[:, :, 2] *= 1.0 + strength * 0.45
    return from_array(arr)


def add_green(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    arr = as_array(image)
    strength = (0.05 + _issue_score(result, "color_cast", 0.3) * 0.04) * (0.80 + min(1.0, strength_scale) * 0.40)
    arr[:, :, 1] *= 1.0 + strength
    arr[:, :, 0] *= 1.0 - strength * 0.55
    arr[:, :, 2] *= 1.0 - strength * 0.35
    return from_array(arr)


def auto_tone(image: Image.Image, strength_scale: float = 1.0) -> Image.Image:
    toned = ImageOps.autocontrast(image, cutoff=1)
    if strength_scale >= 0.99:
        return toned
    return Image.blend(image, toned, max(0.0, min(1.0, 0.55 + strength_scale * 0.35)))


def boost_contrast(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    score = max(_issue_score(result, "low_contrast"), _issue_score(result, "flat_tone"), _issue_score(result, "muted_colors"))
    factor = 1.06 + score * (0.08 + 0.10 * min(1.0, strength_scale))
    if _has_tag(result, "portrait_subject_ok"):
        factor = min(factor, 1.14)
    return ImageEnhance.Contrast(image).enhance(factor)


def boost_vibrance(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    score = _issue_score(result, "muted_colors", 0.4)
    working_max_side = 1500 if result is not None and result.portrait_likely else 1800
    working_image = image
    if max(image.size) > working_max_side:
        scale = working_max_side / max(image.size)
        working_image = image.resize(
            (
                max(64, int(round(image.width * scale))),
                max(64, int(round(image.height * scale))),
            ),
            Image.Resampling.BILINEAR,
        )

    arr = as_array(working_image)
    luma = luma_map(arr)
    sat = saturation_map(arr)
    hue = hue_map(arr)
    masks = build_region_masks(result, working_image.size) if result is not None else None

    subject_mask = masks["subject"] if masks is not None else np.ones_like(luma, dtype=np.float32)
    skin_mask = skin_like_mask(arr).astype(np.float32)
    if result is not None and result.portrait_likely:
        skin_mask *= np.clip(subject_mask * 1.15, 0.0, 1.0)

    warm_hue_mask = (((hue <= 0.10) | (hue >= 0.93)) & (sat >= 0.08)).astype(np.float32)
    sky_mask = (((hue >= 0.52) & (hue <= 0.70)) & (sat >= 0.08) & (luma >= 0.38)).astype(np.float32)
    neutral_guard = ((sat <= 0.10) & (luma >= 0.18) & (luma <= 0.92)).astype(np.float32)
    wood_mask = (((hue >= 0.05) & (hue <= 0.14)) & (sat >= 0.10) & (luma >= 0.18) & (luma <= 0.74)).astype(np.float32)
    low_sat_weight = np.power(np.clip((0.44 - sat) / 0.44, 0.0, 1.0), 1.35)
    highlight_guard = 1.0 - np.clip((luma - 0.72) / 0.20, 0.0, 1.0) * 0.72
    skin_guard = 1.0 - skin_mask * 0.78
    warm_guard = 1.0 - warm_hue_mask * 0.32
    scene_guard = 1.0 - sky_mask * 0.58 - neutral_guard * 0.38 - wood_mask * 0.24
    scene_guard = np.clip(scene_guard, 0.28, 1.0)

    base_strength = (0.05 + score * 0.12) * (0.75 + min(1.0, strength_scale) * 0.40)
    if result is not None and result.portrait_likely:
        base_strength = min(base_strength, 0.12)
    if result is not None and result.color_type == "restrained_natural":
        base_strength = min(base_strength, 0.08)
    if result is not None and result.color_type == "natural_vivid":
        base_strength = min(base_strength, 0.06)

    boost = base_strength * low_sat_weight * highlight_guard * skin_guard * warm_guard * scene_guard
    if result is not None and result.portrait_likely:
        non_skin_subject = np.clip(subject_mask * (1.0 - skin_mask), 0.0, 1.0)
        boost *= 1.0 + non_skin_subject * 0.16

    gray = luma[:, :, None]
    enhanced = gray + (arr - gray) * (1.0 + boost[:, :, None])

    if np.any(skin_mask > 0.01):
        redness_cap = arr[:, :, 0] + 0.018 + boost * 0.020
        enhanced[:, :, 0] = np.where(skin_mask > 0.0, np.minimum(enhanced[:, :, 0], redness_cap), enhanced[:, :, 0])
        skin_blend = np.clip(skin_mask * 0.42, 0.0, 0.42)[..., None]
        enhanced = enhanced * (1.0 - skin_blend) + arr * skin_blend

    output = from_array(enhanced)
    if output.size != image.size:
        output = output.resize(image.size, Image.Resampling.BILINEAR)
    return output


def reduce_saturation(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    score = _issue_score(result, "over_saturated", 0.4)
    arr = as_array(image)
    luma = luma_map(arr)
    saturation = saturation_map(arr)

    focus = np.clip((saturation - 0.68) / 0.24, 0.0, 1.0)
    extreme = np.clip((saturation - 0.84) / 0.12, 0.0, 1.0)
    brightness_weight = 0.30 + 0.70 * np.clip((luma - 0.18) / 0.36, 0.0, 1.0)
    green_dominant = (arr[:, :, 1] > arr[:, :, 0] * 1.08) & (arr[:, :, 1] > arr[:, :, 2] * 1.08)
    sky_mask = (((hue_map(arr) >= 0.52) & (hue_map(arr) <= 0.70)) & (saturation >= 0.10) & (luma >= 0.38)).astype(np.float32)
    foliage_guard = green_dominant.astype(np.float32) * np.clip((0.55 - luma) / 0.35, 0.0, 1.0) * 0.45

    strength = (0.06 + score * 0.15) * (0.70 + min(1.0, strength_scale) * 0.45)
    if result is not None and result.color_type == "natural_vivid":
        strength = min(strength, 0.09)
    weight = np.clip(focus * brightness_weight * (1.0 + extreme * 0.75) * (1.0 - foliage_guard), 0.0, 1.0)
    weight *= (1.0 - sky_mask * 0.32)

    gray = luma[:, :, None]
    blended = arr * (1.0 - strength * weight[:, :, None]) + gray * (strength * weight[:, :, None])
    return from_array(blended)


def boost_clarity(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    score = _issue_score(result, "out_of_focus", 0.35)
    radius = 1.2 + score * (0.4 + 0.5 * min(1.0, strength_scale))
    percent = int(95 + score * (25 + 40 * min(1.0, strength_scale)))
    return image.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=3))


def _edge_strength_map(luma: np.ndarray) -> np.ndarray:
    grad_y, grad_x = np.gradient(luma)
    return np.sqrt(grad_x * grad_x + grad_y * grad_y)


def reduce_noise(image: Image.Image, result: AnalysisResult | None = None, strength_scale: float = 1.0) -> Image.Image:
    scene_profile = getattr(result, "denoise_profile", "generic") if result is not None else "generic"
    issue_score = max(_issue_score(result, "high_noise"), _issue_score(result, "underexposed") * 0.55)
    analysis_noise = float(getattr(result, "noise_score", 0.0)) if result is not None else 0.0
    severity = max(issue_score, min(1.0, analysis_noise / 0.02))
    if severity <= 0.08:
        return image

    arr = as_array(image)
    luma = luma_map(arr)
    sat = saturation_map(arr)
    edge_strength = _edge_strength_map(luma)
    detail_guard = np.clip(edge_strength / 0.055, 0.0, 1.0)
    flat_region = np.clip((0.050 - edge_strength) / 0.050, 0.0, 1.0)
    shadow_mask = np.clip((0.58 - luma) / 0.38, 0.0, 1.0)
    highlight_mask = np.clip((luma - 0.72) / 0.22, 0.0, 1.0)
    sky_mask = (
        (hue_map(arr) >= 0.50)
        & (hue_map(arr) <= 0.70)
        & (sat <= 0.34)
        & (luma >= 0.36)
    ).astype(np.float32)

    masks = build_region_masks(result, image.size) if result is not None else None
    face_mask = masks["face"] if masks is not None else np.zeros_like(luma, dtype=np.float32)
    subject_mask = masks["subject"] if masks is not None else np.zeros_like(luma, dtype=np.float32)
    subject_only_mask = masks["subject_only"] if masks is not None else np.zeros_like(luma, dtype=np.float32)
    background_mask = masks["background"] if masks is not None else np.clip(1.0 - subject_mask, 0.0, 1.0)
    skin_mask = skin_like_mask(arr).astype(np.float32)
    face_skin_mask = np.clip(face_mask * skin_mask, 0.0, 1.0)

    base_radius = 0.55 + severity * 0.95 * (0.75 + min(1.0, strength_scale) * 0.55)
    strong_radius = base_radius + 0.65
    soft_blur = as_array(image.filter(ImageFilter.GaussianBlur(radius=base_radius)))
    strong_blur = as_array(image.filter(ImageFilter.GaussianBlur(radius=strong_radius)))
    median_size = 3 if severity < 0.72 else 5
    median_blur = as_array(image.filter(ImageFilter.MedianFilter(size=median_size)))

    strong_mix = np.clip((severity - 0.34) / 0.56, 0.0, 1.0)
    target = soft_blur * (1.0 - strong_mix) + (strong_blur * 0.65 + median_blur * 0.35) * strong_mix

    weight = flat_region * (0.10 + severity * 0.32) * (0.55 + min(1.0, strength_scale) * 0.70)
    weight *= 0.70 + shadow_mask * 0.30

    if scene_profile in {"night_high_iso", "indoor_shadow"}:
        weight *= 0.80 + shadow_mask * 0.65
        weight += sky_mask * 0.08
    elif scene_profile == "smooth_sky":
        weight = np.maximum(weight, sky_mask * (0.14 + severity * 0.24))
        weight *= 0.86 + background_mask * 0.22
    elif scene_profile == "portrait_protect":
        face_guard = np.clip(face_mask * (0.75 + detail_guard * 0.25), 0.0, 1.0)
        weight *= 1.0 - face_guard * 0.86
        weight += face_skin_mask * flat_region * shadow_mask * (0.02 + severity * 0.08)
        weight *= 0.82 + background_mask * 0.20
    elif scene_profile == "architecture_texture":
        weight *= 0.42 + shadow_mask * 0.18
        weight *= 1.0 - detail_guard * 0.92
        weight *= 1.0 - subject_only_mask * 0.20
    else:
        weight *= 0.82 + shadow_mask * 0.26

    if result is not None and result.portrait_likely:
        weight *= 1.0 - face_mask * detail_guard * 0.52
    if result is not None and result.scene_type in {"architecture_scene", "architecture_vivid_scene"}:
        weight *= 1.0 - detail_guard * 0.28

    weight *= 1.0 - highlight_mask * 0.25
    weight = np.clip(weight, 0.0, 0.60 if scene_profile != "smooth_sky" else 0.72)
    if float(np.max(weight)) < 0.02:
        return image

    return from_array(_blend_arrays(arr, target, weight))


def portrait_local_face_enhance(
    image: Image.Image,
    result: AnalysisResult | None,
    strength_scale: float = 1.0,
) -> Image.Image:
    if result is None or not result.portrait_likely:
        return image
    masks = build_region_masks(result, image.size)
    face_mask = masks["face"]
    if not np.any(face_mask > 0.02):
        return image

    original = as_array(image)
    face_boxes = result.validated_face_boxes or result.face_boxes or ([] if result.face_region is None else [result.face_region])
    for face_box in face_boxes:
        crop_box = _expand_crop_box(face_box, image.size, pad_x_ratio=0.70, pad_y_ratio=0.90)
        if crop_box is None:
            continue
        x0, y0, x1, y1 = crop_box
        crop = image.crop(crop_box)
        original_crop = original[y0:y1, x0:x1]
        clarity = crop.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(108 + strength_scale * 36), threshold=2))
        clarity_arr = as_array(clarity)
        contrast_arr = as_array(ImageEnhance.Contrast(crop).enhance(1.04 + strength_scale * 0.08))
        enhanced = clarity_arr * 0.56 + contrast_arr * 0.44
        alpha = face_mask[y0:y1, x0:x1] * (0.08 + strength_scale * 0.14)
        original[y0:y1, x0:x1] = _blend_arrays(original_crop, enhanced, alpha)
    return from_array(original)


def portrait_subject_midcontrast(
    image: Image.Image,
    result: AnalysisResult | None,
    strength_scale: float = 1.0,
) -> Image.Image:
    if result is None or not result.portrait_likely:
        return image
    masks = build_region_masks(result, image.size)
    subject_mask = masks["subject_only"]
    if not np.any(subject_mask > 0.02):
        return image

    crop_box = _expand_crop_box(result.subject_region, image.size, pad_x_ratio=0.18, pad_y_ratio=0.12)
    if crop_box is None:
        return image
    x0, y0, x1, y1 = crop_box
    crop = image.crop(crop_box)
    original = as_array(image)
    original_crop = original[y0:y1, x0:x1]
    working_crop = crop
    working_mask = subject_mask[y0:y1, x0:x1]
    if max(crop.size) > 1100:
        scale = 1100 / max(crop.size)
        resized_size = (max(64, int(round(crop.width * scale))), max(64, int(round(crop.height * scale))))
        working_crop = crop.resize(resized_size, Image.Resampling.BILINEAR)
        working_mask = _mask_to_size(working_mask, resized_size)

    working_crop_arr = as_array(working_crop)
    luma = luma_map(working_crop_arr)
    midtone_weight = np.clip(1.0 - np.abs(luma - 0.48) / 0.34, 0.0, 1.0)
    contrast_arr = as_array(ImageEnhance.Contrast(working_crop).enhance(1.05 + strength_scale * 0.10))
    if contrast_arr.shape[:2] != original_crop.shape[:2]:
        contrast_arr = as_array(from_array(contrast_arr).resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR))
        midtone_weight = _mask_to_size(midtone_weight, (x1 - x0, y1 - y0))
        working_mask = _mask_to_size(working_mask, (x1 - x0, y1 - y0))
    alpha = working_mask * midtone_weight * (0.07 + strength_scale * 0.16)
    original[y0:y1, x0:x1] = _blend_arrays(original_crop, contrast_arr, alpha)
    return from_array(original)


def portrait_dark_clothing_detail(
    image: Image.Image,
    result: AnalysisResult | None,
    strength_scale: float = 1.0,
) -> Image.Image:
    if result is None or not result.portrait_likely:
        return image
    masks = build_region_masks(result, image.size)
    subject_mask = masks["subject_only"]
    if not np.any(subject_mask > 0.02):
        return image

    crop_box = _expand_crop_box(result.subject_region, image.size, pad_x_ratio=0.12, pad_y_ratio=0.08)
    if crop_box is None:
        return image
    x0, y0, x1, y1 = crop_box
    original = as_array(image)
    original_crop = original[y0:y1, x0:x1]
    subject_crop = subject_mask[y0:y1, x0:x1]
    working_crop = image.crop(crop_box)
    working_mask = subject_crop
    if max(working_crop.size) > 1100:
        scale = 1100 / max(working_crop.size)
        resized_size = (max(64, int(round(working_crop.width * scale))), max(64, int(round(working_crop.height * scale))))
        working_crop = working_crop.resize(resized_size, Image.Resampling.BILINEAR)
        working_mask = _mask_to_size(working_mask, resized_size)

    working_crop_arr = as_array(working_crop)
    luma = luma_map(working_crop_arr)
    sat = saturation_map(working_crop_arr)
    dark_clothing_mask = np.clip(working_mask * ((luma >= 0.05) & (luma <= 0.28) & (sat <= 0.40)).astype(np.float32), 0.0, 1.0)
    if not np.any(dark_clothing_mask > 0.01):
        return image
    if float(np.mean(dark_clothing_mask > 0.04)) > 0.42:
        strength_scale *= 0.72

    clarity = working_crop.filter(ImageFilter.UnsharpMask(radius=1.0, percent=int(95 + strength_scale * 30), threshold=3))
    enhanced = as_array(clarity)
    if enhanced.shape[:2] != original_crop.shape[:2]:
        enhanced = as_array(from_array(enhanced).resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR))
        dark_clothing_mask = _mask_to_size(dark_clothing_mask, (x1 - x0, y1 - y0))
    alpha = dark_clothing_mask * (0.05 + strength_scale * 0.10)
    original[y0:y1, x0:x1] = _blend_arrays(original_crop, enhanced, alpha)
    return from_array(original)


def protect_high_key_background(
    image: Image.Image,
    result: AnalysisResult | None,
    strength_scale: float = 1.0,
    *,
    original_image: Image.Image | None = None,
) -> Image.Image:
    if result is None or original_image is None:
        return image
    if result.portrait_scene_type not in {"high_key_portrait", "backlit_portrait"}:
        return image

    current = as_array(image)
    original = as_array(original_image)
    current_luma = luma_map(current)
    original_luma = luma_map(original)
    masks = build_region_masks(result, image.size)

    highlight_focus = ((original_luma >= 0.82) | (current_luma >= 0.80)).astype(np.float32)
    background_highlight_mask = masks["background"] * masks["highlight"] * highlight_focus
    if not np.any(background_highlight_mask > 0.02):
        background_highlight_mask = masks["background"] * highlight_focus
    alpha = background_highlight_mask * (0.12 + strength_scale * 0.24)
    blended = _blend_arrays(current, original, alpha)
    return from_array(blended)
