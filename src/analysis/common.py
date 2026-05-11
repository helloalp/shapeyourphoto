from __future__ import annotations

import time
from typing import Iterable

import numpy as np

from models import Issue, MetricItem


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".jfif"}
GARBLED_TEXT_FRAGMENTS = ("????", "杩", "璁", "銆", "锛", "鍙", "鏄", "鐗", "浜", "淇", "\ufffd")


def level(score: float) -> str:
    if score >= 0.82:
        return "严重"
    if score >= 0.62:
        return "明显"
    return "轻微"


def metric(label: str, value: float, display: str, color: str, max_value: float = 1.0) -> MetricItem:
    ratio = 0.0 if max_value <= 0 else max(0.0, min(1.0, value / max_value))
    return MetricItem(label=label, value=display, ratio=ratio, color=color)


def looks_garbled_text(text: str) -> bool:
    if not text:
        return False
    if any(fragment in text for fragment in GARBLED_TEXT_FRAGMENTS):
        return True
    question_count = text.count("?")
    return question_count >= 2 and question_count / max(len(text), 1) >= 0.08


def fallback_issue_text(issue: Issue) -> tuple[str, str, str]:
    fallback_map: dict[str, tuple[str, str, str]] = {
        "overexposed": (
            "过曝",
            "亮部区域明显过亮，部分高光可能已经接近或进入裁切。",
            "建议适度压低曝光或高光，尽量保留亮部层次。",
        ),
        "underexposed": (
            "欠曝",
            "暗部信息偏少，主体细节可能被压暗。",
            "建议保守提亮主体并恢复暗部层次，避免把背景整体抬灰。",
        ),
        "out_of_focus": (
            "失焦/模糊",
            "局部清晰度不足，画面可能存在失焦或抖动问题。",
            "建议优先保留原图；自动修复只能做轻微锐化，无法真正恢复失焦细节。",
        ),
        "portrait_out_of_focus": (
            "人像主体虚焦",
            "人物脸部或主体关键区域明显未对焦，保留价值较低。",
            "不适合保留 / 建议删除；自动锐化无法恢复脸部失焦细节。",
        ),
        "low_contrast": (
            "低对比度",
            "整体层次偏平，画面对比度不足。",
            "建议轻微提升中间调对比和局部层次，避免把高光压脏或把阴影抬灰。",
        ),
        "color_cast": (
            "偏色",
            "整体存在可见偏色，中性区域可能不够自然。",
            "建议微调白平衡或色温，优先观察白色、灰色和肤色是否恢复自然。",
        ),
        "high_noise": (
            "噪点偏高",
            "暗部、纯色背景或高 ISO 区域出现明显颗粒噪点。",
            "建议优先使用保守的自适应降噪，并检查主体纹理与边缘是否仍然自然。",
        ),
        "muted_colors": (
            "色彩寡淡",
            "画面整体饱和度偏低，颜色层次较弱。",
            "建议使用保守的 vibrance 式增强，优先提升低饱和区域色彩并保护肤色自然。",
        ),
        "over_saturated": (
            "过饱和",
            "颜色整体偏浓，亮部高饱和区域可能显得发脏。",
            "建议适度回收饱和度并保护高光，避免鲜艳区域细节堵塞。",
        ),
    }
    return fallback_map.get(
        issue.code,
        (
            issue.code.replace("_", " ").strip() or "诊断结果",
            "检测到一项需要关注的问题，原始说明已回退为通用描述。",
            "建议结合原图观察主体区域，再决定是否修复或清理。",
        ),
    )


def sanitize_issues(issues: list[Issue]) -> list[Issue]:
    sanitized: list[Issue] = []
    for item in issues:
        fallback_label, fallback_detail, fallback_suggestion = fallback_issue_text(item)
        sanitized.append(
            Issue(
                code=item.code,
                label=fallback_label if looks_garbled_text(item.label) else item.label,
                score=item.score,
                level=item.level,
                detail=fallback_detail if looks_garbled_text(item.detail) else item.detail,
                suggestion=fallback_suggestion if looks_garbled_text(item.suggestion) else item.suggestion,
                meta=dict(item.meta),
            )
        )
    return sanitized


