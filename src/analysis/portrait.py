from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from models import FaceCandidate, FaceStat

from .common import (
    box_iou,
    box_ring_mask,
    cleanup_binary_mask,
    component_boxes,
    crop_mask,
    edge_density,
    expanded_box,
    gradient_maps,
    laplacian_variance,
    mask_from_box,
    masked_laplacian_variance,
    merge_boxes,
    merge_region_boxes,
    region_box,
    region_mean,
    region_median,
    region_std,
    saturation_map,
    skin_mask_ycbcr,
    safe_mean,
)


def _cleanup_face_severity(score: float) -> str:
    if score >= 0.82:
        return "critical"
    if score >= 0.64:
        return "high"
    if score >= 0.46:
        return "medium"
    return "low"


def face_candidate_metrics(
    rgb: np.ndarray,
    gray: np.ndarray,
    box: tuple[int, int, int, int],
) -> dict[str, float]:
    height, width = gray.shape
    x0, y0, x1, y1 = box
    if x1 - x0 < 4 or y1 - y0 < 4:
        return {}

    crop_rgb = rgb[y0:y1, x0:x1]
    crop_gray = gray[y0:y1, x0:x1]
    sat = saturation_map(crop_rgb)
    skin_mask = skin_mask_ycbcr(crop_rgb, crop_gray)
    center_mask = crop_mask((y1 - y0, x1 - x0), (0, 0, x1 - x0, y1 - y0), 0.18)
    inner_mask = crop_mask((y1 - y0, x1 - x0), (0, 0, x1 - x0, y1 - y0), 0.10)
    ring_mask = np.ones_like(inner_mask, dtype=bool) & ~inner_mask

    neutral_mask = (sat < 0.12) & (crop_gray > 0.20) & (crop_gray < 0.90)
    green_mask = (crop_rgb[:, :, 1] > crop_rgb[:, :, 0] * 1.08) & (crop_rgb[:, :, 1] > crop_rgb[:, :, 2] * 1.08)
    warm_mask = ((crop_rgb[:, :, 0] > crop_rgb[:, :, 1] * 1.04) & (crop_rgb[:, :, 0] > crop_rgb[:, :, 2] * 1.10))
    left = crop_gray[:, : max(1, crop_gray.shape[1] // 2)]
    right = crop_gray[:, crop_gray.shape[1] - left.shape[1] :]
    symmetry = 1.0 - min(1.0, float(np.mean(np.abs(left[:, : right.shape[1]] - np.flip(right, axis=1)))))

    grad_x, grad_y, grad = gradient_maps(crop_gray)
    frame = expanded_box(box, gray.shape, 0.50, 0.62)
    fx0, fy0, fx1, fy1 = frame
    frame_gray = gray[fy0:fy1, fx0:fx1]
    frame_sat = saturation_map(rgb[fy0:fy1, fx0:fx1])
    if frame_gray.size:
        top_band = frame_gray[: max(2, frame_gray.shape[0] // 10), :]
        bottom_band = frame_gray[-max(2, frame_gray.shape[0] // 10) :, :]
        left_band = frame_gray[:, : max(2, frame_gray.shape[1] // 10)]
        right_band = frame_gray[:, -max(2, frame_gray.shape[1] // 10) :]
        border_energy = safe_mean(
            [
                np.mean(np.abs(np.diff(top_band, axis=0))) if top_band.shape[0] > 1 else 0.0,
                np.mean(np.abs(np.diff(bottom_band, axis=0))) if bottom_band.shape[0] > 1 else 0.0,
                np.mean(np.abs(np.diff(left_band, axis=1))) if left_band.shape[1] > 1 else 0.0,
                np.mean(np.abs(np.diff(right_band, axis=1))) if right_band.shape[1] > 1 else 0.0,
            ]
        )
        frame_edge_density = edge_density(frame_gray, threshold=0.07)
        border_neutral_ratio = float(np.mean((frame_sat < 0.16) & (frame_gray > 0.16) & (frame_gray < 0.92)))
    else:
        border_energy = 0.0
        frame_edge_density = 0.0
        border_neutral_ratio = 0.0

    upper_half = crop_gray[: max(1, crop_gray.shape[0] // 2), :]
    lower_half = crop_gray[crop_gray.shape[0] // 2 :, :]
    vertical_skin_balance = abs(
        float(np.mean(skin_mask[: max(1, skin_mask.shape[0] // 2), :]))
        - float(np.mean(skin_mask[skin_mask.shape[0] // 2 :, :]))
    )

    return {
        "skin_ratio": float(np.mean(skin_mask)),
        "inner_skin_ratio": float(np.mean(skin_mask & inner_mask) / max(1e-6, np.mean(inner_mask))),
        "center_skin_ratio": float(np.mean(skin_mask & center_mask) / max(1e-6, np.mean(center_mask))),
        "ring_skin_ratio": float(np.mean(skin_mask & ring_mask) / max(1e-6, np.mean(ring_mask))),
        "neutral_ratio": float(np.mean(neutral_mask)),
        "green_ratio": float(np.mean(green_mask)),
        "warm_ratio": float(np.mean(warm_mask)),
        "symmetry": symmetry,
        "contrast": float(np.std(crop_gray)),
        "inner_luma_std": region_std(crop_gray, inner_mask),
        "inner_sat_std": region_std(sat, inner_mask),
        "inner_sharpness": laplacian_variance(crop_gray) if crop_gray.shape[0] >= 3 and crop_gray.shape[1] >= 3 else 0.0,
        "edge_density": frame_edge_density,
        "border_energy": border_energy,
        "border_neutral_ratio": border_neutral_ratio,
        "vertical_skin_balance": vertical_skin_balance,
        "top_bottom_luma_gap": abs(float(np.mean(upper_half)) - float(np.mean(lower_half))) if upper_half.size and lower_half.size else 0.0,
    }


def _classify_face_candidate(
    image_size: tuple[int, int],
    box: tuple[int, int, int, int],
    score: float,
    metrics: dict[str, float],
) -> tuple[str, float, bool, bool, list[str]]:
    width, height = image_size
    bw = max(1, box[2] - box[0])
    bh = max(1, box[3] - box[1])
    box_area_ratio = (bw * bh) / max(1.0, float(width * height))
    aspect_ratio = bw / max(1.0, float(bh))
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    centrality = 1.0 - min(1.0, abs(cx - width / 2.0) / max(1.0, width * 0.62))
    confidence = min(
        1.0,
        score * 0.38
        + centrality * 0.12
        + min(1.0, box_area_ratio / 0.010) * 0.08
        + metrics.get("inner_skin_ratio", 0.0) * 0.16
        + metrics.get("center_skin_ratio", 0.0) * 0.10
        + metrics.get("symmetry", 0.0) * 0.10
        + metrics.get("inner_luma_std", 0.0) * 0.18
        + metrics.get("inner_sat_std", 0.0) * 0.10,
    )

    rejection_reasons: list[str] = []
    classification = "texture_false_positive"
    is_real_face = False
    is_frontal = False

    artwork_score = 0.0
    if metrics.get("border_energy", 0.0) > 0.06:
        artwork_score += 0.30
    if metrics.get("border_neutral_ratio", 0.0) > 0.46:
        artwork_score += 0.24
    if metrics.get("border_neutral_ratio", 0.0) > 0.72 and metrics.get("inner_sharpness", 0.0) < 0.00018:
        artwork_score += 0.26
    if metrics.get("edge_density", 0.0) > 0.16:
        artwork_score += 0.18
    if metrics.get("inner_sat_std", 0.0) < 0.055:
        artwork_score += 0.16
    if metrics.get("inner_luma_std", 0.0) < 0.075:
        artwork_score += 0.12
    if metrics.get("neutral_ratio", 0.0) > 0.56:
        artwork_score += 0.12
    if metrics.get("skin_ratio", 0.0) > 0.88 and metrics.get("warm_ratio", 0.0) > 0.82 and metrics.get("top_bottom_luma_gap", 0.0) < 0.04:
        artwork_score += 0.18

    if bh < height * 0.035 or bw < width * 0.024:
        confidence *= 0.72
        rejection_reasons.append("尺寸过小")
    if box_area_ratio < 0.0014:
        confidence *= 0.60
        rejection_reasons.append("面积占比过低")
    if box_area_ratio > 0.060:
        confidence *= 0.76
        rejection_reasons.append("面积占比异常偏大")
    if aspect_ratio < 0.60 or aspect_ratio > 1.42:
        confidence *= 0.68
        rejection_reasons.append("宽高比不符合人脸")
    if cy < height * 0.08 or cy > height * 0.88:
        confidence *= 0.72
        rejection_reasons.append("位置过靠近画面边缘")
    if cy > height * 0.68:
        confidence *= 0.54
        rejection_reasons.append("位置过低，更像局部物体或衣物")
    if metrics.get("inner_skin_ratio", 0.0) < 0.055:
        confidence *= 0.44
        rejection_reasons.append("中心肤色占比不足")
    elif metrics.get("center_skin_ratio", 0.0) < 0.08 and metrics.get("skin_ratio", 0.0) < 0.10:
        confidence *= 0.64
        rejection_reasons.append("主体中心肤色偏弱")
    if metrics.get("ring_skin_ratio", 0.0) > metrics.get("inner_skin_ratio", 0.0) + 0.08:
        confidence *= 0.74
        rejection_reasons.append("肤色主要出现在边缘，缺少稳定脸部结构")
    if metrics.get("green_ratio", 0.0) > 0.28 and metrics.get("inner_skin_ratio", 0.0) < 0.12:
        confidence *= 0.36
        rejection_reasons.append("区域偏绿且肤色不足，疑似绿植纹理")
    elif metrics.get("green_ratio", 0.0) > 0.20:
        confidence *= 0.74
        rejection_reasons.append("绿色纹理干扰较强")
    if metrics.get("neutral_ratio", 0.0) > 0.72 and metrics.get("inner_skin_ratio", 0.0) < 0.10:
        confidence *= 0.64
        rejection_reasons.append("中性纹理占比过高，疑似背景边缘或文字")
    if metrics.get("symmetry", 0.0) < 0.34:
        confidence *= 0.62
        rejection_reasons.append("局部结构对称性不足")
    elif metrics.get("symmetry", 0.0) < 0.44:
        confidence *= 0.84
        rejection_reasons.append("局部结构偏弱")
    if metrics.get("vertical_skin_balance", 0.0) < 0.12 and metrics.get("inner_skin_ratio", 0.0) < 0.15:
        confidence *= 0.74
        rejection_reasons.append("上下肤色分布不稳定")
    if metrics.get("contrast", 0.0) < 0.035 and metrics.get("inner_skin_ratio", 0.0) < 0.10:
        confidence *= 0.80
        rejection_reasons.append("局部层次过低")

    if artwork_score >= 0.54:
        classification = "artwork_face"
        confidence *= 0.72
        rejection_reasons.append("周边存在画布/海报式矩形边界，更像画作或印刷人脸")
    elif metrics.get("symmetry", 0.0) >= 0.52 and metrics.get("inner_skin_ratio", 0.0) >= 0.10 and confidence >= 0.58:
        classification = "real_frontal_face"
        is_real_face = True
        is_frontal = True
    elif metrics.get("symmetry", 0.0) >= 0.44 and metrics.get("inner_skin_ratio", 0.0) >= 0.08 and confidence >= 0.54:
        classification = "real_near_frontal_face"
        is_real_face = True
    elif metrics.get("symmetry", 0.0) >= 0.32 and metrics.get("skin_ratio", 0.0) >= 0.06:
        classification = "non_frontal_face_candidate"
        rejection_reasons.append("疑似侧脸或非正面人脸，未纳入真人正面人像策略")
    elif metrics.get("warm_ratio", 0.0) > 0.15 and metrics.get("inner_skin_ratio", 0.0) < 0.05:
        classification = "back_view_proxy"
        rejection_reasons.append("更像背身人物或局部暖色衣物，不按正面人脸处理")

    accepted = is_real_face and confidence >= (0.56 if is_frontal else 0.60)
    if not accepted and classification == "real_near_frontal_face":
        rejection_reasons.append("真人近正面候选置信度不足")
    if classification == "artwork_face":
        is_real_face = False
        is_frontal = False
    return classification, float(confidence), accepted, is_frontal, rejection_reasons


def _detect_people_context(
    image: Image.Image,
) -> dict[str, Any]:
    max_side = max(image.width, image.height)
    if max_side > 360:
        scale = 360.0 / max_side
        preview = image.resize(
            (max(64, int(round(image.width * scale))), max(64, int(round(image.height * scale)))),
            Image.Resampling.BILINEAR,
        )
    else:
        preview = image.copy()

    arr = np.asarray(preview, dtype=np.float32)
    gray = (arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114) / 255.0
    sat = saturation_map(arr)
    dark_mask = gray < 0.28
    clothing_mask = (sat > 0.14) & (gray > 0.05) & (gray < 0.70)
    candidate_mask = cleanup_binary_mask(dark_mask | clothing_mask)
    components = component_boxes(candidate_mask)
    if not components:
        return {"score": 0.0, "box": None, "kind": "none"}

    best_score = 0.0
    best_box: tuple[int, int, int, int] | None = None
    for x0, y0, x1, y1, area in components:
        bw = x1 - x0
        bh = y1 - y0
        if area < max(64, int(arr.shape[0] * arr.shape[1] * 0.015)):
            continue
        if bh < arr.shape[0] * 0.28 or bw < arr.shape[1] * 0.10:
            continue
        aspect = bw / max(1, bh)
        if aspect < 0.16 or aspect > 0.95:
            continue
        cx = (x0 + x1) / 2.0
        side_score = max(0.0, 1.0 - min(1.0, abs(cx - arr.shape[1] * 0.18) / (arr.shape[1] * 0.30)))
        side_score = max(side_score, 1.0 - min(1.0, abs(cx - arr.shape[1] * 0.82) / (arr.shape[1] * 0.30)))
        head_band = gray[y0 : y0 + max(2, bh // 4), x0:x1]
        torso_band = sat[y0 + max(1, bh // 4) : y1, x0:x1]
        hair_like = float(np.mean(head_band < 0.18)) if head_band.size else 0.0
        torso_color = float(np.mean(torso_band > 0.12)) if torso_band.size else 0.0
        score = min(1.0, area / max(1.0, arr.shape[0] * arr.shape[1] * 0.16)) * 0.42 + side_score * 0.28 + hair_like * 0.18 + torso_color * 0.18
        if score > best_score:
            best_score = score
            best_box = (x0, y0, x1, y1)

    if best_box is None or best_score < 0.42:
        return {"score": best_score, "box": None, "kind": "none"}

    scale_x = image.width / preview.width
    scale_y = image.height / preview.height
    return {
        "score": float(best_score),
        "box": (
            int(round(best_box[0] * scale_x)),
            int(round(best_box[1] * scale_y)),
            int(round(best_box[2] * scale_x)),
            int(round(best_box[3] * scale_y)),
        ),
        "kind": "back_view_person_context",
    }


def detect_portrait_regions(image: Image.Image) -> dict[str, Any]:
    max_side = max(image.width, image.height)
    if max_side > 320:
        scale = 320.0 / max_side
        small = image.resize(
            (max(48, int(round(image.width * scale))), max(48, int(round(image.height * scale)))),
            Image.Resampling.BILINEAR,
        )
    else:
        small = image.copy()

    small_arr = np.asarray(small, dtype=np.float32)
    small_gray = (small_arr[:, :, 0] * 0.299 + small_arr[:, :, 1] * 0.587 + small_arr[:, :, 2] * 0.114) / 255.0
    skin_mask = skin_mask_ycbcr(small_arr, small_gray)
    cleaned = cleanup_binary_mask(skin_mask)
    height, width = cleaned.shape
    central_slice = cleaned[height // 8 : max(height // 8 + 1, height * 7 // 8), width // 6 : max(width // 6 + 1, width * 5 // 6)]
    central_skin_ratio = float(np.mean(central_slice)) if central_slice.size else 0.0

    total_area = float(height * width)
    center_x = width / 2.0
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for x0, y0, x1, y1, area in component_boxes(cleaned):
        bw = x1 - x0
        bh = y1 - y0
        if bw < 6 or bh < 8:
            continue
        if area < max(36, int(total_area * 0.0007)):
            continue
        area_ratio = area / total_area
        if area_ratio > 0.18:
            continue
        aspect = bw / max(bh, 1)
        if aspect < 0.45 or aspect > 1.85:
            continue
        fill_ratio = area / max(1, bw * bh)
        if fill_ratio < 0.16:
            continue
        y_center_ratio = ((y0 + y1) / 2.0) / max(height, 1)
        if y_center_ratio > 0.88:
            continue
        box_luma = float(np.mean(small_gray[y0:y1, x0:x1])) if (y1 > y0 and x1 > x0) else 0.0
        if box_luma < 0.24 or box_luma > 0.92:
            continue
        center_score = 1.0 - min(1.0, abs(((x0 + x1) / 2.0) - center_x) / max(1.0, width * 0.65))
        size_score = min(1.0, area_ratio / 0.012)
        score = fill_ratio * 0.42 + center_score * 0.24 + size_score * 0.18 + min(1.0, box_luma / 0.55) * 0.08 + central_skin_ratio * 0.08
        if score < 0.30:
            continue
        candidates.append((score, (x0, y0, x1, y1)))

    candidates.sort(key=lambda item: item[0], reverse=True)
    if len(candidates) < 2:
        warm_mask = (
            (small_arr[:, :, 0] > small_arr[:, :, 1] * 1.04)
            & (small_arr[:, :, 0] > small_arr[:, :, 2] * 1.10)
            & (small_gray >= 0.18)
            & (small_gray <= 0.88)
        )
        global_warm_ratio = float(np.mean(warm_mask))
        global_skin_ratio = float(np.mean(skin_mask))
        if global_warm_ratio >= 0.18 or global_skin_ratio >= 0.08:
            warm_cleaned = warm_mask
            for x0, y0, x1, y1, area in component_boxes(warm_cleaned):
                bw = x1 - x0
                bh = y1 - y0
                if bw < 5 or bh < 7:
                    continue
                area_ratio = area / total_area
                if area_ratio < 0.0005 or area_ratio > 0.12:
                    continue
                aspect = bw / max(1, bh)
                if aspect < 0.38 or aspect > 1.95:
                    continue
                box_luma = float(np.mean(small_gray[y0:y1, x0:x1])) if (y1 > y0 and x1 > x0) else 0.0
                center_score = 1.0 - min(1.0, abs(((x0 + x1) / 2.0) - center_x) / max(1.0, width * 0.70))
                score = area_ratio * 12.0 + center_score * 0.18 + min(1.0, box_luma / 0.60) * 0.08
                if score >= 0.18:
                    candidates.append((score, (x0, y0, x1, y1)))
            if not candidates:
                scan_heights = [max(14, int(round(min(height, width) * ratio))) for ratio in (0.10, 0.14, 0.18, 0.24)]
                scanned: list[tuple[float, tuple[int, int, int, int]]] = []
                for bh in scan_heights:
                    bw = max(10, int(round(bh * 0.78)))
                    step = max(4, bh // 4)
                    for y0 in range(0, max(1, height - bh + 1), step):
                        for x0 in range(0, max(1, width - bw + 1), step):
                            x1 = min(width, x0 + bw)
                            y1 = min(height, y0 + bh)
                            crop = small_gray[y0:y1, x0:x1]
                            if crop.shape[0] < 8 or crop.shape[1] < 6:
                                continue
                            warm_crop = warm_mask[y0:y1, x0:x1]
                            warm_ratio = float(np.mean(warm_crop))
                            if warm_ratio < 0.12:
                                continue
                            left = crop[:, : max(1, crop.shape[1] // 2)]
                            right = crop[:, crop.shape[1] - left.shape[1] :]
                            symmetry = 1.0 - min(1.0, float(np.mean(np.abs(left[:, : right.shape[1]] - np.flip(right, axis=1)))))
                            if symmetry < 0.42:
                                continue
                            box_luma = float(np.mean(crop))
                            center_score = 1.0 - min(1.0, abs(((x0 + x1) / 2.0) - center_x) / max(1.0, width * 0.72))
                            score = warm_ratio * 0.44 + symmetry * 0.34 + center_score * 0.16 + min(1.0, box_luma / 0.60) * 0.06
                            if score >= 0.26:
                                scanned.append((score, (x0, y0, x1, y1)))
                scanned.sort(key=lambda item: item[0], reverse=True)
                candidates.extend(scanned[:8])
        candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[:12]
    selected_small_boxes = merge_boxes([box for _, box in selected])[:12]

    scale_x = image.width / max(1, width)
    scale_y = image.height / max(1, height)
    full_arr = np.asarray(image, dtype=np.float32)
    full_gray = (full_arr[:, :, 0] * 0.299 + full_arr[:, :, 1] * 0.587 + full_arr[:, :, 2] * 0.114) / 255.0
    raw_face_candidates = [
        (
            max(0, int(round(x0 * scale_x))),
            max(0, int(round(y0 * scale_y))),
            min(image.width, int(round(x1 * scale_x))),
            min(image.height, int(round(y1 * scale_y))),
        )
        for x0, y0, x1, y1 in selected_small_boxes
    ]
    raw_face_candidates = [box for box in raw_face_candidates if box[2] - box[0] >= 8 and box[3] - box[1] >= 8]
    scored_candidates = [
        (
            score,
            (
                max(0, int(round(box[0] * scale_x))),
                max(0, int(round(box[1] * scale_y))),
                min(image.width, int(round(box[2] * scale_x))),
                min(image.height, int(round(box[3] * scale_y))),
            ),
        )
        for score, box in selected
    ]

    face_candidates: list[FaceCandidate] = []
    validated_face_boxes: list[tuple[int, int, int, int]] = []
    face_confidences: list[float] = []
    accepted_reals: list[tuple[tuple[int, int, int, int], float]] = []
    classification_counts: dict[str, int] = {}
    for score, box in scored_candidates:
        metrics = face_candidate_metrics(full_arr, full_gray, box)
        classification, confidence, accepted, is_frontal, rejection_reasons = _classify_face_candidate(
            image.size,
            box,
            score,
            metrics,
        )
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
        candidate = FaceCandidate(
            box=box,
            detector_score=float(score),
            confidence=float(confidence),
            accepted=accepted,
            classification=classification,
            is_real_face=accepted,
            is_frontal=is_frontal if accepted else False,
            rejection_reasons=[] if accepted else rejection_reasons,
        )
        face_candidates.append(candidate)
        if accepted:
            accepted_reals.append((box, float(confidence)))

    if accepted_reals:
        deduped: list[tuple[tuple[int, int, int, int], float]] = []
        for box, confidence in sorted(accepted_reals, key=lambda item: item[1], reverse=True):
            if any(box_iou(box, kept_box) >= 0.30 for kept_box, _ in deduped):
                continue
            deduped.append((box, confidence))
        accepted_reals = deduped[:6]
        validated_face_boxes = [box for box, _ in accepted_reals]
        face_confidences = [confidence for _, confidence in accepted_reals]

    rejection_reason = ""
    if raw_face_candidates and not validated_face_boxes:
        top_reasons: list[str] = []
        for candidate in sorted(face_candidates, key=lambda item: item.confidence, reverse=True):
            if candidate.accepted:
                continue
            if candidate.classification == "artwork_face":
                top_reasons.append("候选更像画作/海报中的人脸")
            top_reasons.extend(candidate.rejection_reasons[:1])
            if len(top_reasons) >= 3:
                break
        reason_suffix = f" 主要原因：{'、'.join(top_reasons[:3])}。" if top_reasons else ""
        rejection_reason = f"检测到 {len(raw_face_candidates)} 个人脸候选，但未达到真人正面人像阈值。{reason_suffix}"

    context_info = _detect_people_context(image)
    portrait_type = "non_portrait"
    if validated_face_boxes:
        frontal_count = sum(1 for item in face_candidates if item.accepted and item.is_frontal)
        if len(validated_face_boxes) >= 2:
            portrait_type = "real_multi_portrait"
        elif frontal_count >= 1:
            portrait_type = "real_frontal_portrait"
        else:
            portrait_type = "real_near_frontal_portrait"
    elif classification_counts.get("artwork_face", 0) > 0:
        portrait_type = "artwork_face_context"
    elif classification_counts.get("non_frontal_face_candidate", 0) > 0:
        portrait_type = "side_back_view_person"
    elif context_info.get("box") is not None and context_info.get("score", 0.0) >= 0.42:
        portrait_type = "back_view_person_context"

    return {
        "raw_face_candidates": raw_face_candidates[:12],
        "validated_face_boxes": validated_face_boxes,
        "face_confidences": face_confidences,
        "face_candidates": face_candidates,
        "face_confidence": float(max(face_confidences, default=0.0)),
        "central_skin_ratio": central_skin_ratio,
        "portrait_rejection_reason": rejection_reason,
        "portrait_type": portrait_type,
        "rejected_face_count": len([candidate for candidate in face_candidates if not candidate.accepted]),
        "people_context_box": context_info.get("box"),
        "people_context_score": float(context_info.get("score", 0.0)),
    }


def confirm_portrait(
    image_size: tuple[int, int],
    raw_face_candidates: list[tuple[int, int, int, int]],
    validated_face_boxes: list[tuple[int, int, int, int]],
    face_confidences: list[float],
    skin_ratio: float,
    central_skin_ratio: float,
    portrait_type: str,
) -> tuple[bool, str]:
    if portrait_type in {"artwork_face_context", "back_view_person_context", "side_back_view_person"}:
        if portrait_type == "artwork_face_context":
            return False, "检测到画作/非真实人像中的脸部候选，未按真人人像策略处理。"
        return False, "检测到背身/非正面人物上下文，未按真人正面人像策略处理。"
    if not validated_face_boxes:
        if raw_face_candidates:
            return False, f"检测到 {len(raw_face_candidates)} 个人脸候选，但未启用 portrait-aware。"
        return False, ""

    best_conf = max(face_confidences, default=0.0)
    avg_conf = float(np.mean(np.asarray(face_confidences, dtype=np.float32))) if face_confidences else 0.0
    avg_face_height_ratio = float(
        np.mean(np.asarray([(box[3] - box[1]) / max(1, image_size[1]) for box in validated_face_boxes], dtype=np.float32))
    )
    if len(validated_face_boxes) >= 2 and avg_conf >= 0.50:
        return True, ""
    if len(validated_face_boxes) == 1 and best_conf >= 0.58 and avg_face_height_ratio >= 0.045 and (central_skin_ratio >= 0.010 or skin_ratio >= 0.008):
        return True, ""
    if raw_face_candidates:
        return False, f"检测到 {len(raw_face_candidates)} 个人脸候选，但有效真人正面人脸置信度不足。"
    return False, "有效真人正面人脸数量或置信度不足。"


def face_stats(
    gray: np.ndarray,
    saturation: np.ndarray,
    rgb: np.ndarray,
    face_boxes: list[tuple[int, int, int, int]],
    face_confidences: list[float],
) -> list[FaceStat]:
    stats: list[FaceStat] = []
    redness_map = np.clip((rgb[:, :, 0] / 255.0) - ((rgb[:, :, 1] / 255.0) * 0.6 + (rgb[:, :, 2] / 255.0) * 0.4), 0.0, 1.0)
    for index, box in enumerate(face_boxes):
        x0, y0, x1, y1 = box
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        gray_region = gray[y0:y1, x0:x1]
        sat_region = saturation[y0:y1, x0:x1]
        red_region = redness_map[y0:y1, x0:x1]
        sharpness = laplacian_variance(gray_region) if gray_region.shape[0] >= 3 and gray_region.shape[1] >= 3 else None
        stats.append(
            FaceStat(
                box=box,
                confidence=float(face_confidences[index]) if index < len(face_confidences) else 0.0,
                luma_mean=float(np.mean(gray_region)),
                saturation_mean=float(np.mean(sat_region)),
                sharpness=sharpness,
                redness=float(np.mean(red_region)),
            )
        )
    return stats


def _build_mask_from_boxes(shape: tuple[int, int], boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    for box in boxes:
        mask |= mask_from_box(shape, box)
    return mask


def _expand_subject_boxes(
    shape: tuple[int, int],
    face_boxes: list[tuple[int, int, int, int]],
    portrait_likely: bool,
    people_context_box: tuple[int, int, int, int] | None,
) -> list[tuple[int, int, int, int]]:
    if face_boxes:
        return [
            expanded_box(box, shape, 0.60 if portrait_likely else 0.42, 1.65 if portrait_likely else 1.10)
            for box in face_boxes
        ]
    if people_context_box is not None:
        return [expanded_box(people_context_box, shape, 0.10, 0.08)]
    return []


def _build_subject_mask(
    shape: tuple[int, int],
    face_boxes: list[tuple[int, int, int, int]],
    portrait_likely: bool,
    people_context_box: tuple[int, int, int, int] | None,
) -> np.ndarray:
    subject_boxes = _expand_subject_boxes(shape, face_boxes, portrait_likely, people_context_box)
    if not subject_boxes:
        return np.zeros(shape, dtype=bool)
    return _build_mask_from_boxes(shape, subject_boxes)


def analyze_portrait_regions(
    rgb: np.ndarray,
    gray: np.ndarray,
    saturation: np.ndarray,
    face_boxes: list[tuple[int, int, int, int]],
    face_confidences: list[float],
    raw_face_candidates: list[tuple[int, int, int, int]],
    face_candidates: list[FaceCandidate],
    portrait_likely: bool,
    portrait_rejection_reason: str,
    portrait_type: str,
    people_context_box: tuple[int, int, int, int] | None,
) -> dict[str, Any]:
    face_mask = _build_mask_from_boxes(gray.shape, face_boxes) if face_boxes else np.zeros_like(gray, dtype=bool)
    subject_mask = _build_subject_mask(gray.shape, face_boxes, portrait_likely, people_context_box)
    subject_boxes = _expand_subject_boxes(gray.shape, face_boxes, portrait_likely, people_context_box)
    if not np.any(subject_mask) and np.any(face_mask):
        subject_mask = face_mask.copy()
    background_mask = ~subject_mask if np.any(subject_mask) else np.ones_like(gray, dtype=bool)
    highlight_mask = background_mask & (gray >= 0.92)

    face_stat_items = face_stats(gray, saturation, rgb, face_boxes, face_confidences)
    face_region = merge_region_boxes(face_boxes)
    subject_region = region_box(subject_mask)
    background_region = region_box(background_mask)
    highlight_region = region_box(highlight_mask)
    face_luma_median = region_median(gray, face_mask)
    face_luma_mean = region_mean(gray, face_mask)
    face_saturation_mean = region_mean(saturation, face_mask)
    face_sharpness_mean = safe_mean(
        [stat.sharpness for stat in face_stat_items if stat.sharpness is not None],
        default=0.0,
    )
    face_sharpness_mean = None if not face_stat_items else face_sharpness_mean
    subject_luma_estimate = region_mean(gray, subject_mask)
    subject_saturation_mean = region_mean(saturation, subject_mask)
    subject_sharpness = masked_laplacian_variance(gray, subject_mask)
    background_luma_estimate = region_mean(gray, background_mask)
    background_saturation_mean = region_mean(saturation, background_mask)
    background_sharpness = masked_laplacian_variance(gray, background_mask)
    face_context_sharpness = max(
        (_masked for _masked in (masked_laplacian_variance(gray, box_ring_mask(gray.shape, box)) for box in face_boxes) if _masked is not None),
        default=None,
    )
    highlight_clipping_ratio = float(np.mean(background_mask & (gray >= 0.985))) if np.any(background_mask) else float(np.mean(gray >= 0.985))
    subject_background_separation = (
        abs(subject_luma_estimate - background_luma_estimate)
        if subject_luma_estimate is not None and background_luma_estimate is not None
        else 0.0
    )

    face_status = "unknown"
    if face_luma_mean is not None:
        if face_luma_mean < 0.31:
            face_status = "underexposed"
        elif face_luma_mean >= 0.84:
            face_status = "overexposed"
        elif face_luma_mean >= 0.76:
            face_status = "bright"
        else:
            face_status = "normal"

    subject_status = "unknown"
    if subject_luma_estimate is not None:
        if subject_luma_estimate < 0.28:
            subject_status = "underexposed"
        elif subject_luma_estimate >= 0.82:
            subject_status = "overexposed"
        elif subject_luma_estimate >= 0.74:
            subject_status = "bright"
        else:
            subject_status = "normal"

    background_status = "unknown"
    if background_luma_estimate is not None:
        if highlight_clipping_ratio >= 0.04 or background_luma_estimate >= 0.82:
            background_status = "high_key"
        elif background_luma_estimate >= 0.72:
            background_status = "bright"
        elif background_luma_estimate <= 0.22:
            background_status = "dark"
        else:
            background_status = "normal"

    portrait_scene_type = "non_portrait"
    portrait_repair_policy = "standard"
    portrait_exposure_status = "not_portrait"
    diagnostic_tags: list[str] = []
    diagnostic_notes: list[str] = []
    exposure_warning_reason = ""

    if portrait_likely:
        portrait_scene_type = "multi_person_portrait" if len(face_boxes) >= 2 else "normal_portrait"
        diagnostic_notes.append(f"检测到 {len(face_boxes)} 张有效真人人脸，按人像场景评估曝光。")
        if (
            face_status == "normal"
            and subject_status == "underexposed"
            and face_luma_mean is not None
            and background_luma_estimate is not None
            and face_luma_mean >= max(0.34, background_luma_estimate + 0.12)
        ):
            subject_status = "normal"

        high_key_background = background_status in {"high_key", "bright"}
        dark_background = background_status == "dark"
        if high_key_background and face_status == "normal":
            if (
                background_luma_estimate is not None
                and subject_luma_estimate is not None
                and face_luma_mean is not None
                and background_luma_estimate >= subject_luma_estimate + 0.08
                and face_luma_mean <= 0.40
            ):
                portrait_scene_type = "backlit_portrait"
                diagnostic_tags.extend(["bright_background_portrait", "protect_high_key_background"])
            else:
                portrait_scene_type = "high_key_portrait"
                diagnostic_tags.extend(["high_key_background", "bright_background_portrait", "protect_high_key_background", "suppress_global_highlight_compression"])
        elif len(face_boxes) >= 2:
            diagnostic_tags.append("multi_person_portrait")

        if face_status == "underexposed" or subject_status == "underexposed":
            portrait_exposure_status = "subject_dark"
            if portrait_scene_type == "backlit_portrait":
                portrait_repair_policy = "gentle_subject_lift_protect_background"
                exposure_warning_reason = "检测到人像逆光或亮背景场景，应优先保护背景并温和增强主体。"
                diagnostic_notes.append("背景明显更亮，主体与背景需要分区域处理。")
            else:
                portrait_repair_policy = "gentle_subject_lift"
                exposure_warning_reason = "检测到人像主体亮度偏低，可做温和主体提亮。"
                diagnostic_notes.append("主体与脸部亮度偏低，允许适度提亮。")
        elif face_status in {"bright", "overexposed"} or subject_status in {"bright", "overexposed"}:
            portrait_exposure_status = "subject_bright"
            if portrait_scene_type == "high_key_portrait":
                portrait_repair_policy = "protect_face_and_high_key_background"
                exposure_warning_reason = "人物主体偏亮，背景也偏亮，不建议整体压暗，应优先保护脸部与高调背景。"
                diagnostic_notes.append("检测到人像高调背景场景。")
                diagnostic_notes.append("背景偏亮但不建议整体压暗，以免白墙或浅色建筑变灰。")
            else:
                portrait_repair_policy = "protect_face_highlights"
                exposure_warning_reason = "人像主体已经偏亮，应优先保护脸部与高光。"
                diagnostic_notes.append("主体已经偏亮，避免继续整体提亮。")
        else:
            portrait_exposure_status = "subject_normal"
            diagnostic_tags.append("portrait_subject_ok")
            if dark_background and background_luma_estimate is not None:
                subject_reference = face_luma_mean if face_luma_mean is not None else subject_luma_estimate
                if subject_reference is not None and subject_reference > background_luma_estimate + 0.10:
                    portrait_scene_type = "dark_background_portrait"
                    portrait_repair_policy = "local_subject_preserve_dark_background"
                    diagnostic_tags.extend(["dark_background", "global_underexposure_suspect_but_subject_ok"])
                    exposure_warning_reason = "主体曝光基本正常，背景偏暗但可作为氛围，不建议强行全局提亮。"
                    diagnostic_notes.append("主体曝光基本正常，背景偏暗但可作为氛围。")
            elif high_key_background:
                if portrait_scene_type == "backlit_portrait":
                    portrait_repair_policy = "gentle_subject_lift_protect_background"
                    exposure_warning_reason = "检测到人像逆光或亮背景场景，应优先保护背景并温和增强主体。"
                    diagnostic_notes.append("背景明显更亮，主体与背景需要分区域处理。")
                else:
                    portrait_scene_type = "high_key_portrait"
                    portrait_repair_policy = "local_subject_enhance_protect_high_key_background"
                    exposure_warning_reason = "人物主体曝光基本正常，背景偏亮但不建议整体压暗。"
                    diagnostic_notes.append("已优先保护高调背景，避免把白墙或浅色建筑压成灰。")
            else:
                portrait_repair_policy = "local_portrait_enhance_only"
                exposure_warning_reason = "检测到人像主体曝光基本正常。"
                diagnostic_notes.append("主体曝光基本正常，可优先做轻微局部增强。")
    else:
        if portrait_type == "artwork_face_context":
            diagnostic_tags.append("artwork_face")
            diagnostic_notes.append("检测到画作/海报中的肖像脸部，未按真人虚焦或真人人像处理。")
            if people_context_box is not None:
                diagnostic_tags.append("back_view_person")
                diagnostic_notes.append("画面中同时存在背身/侧背身人物上下文，但未检测到可用于真人人像策略的正面脸部。")
        elif portrait_type in {"back_view_person_context", "side_back_view_person"}:
            diagnostic_tags.append("back_view_person")
            diagnostic_notes.append("检测到背身或非正面人物上下文，未按真人正面脸部处理。")
        elif portrait_rejection_reason:
            diagnostic_notes.append(portrait_rejection_reason)

    return {
        "face_mask": face_mask,
        "subject_mask": subject_mask,
        "background_mask": background_mask,
        "highlight_mask": highlight_mask,
        "face_region": face_region,
        "subject_boxes": subject_boxes,
        "subject_region": subject_region,
        "background_region": background_region,
        "highlight_region": highlight_region,
        "face_stats": face_stat_items,
        "face_luma_median": face_luma_median,
        "face_luma_mean": face_luma_mean,
        "face_saturation_mean": face_saturation_mean,
        "face_sharpness_mean": face_sharpness_mean,
        "subject_luma_estimate": subject_luma_estimate,
        "subject_saturation_mean": subject_saturation_mean,
        "subject_sharpness": subject_sharpness,
        "background_luma_estimate": background_luma_estimate,
        "background_saturation_mean": background_saturation_mean,
        "background_sharpness": background_sharpness,
        "face_context_sharpness": face_context_sharpness,
        "face_exposure_status": face_status,
        "subject_exposure_status": subject_status,
        "background_exposure_status": background_status,
        "highlight_clipping_ratio": highlight_clipping_ratio,
        "subject_background_separation": subject_background_separation,
        "portrait_scene_type": portrait_scene_type,
        "portrait_repair_policy": portrait_repair_policy,
        "portrait_exposure_status": portrait_exposure_status,
        "portrait_type": portrait_type,
        "diagnostic_tags": diagnostic_tags,
        "diagnostic_notes": diagnostic_notes,
        "exposure_warning_reason": exposure_warning_reason,
        "portrait_rejection_reason": portrait_rejection_reason,
        "raw_face_candidates": raw_face_candidates,
        "face_candidates": face_candidates,
        "validated_face_boxes": face_boxes,
        "face_confidences": face_confidences,
        "face_confidence": float(max(face_confidences, default=0.0)),
        "people_context_box": people_context_box,
    }