def add_timing(perf_timings: dict[str, float], key: str, started_at: float) -> None:
    perf_timings[key] = perf_timings.get(key, 0.0) + (time.perf_counter() - started_at) * 1000.0


def issue(
    code: str,
    label: str,
    score: float,
    detail: str,
    suggestion: str,
    meta: dict[str, str] | None = None,
) -> Issue:
    return Issue(
        code=code,
        label=label,
        score=score,
        level=level(score),
        detail=detail,
        suggestion=suggestion,
        meta=meta or {},
    )


def laplacian_variance(gray: np.ndarray) -> float:
    center = gray[1:-1, 1:-1] * -4.0
    neighbors = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
    laplacian = center + neighbors
    return float(np.var(laplacian))


def local_range(gray: np.ndarray) -> float:
    step = max(1, min(gray.shape[0], gray.shape[1]) // 32)
    sampled = gray[::step, ::step]
    return float(np.percentile(sampled, 90) - np.percentile(sampled, 10))


def box_iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax0, ay0, ax1, ay1 = box_a
    bx0, by0, bx1, by1 = box_b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    iw = max(0, ix1 - ix0)
    ih = max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(1, (ax1 - ax0) * (ay1 - ay0))
    area_b = max(1, (bx1 - bx0) * (by1 - by0))
    return inter / float(area_a + area_b - inter)


def tile_sharpness(gray: np.ndarray, grid: int = 6) -> tuple[float, float, float]:
    height, width = gray.shape
    values: list[float] = []
    for yi in range(grid):
        for xi in range(grid):
            y0 = yi * height // grid
            y1 = (yi + 1) * height // grid
            x0 = xi * width // grid
            x1 = (xi + 1) * width // grid
            tile = gray[y0:y1, x0:x1]
            if tile.shape[0] < 3 or tile.shape[1] < 3:
                continue
            values.append(laplacian_variance(tile))
    if not values:
        return 0.0, 0.0, 0.0
    sharpness = np.asarray(values, dtype=np.float32)
    return float(np.percentile(sharpness, 50)), float(np.percentile(sharpness, 90)), float(np.max(sharpness))


def saturation_map(rgb: np.ndarray) -> np.ndarray:
    maxc = np.max(rgb, axis=2)
    minc = np.min(rgb, axis=2)
    return np.divide(maxc - minc, np.maximum(maxc, 1e-6), out=np.zeros_like(maxc), where=maxc > 1e-6)


def hue_map(rgb: np.ndarray) -> np.ndarray:
    normalized = rgb / 255.0
    r = normalized[:, :, 0]
    g = normalized[:, :, 1]
    b = normalized[:, :, 2]
    maxc = np.max(normalized, axis=2)
    minc = np.min(normalized, axis=2)
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


def skin_ratio(rgb: np.ndarray) -> float:
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]
    y = (r * 0.299 + g * 0.587 + b * 0.114) / 255.0
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    mask = (
        (r >= 92.0)
        & (g >= 38.0)
        & (b >= 18.0)
        & (r > g)
        & (r > b)
        & (np.abs(r - g) >= 10.0)
        & ((np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)) >= 10.0)
        & (cb >= 76.0)
        & (cb <= 128.0)
        & (cr >= 132.0)
        & (cr <= 178.0)
        & (y >= 0.18)
        & (y <= 0.92)
    )
    return float(np.mean(mask))


def hue_entropy(hue: np.ndarray, saturation: np.ndarray) -> float:
    mask = saturation > 0.18
    if not np.any(mask):
        return 0.0
    hist, _ = np.histogram(hue[mask], bins=18, range=(0.0, 1.0))
    hist = hist.astype(np.float32)
    hist /= max(1.0, float(np.sum(hist)))
    hist = hist[hist > 0]
    return float(-np.sum(hist * np.log2(hist)))


def masked_mean(values: np.ndarray, mask: np.ndarray, fallback: float) -> float:
    if not np.any(mask):
        return fallback
    return float(np.mean(values[mask]))


def masked_percentile(values: np.ndarray, mask: np.ndarray, q: float, fallback: float) -> float:
    if not np.any(mask):
        return fallback
    return float(np.percentile(values[mask], q))


def region_mean(values: np.ndarray, mask: np.ndarray) -> float | None:
    if not np.any(mask):
        return None
    return float(np.mean(values[mask]))


def region_median(values: np.ndarray, mask: np.ndarray) -> float | None:
    if not np.any(mask):
        return None
    return float(np.median(values[mask]))


def region_box(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if ys.size == 0 or xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def merge_region_boxes(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    if not boxes:
        return None
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[2] for box in boxes)
    y1 = max(box[3] for box in boxes)
    return x0, y0, x1, y1


def skin_mask_ycbcr(rgb: np.ndarray, gray: np.ndarray) -> np.ndarray:
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return (
        (r >= 92.0)
        & (g >= 38.0)
        & (b >= 18.0)
        & (r > g)
        & (r > b)
        & ((np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)) >= 10.0)
        & (cb >= 76.0)
        & (cb <= 128.0)
        & (cr >= 132.0)
        & (cr <= 178.0)
        & (gray >= 0.16)
        & (gray <= 0.92)
    )


def cleanup_binary_mask(mask: np.ndarray) -> np.ndarray:
    cleaned = mask.copy()
    for _ in range(2):
        neighbors = (
            np.pad(cleaned[1:, :], ((0, 1), (0, 0)))
            + np.pad(cleaned[:-1, :], ((1, 0), (0, 0)))
            + np.pad(cleaned[:, 1:], ((0, 0), (0, 1)))
            + np.pad(cleaned[:, :-1], ((0, 0), (1, 0)))
        )
        cleaned = neighbors >= 2
    return cleaned


def component_boxes(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    boxes: list[tuple[int, int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            stack = [(x, y)]
            visited[y, x] = True
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while stack:
                cx, cy = stack.pop()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((nx, ny))
            boxes.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return boxes


def boxes_close(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> bool:
    ax0, ay0, ax1, ay1 = box_a
    bx0, by0, bx1, by1 = box_b
    return not (ax1 < bx0 - 6 or bx1 < ax0 - 6 or ay1 < by0 - 8 or by1 < ay0 - 8)


def merge_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: (item[1], item[0])):
        current = box
        changed = True
        while changed:
            changed = False
            next_merged: list[tuple[int, int, int, int]] = []
            for kept in merged:
                if box_iou(current, kept) >= 0.12 or boxes_close(current, kept):
                    current = (
                        min(current[0], kept[0]),
                        min(current[1], kept[1]),
                        max(current[2], kept[2]),
                        max(current[3], kept[3]),
                    )
                    changed = True
                else:
                    next_merged.append(kept)
            merged = next_merged
        merged.append(current)
    return merged


def expanded_box(
    box: tuple[int, int, int, int],
    shape: tuple[int, int],
    pad_x_ratio: float = 0.15,
    pad_y_ratio: float = 0.18,
) -> tuple[int, int, int, int]:
    height, width = shape
    x0, y0, x1, y1 = box
    bw = max(1, x1 - x0)
    bh = max(1, y1 - y0)
    pad_x = int(round(bw * pad_x_ratio))
    pad_y = int(round(bh * pad_y_ratio))
    return max(0, x0 - pad_x), max(0, y0 - pad_y), min(width, x1 + pad_x), min(height, y1 + pad_y)


def mask_from_box(shape: tuple[int, int], box: tuple[int, int, int, int]) -> np.ndarray:
    height, width = shape
    x0, y0, x1, y1 = box
    mask = np.zeros((height, width), dtype=bool)
    mask[max(0, y0) : min(height, y1), max(0, x0) : min(width, x1)] = True
    return mask


def box_ring_mask(shape: tuple[int, int], box: tuple[int, int, int, int]) -> np.ndarray:
    outer = mask_from_box(shape, expanded_box(box, shape, 0.26, 0.30))
    inner = mask_from_box(shape, expanded_box(box, shape, 0.06, 0.08))
    return outer & ~inner


def masked_laplacian_variance(values: np.ndarray, mask: np.ndarray) -> float | None:
    if not np.any(mask) or values.shape[0] < 3 or values.shape[1] < 3:
        return None
    center = values[1:-1, 1:-1] * -4.0
    neighbors = values[:-2, 1:-1] + values[2:, 1:-1] + values[1:-1, :-2] + values[1:-1, 2:]
    lap = center + neighbors
    mask_inner = mask[1:-1, 1:-1]
    if not np.any(mask_inner):
        return None
    return float(np.var(lap[mask_inner]))


def crop_mask(shape: tuple[int, int], box: tuple[int, int, int, int], inset_ratio: float) -> np.ndarray:
    height, width = shape
    x0, y0, x1, y1 = box
    bw = max(1, x1 - x0)
    bh = max(1, y1 - y0)
    inset_x = int(round(bw * inset_ratio))
    inset_y = int(round(bh * inset_ratio))
    inner = (
        max(0, x0 + inset_x),
        max(0, y0 + inset_y),
        min(width, x1 - inset_x),
        min(height, y1 - inset_y),
    )
    return mask_from_box(shape, inner)


def region_std(values: np.ndarray, mask: np.ndarray) -> float:
    if not np.any(mask):
        return 0.0
    return float(np.std(values[mask]))


def gradient_maps(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    grad_x = np.abs(np.diff(gray, axis=1, append=gray[:, -1:]))
    grad_y = np.abs(np.diff(gray, axis=0, append=gray[-1:, :]))
    return grad_x, grad_y, grad_x + grad_y


def edge_density(gray: np.ndarray, threshold: float = 0.08) -> float:
    _, _, grad = gradient_maps(gray)
    return float(np.mean(grad >= threshold))


def safe_mean(values: Iterable[float], default: float = 0.0) -> float:
    items = list(values)
    if not items:
        return default
    return float(np.mean(np.asarray(items, dtype=np.float32)))


def describe_color_cast(
    r_mean: float, g_mean: float, b_mean: float, rgb_balance: float
) -> tuple[str, str, str, dict[str, str]]:
    mean_value = (r_mean + g_mean + b_mean) / 3.0
    offsets = {
        "red": r_mean - mean_value,
        "green": g_mean - mean_value,
        "blue": b_mean - mean_value,
    }
    positive = {name for name, value in offsets.items() if value > 0.015}
    negative = min(offsets.items(), key=lambda item: item[1])[0]
    if positive == {"red", "green"}:
        return (
            "偏暖/偏黄",
            "中性区域明显偏暖，白色或灰色可能带黄。",
            "建议略微降低色温，观察白色衣物或墙面是否发黄。",
            {"method_hint": "cool_down", "negative_channel": negative},
        )
    if positive == {"green", "blue"}:
        return (
            "偏冷/偏青",
            "整体存在偏冷或偏青倾向。",
            "建议略微提高色温或微调品红，观察肤色是否偏冷。",
            {"method_hint": "warm_up", "negative_channel": negative},
        )
    if positive == {"red", "blue"}:
        return (
            "偏洋红",
            "整体存在洋红偏色。",
            "建议向绿色方向微调白平衡，避免肤色偏粉紫。",
            {"method_hint": "add_green", "negative_channel": negative},
        )
    if "red" in positive:
        return (
            "偏红",
            "红通道明显偏强。",
            "建议适度降低红色或色温，检查高光区域是否偏暖。",
            {"method_hint": "cool_down", "negative_channel": negative},
        )
    if "green" in positive:
        return (
            "偏绿",
            "绿色分量偏强，中性区域可能发脏。",
            "建议补少量品红，观察白墙和灰墙是否恢复中性。",
            {"method_hint": "add_magenta", "negative_channel": negative},
        )
    return (
        "偏蓝",
        f"蓝通道偏强，RGB 最大通道偏差约 {rgb_balance:.3f}。",
        "建议略微提高色温，观察白色、肤色和灰色是否更自然。",
        {"method_hint": "warm_up", "negative_channel": negative},
    )
