from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from pathlib import Path
import os
import re
import time

import numpy as np
from PIL import Image, ImageOps

from models import AnalysisResult, SimilarImageGroup


_EXIF_DATETIME_TAGS = (36867, 36868, 306)
_MAX_ALL_PAIR_FEATURE_COMPARE = 220
_LOW_CONFIDENCE_LEVEL = "low"
_MEDIUM_LEVEL = "medium"
_HIGH_LEVEL = "high"


@dataclass(frozen=True)
class _ImageFeature:
    path: Path
    width: int
    height: int
    ahash_variants: tuple[int, ...]
    dhash_variants: tuple[int, ...]
    color_hist: tuple[float, ...]
    luma_hist: tuple[float, ...]
    scene_vector: tuple[float, ...]
    center_vector: tuple[float, ...]
    edge_vector: tuple[float, ...]
    mean_luma: float
    std_luma: float
    dark_ratio: float
    bright_ratio: float
    green_ratio: float
    purple_ratio: float
    capture_time: float | None
    mtime: float
    sequence_prefix: str
    sequence_number: int | None

    @property
    def aspect_ratio(self) -> float:
        return self.width / max(1, self.height)


@dataclass(frozen=True)
class _PairMatch:
    left: Path
    right: Path
    score: float
    level: str
    reasons: tuple[str, ...]
    possible_burst: bool


class _UnionFind:
    def __init__(self, paths: list[Path]) -> None:
        self.parent = {path: path for path in paths}

    def find(self, path: Path) -> Path:
        parent = self.parent[path]
        if parent != path:
            self.parent[path] = self.find(parent)
        return self.parent[path]

    def union(self, left: Path, right: Path) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def detect_similar_groups(
    paths: list[Path],
    results: dict[Path, AnalysisResult],
    *,
    max_workers: int | None = None,
    perf_timings: dict[str, float] | None = None,
) -> list[SimilarImageGroup]:
    similar_started_at = time.perf_counter()
    ordered_paths = [path for path in paths if path.exists() and path in results]
    if len(ordered_paths) < 2:
        return []

    started_at = time.perf_counter()
    features = _extract_features_parallel(ordered_paths, max_workers=max_workers)
    _add_timing(perf_timings, "similar_feature_extract", started_at)
    if len(features) < 2:
        _add_timing(perf_timings, "similar_detection", similar_started_at)
        return []

    feature_map = {feature.path: feature for feature in features}
    started_at = time.perf_counter()
    candidate_pairs = _candidate_pairs(features)
    _add_timing(perf_timings, "similar_pair_build", started_at)

    matches: list[_PairMatch] = []
    started_at = time.perf_counter()
    for left, right in candidate_pairs:
        match = _compare_features(feature_map[left], feature_map[right], results)
        if match is not None:
            matches.append(match)
    _add_timing(perf_timings, "similar_pair_compare", started_at)
    if not matches:
        _add_timing(perf_timings, "similar_detection", similar_started_at)
        return []

    started_at = time.perf_counter()
    union_find = _UnionFind([feature.path for feature in features])
    for match in matches:
        union_find.union(match.left, match.right)

    grouped: dict[Path, list[Path]] = {}
    for feature in features:
        grouped.setdefault(union_find.find(feature.path), []).append(feature.path)

    matches_by_group: dict[Path, list[_PairMatch]] = {}
    for match in matches:
        matches_by_group.setdefault(union_find.find(match.left), []).append(match)

    groups: list[SimilarImageGroup] = []
    group_id = 1
    ordered_group_items = sorted(grouped.items(), key=lambda item: (-len(item[1]), min(str(path) for path in item[1])))
    for root, group_paths in ordered_group_items:
        existing_paths = [path for path in ordered_paths if path in group_paths]
        if len(existing_paths) < 2:
            continue
        group_matches = matches_by_group.get(root, [])
        if not group_matches:
            continue

        score = float(np.mean([match.score for match in group_matches]))
        level = _group_level(group_matches, score)
        possible_burst = any(match.possible_burst for match in group_matches)
        evidence = _summarize_evidence(group_matches, existing_paths, feature_map)
        reason = _build_group_reason(level, score, possible_burst, evidence)
        groups.append(
            SimilarImageGroup(
                group_id=group_id,
                paths=existing_paths,
                similarity=score,
                level=level,
                reason=reason,
                evidence=evidence,
                possible_burst=possible_burst,
            )
        )
        group_id += 1

    _add_timing(perf_timings, "similar_group_build", started_at)
    _add_timing(perf_timings, "similar_detection", similar_started_at)
    return groups


def _add_timing(perf_timings: dict[str, float] | None, key: str, started_at: float) -> None:
    if perf_timings is None:
        return
    perf_timings[key] = perf_timings.get(key, 0.0) + (time.perf_counter() - started_at) * 1000.0


def _extract_features_parallel(paths: list[Path], max_workers: int | None = None) -> list[_ImageFeature]:
    workers = max_workers or max(1, min(8, os.cpu_count() or 4, len(paths)))
    features: list[_ImageFeature] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_extract_feature, path): path for path in paths}
        for future in as_completed(futures):
            try:
                feature = future.result()
            except Exception:
                feature = None
            if feature is not None:
                features.append(feature)
    features.sort(key=lambda feature: str(feature.path).casefold())
    return features


def _extract_feature(path: Path) -> _ImageFeature | None:
    with Image.open(path) as raw:
        exif_time = _read_capture_time(raw)
        try:
            raw.draft("RGB", (512, 512))
        except Exception:
            pass
        image = ImageOps.exif_transpose(raw).convert("RGB")

    width, height = image.size
    scene_image = image.resize((48, 48), Image.Resampling.BILINEAR)
    scene_arr = np.asarray(scene_image, dtype=np.float32) / 255.0
    gray = _gray(scene_arr)
    center_image = _center_crop(image, 0.72).resize((48, 48), Image.Resampling.BILINEAR)
    center_arr = np.asarray(center_image, dtype=np.float32) / 255.0
    center_gray = _gray(center_arr)

    hash_sources = _hash_source_images(image)
    ahash_variants = tuple(_average_hash(_image_gray(source)) for source in hash_sources)
    dhash_variants = tuple(_difference_hash(source) for source in hash_sources)
    color_hist = _channel_histogram(scene_arr)
    luma_hist = tuple(float(value) for value in np.histogram(gray, bins=10, range=(0.0, 1.0), density=False)[0] / max(1, gray.size))
    scene_vector = _summary_vector(scene_arr, gray)
    center_vector = _summary_vector(center_arr, center_gray)
    edge_vector = _edge_vector(gray)
    stat = path.stat()
    prefix, sequence_number = _parse_sequence(path)
    return _ImageFeature(
        path=path,
        width=width,
        height=height,
        ahash_variants=ahash_variants,
        dhash_variants=dhash_variants,
        color_hist=color_hist,
        luma_hist=luma_hist,
        scene_vector=scene_vector,
        center_vector=center_vector,
        edge_vector=edge_vector,
        mean_luma=float(np.mean(gray)),
        std_luma=float(np.std(gray)),
        dark_ratio=float(np.mean(gray <= 0.20)),
        bright_ratio=float(np.mean(gray >= 0.82)),
        green_ratio=float(np.mean((scene_arr[:, :, 1] > scene_arr[:, :, 0] * 1.08) & (scene_arr[:, :, 1] > scene_arr[:, :, 2] * 1.06))),
        purple_ratio=float(np.mean((scene_arr[:, :, 0] > scene_arr[:, :, 1] * 1.08) & (scene_arr[:, :, 2] > scene_arr[:, :, 1] * 1.04))),
        capture_time=exif_time,
        mtime=stat.st_mtime,
        sequence_prefix=prefix,
        sequence_number=sequence_number,
    )


def _read_capture_time(image: Image.Image) -> float | None:
    try:
        exif = image.getexif()
    except Exception:
        return None
    for tag in _EXIF_DATETIME_TAGS:
        raw = exif.get(tag)
        if not raw:
            continue
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8", errors="ignore")
            except Exception:
                continue
        try:
            parsed = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
        return parsed.timestamp()
    return None


def _contain_square(image: Image.Image, size: int) -> Image.Image:
    contained = image.copy()
    contained.thumbnail((size, size), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), (238, 238, 238))
    canvas.paste(contained, ((size - contained.width) // 2, (size - contained.height) // 2))
    return canvas


def _center_crop(image: Image.Image, ratio: float) -> Image.Image:
    width, height = image.size
    crop_width = max(1, int(width * ratio))
    crop_height = max(1, int(height * ratio))
    left = max(0, (width - crop_width) // 2)
    top = max(0, (height - crop_height) // 2)
    return image.crop((left, top, left + crop_width, top + crop_height))


def _hash_source_images(image: Image.Image) -> list[Image.Image]:
    sources = [
        _contain_square(image, 64),
        _center_crop(image, 0.82).resize((64, 64), Image.Resampling.BILINEAR),
        _center_crop(image, 0.62).resize((64, 64), Image.Resampling.BILINEAR),
    ]
    rotated_sources: list[Image.Image] = []
    for source in sources:
        rotated_sources.append(source)
        rotated_sources.append(source.rotate(90, expand=True).resize((64, 64), Image.Resampling.BILINEAR))
        rotated_sources.append(source.rotate(270, expand=True).resize((64, 64), Image.Resampling.BILINEAR))
    return rotated_sources


def _image_gray(image: Image.Image) -> np.ndarray:
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return _gray(arr)


def _gray(arr: np.ndarray) -> np.ndarray:
    return arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114


def _average_hash(gray: np.ndarray) -> int:
    resized = np.asarray(Image.fromarray(np.uint8(np.clip(gray * 255.0, 0, 255))).resize((8, 8), Image.Resampling.BILINEAR))
    threshold = float(np.mean(resized))
    value = 0
    for pixel in resized.flatten():
        value = (value << 1) | int(pixel >= threshold)
    return value


def _difference_hash(image: Image.Image) -> int:
    gray = image.resize((9, 8), Image.Resampling.BILINEAR).convert("L")
    arr = np.asarray(gray, dtype=np.float32)
    value = 0
    for bit in (arr[:, 1:] > arr[:, :-1]).flatten():
        value = (value << 1) | int(bool(bit))
    return value


def _channel_histogram(arr: np.ndarray) -> tuple[float, ...]:
    values: list[float] = []
    for channel in range(3):
        hist, _ = np.histogram(arr[:, :, channel], bins=10, range=(0.0, 1.0), density=False)
        hist = hist.astype(np.float32)
        hist /= max(1.0, float(np.sum(hist)))
        values.extend(float(item) for item in hist)
    return tuple(values)


def _summary_vector(arr: np.ndarray, gray: np.ndarray) -> tuple[float, ...]:
    saturation = (np.max(arr, axis=2) - np.min(arr, axis=2)) / np.maximum(np.max(arr, axis=2), 1e-6)
    values = [
        float(np.mean(arr[:, :, 0])),
        float(np.mean(arr[:, :, 1])),
        float(np.mean(arr[:, :, 2])),
        float(np.std(arr[:, :, 0])),
        float(np.std(arr[:, :, 1])),
        float(np.std(arr[:, :, 2])),
        float(np.mean(gray)),
        float(np.std(gray)),
        float(np.mean(saturation)),
        float(np.mean(gray <= 0.20)),
        float(np.mean(gray >= 0.82)),
        float(np.mean((arr[:, :, 1] > arr[:, :, 0] * 1.08) & (arr[:, :, 1] > arr[:, :, 2] * 1.06))),
        float(np.mean((arr[:, :, 0] > arr[:, :, 1] * 1.08) & (arr[:, :, 2] > arr[:, :, 1] * 1.04))),
    ]
    return tuple(values)


def _edge_vector(gray: np.ndarray) -> tuple[float, ...]:
    grad_x = np.abs(np.diff(gray, axis=1, append=gray[:, -1:]))
    grad_y = np.abs(np.diff(gray, axis=0, append=gray[-1:, :]))
    grad = np.clip(grad_x + grad_y, 0.0, 1.0)
    bins = []
    for threshold in (0.04, 0.08, 0.14, 0.22):
        bins.append(float(np.mean(grad >= threshold)))
    row_energy = np.mean(grad, axis=1)
    col_energy = np.mean(grad, axis=0)
    bins.extend(float(value) for value in np.percentile(row_energy, [25, 50, 75]))
    bins.extend(float(value) for value in np.percentile(col_energy, [25, 50, 75]))
    return tuple(bins)


def _parse_sequence(path: Path) -> tuple[str, int | None]:
    match = re.match(r"^(.*?)(\d+)$", path.stem)
    if not match:
        return (path.stem.casefold(), None)
    return (match.group(1).casefold(), int(match.group(2)))


def _candidate_pairs(features: list[_ImageFeature]) -> set[tuple[Path, Path]]:
    if len(features) <= _MAX_ALL_PAIR_FEATURE_COMPARE:
        return {tuple(sorted((left.path, right.path), key=str)) for left, right in combinations(features, 2)}

    buckets: dict[tuple[str, int | str], list[Path]] = {}
    for feature in features:
        for hash_value in feature.ahash_variants[:3] + feature.dhash_variants[:3]:
            for offset in range(0, 64, 16):
                buckets.setdefault((f"h{offset}", f"{(hash_value >> offset) & 0xFFFF:04x}"), []).append(feature.path)
        buckets.setdefault(("green", int(feature.green_ratio * 10)), []).append(feature.path)
        buckets.setdefault(("purple", int(feature.purple_ratio * 10)), []).append(feature.path)
        buckets.setdefault(("dark", int(feature.dark_ratio * 10)), []).append(feature.path)
        if feature.sequence_number is not None:
            buckets.setdefault(("seq", feature.sequence_prefix), []).append(feature.path)
        time_value = feature.capture_time if feature.capture_time is not None else feature.mtime
        buckets.setdefault(("time", int(time_value // 20)), []).append(feature.path)

    pairs: set[tuple[Path, Path]] = set()
    for bucket_paths in buckets.values():
        if len(bucket_paths) < 2:
            continue
        for left, right in combinations(bucket_paths[:90], 2):
            pairs.add(tuple(sorted((left, right), key=str)))
    return pairs


def _compare_features(left: _ImageFeature, right: _ImageFeature, results: dict[Path, AnalysisResult]) -> _PairMatch | None:
    hash_distance = _best_hash_distance(left, right)
    hash_score = 1.0 - min(1.0, hash_distance / 32.0)
    color_distance = _l1(left.color_hist, right.color_hist) / 2.0
    color_score = 1.0 - min(1.0, color_distance / 0.72)
    luma_distance = _l1(left.luma_hist, right.luma_hist) / 2.0
    luma_score = 1.0 - min(1.0, luma_distance / 0.55)
    scene_score = _vector_score(left.scene_vector, right.scene_vector, 0.58)
    center_score = _vector_score(left.center_vector, right.center_vector, 0.70)
    edge_score = _vector_score(left.edge_vector, right.edge_vector, 0.36)
    aspect_score = 1.0 - min(1.0, abs(left.aspect_ratio - right.aspect_ratio) / 1.4)
    sequence_score = _sequence_score(left, right)
    time_score, possible_burst = _time_score(left, right)
    same_scene = _scene_compatible(results.get(left.path), results.get(right.path))

    strict_score = (
        hash_score * 0.34
        + center_score * 0.22
        + color_score * 0.18
        + luma_score * 0.10
        + edge_score * 0.08
        + max(time_score, sequence_score) * 0.08
    )
    contextual_score = (
        color_score * 0.25
        + scene_score * 0.23
        + center_score * 0.18
        + luma_score * 0.10
        + edge_score * 0.10
        + sequence_score * 0.09
        + time_score * 0.03
        + aspect_score * 0.02
    )
    score = max(strict_score, contextual_score)

    palette_close = (color_score >= 0.42 and luma_score >= 0.46) or scene_score >= 0.72
    context_close = scene_score >= 0.68 or center_score >= 0.66
    sequence_close = sequence_score >= 0.72 or time_score >= 0.72
    high_match = same_scene and strict_score >= 0.86 and hash_distance <= 16 and palette_close
    medium_match = (
        same_scene
        and contextual_score >= 0.70
        and palette_close
        and context_close
        and (sequence_close or (strict_score >= 0.80 and hash_distance <= 16))
    )
    low_match = same_scene and contextual_score >= 0.62 and palette_close and sequence_close
    burst_match = possible_burst and palette_close and contextual_score >= 0.64

    if not (high_match or medium_match or low_match or burst_match):
        return None

    reasons: list[str] = []
    if sequence_score >= 0.72:
        reasons.append("文件编号连续")
    if time_score >= 0.72:
        reasons.append("拍摄/文件时间接近")
    if color_score >= 0.58:
        reasons.append("颜色分布相近")
    if luma_score >= 0.46:
        reasons.append("亮度分布相近")
    if center_score >= 0.66:
        reasons.append("主体/中心区域相似")
    if scene_score >= 0.68:
        reasons.append("场景摘要相似")
    if edge_score >= 0.58:
        reasons.append("结构/边缘摘要相近")
    if hash_distance <= 16:
        reasons.append("多尺度感知哈希接近")
    if aspect_score < 0.70:
        reasons.append("横竖或裁切差异明显，归入复核候选")

    if high_match:
        level = _HIGH_LEVEL
    elif medium_match or burst_match:
        level = _MEDIUM_LEVEL
    else:
        level = _LOW_CONFIDENCE_LEVEL
    return _PairMatch(left.path, right.path, float(score), level, tuple(reasons), possible_burst or sequence_score >= 0.90)


def _best_hash_distance(left: _ImageFeature, right: _ImageFeature) -> float:
    distances: list[int] = []
    for left_hash in left.ahash_variants:
        for right_hash in right.ahash_variants:
            distances.append(_hamming(left_hash, right_hash))
    for left_hash in left.dhash_variants:
        for right_hash in right.dhash_variants:
            distances.append(_hamming(left_hash, right_hash))
    return float(min(distances)) if distances else 64.0


def _sequence_score(left: _ImageFeature, right: _ImageFeature) -> float:
    if left.sequence_number is None or right.sequence_number is None:
        return 0.0
    if left.sequence_prefix != right.sequence_prefix:
        return 0.0
    gap = abs(left.sequence_number - right.sequence_number)
    if gap == 0:
        return 0.0
    if gap <= 3:
        return 1.0
    if gap <= 8:
        return 0.72
    if gap <= 20:
        return 0.45
    return 0.0


def _time_score(left: _ImageFeature, right: _ImageFeature) -> tuple[float, bool]:
    reliable = left.capture_time is not None and right.capture_time is not None
    if not reliable:
        return 0.0, False
    left_time = left.capture_time
    right_time = right.capture_time
    if left_time <= 0 or right_time <= 0:
        return 0.0, False
    gap = abs(left_time - right_time)
    if gap <= 5:
        return 1.0, True
    if gap <= 20:
        return 0.86, True
    if gap <= 60:
        return 0.66, False
    return 0.0, False


def _vector_score(left: tuple[float, ...], right: tuple[float, ...], scale: float) -> float:
    if not left or not right:
        return 0.0
    distance = float(np.mean(np.abs(np.asarray(left, dtype=np.float32) - np.asarray(right, dtype=np.float32))))
    return 1.0 - min(1.0, distance / max(1e-6, scale))


def _hamming(left: int, right: int) -> int:
    return int((left ^ right).bit_count())


def _l1(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return float(sum(abs(a - b) for a, b in zip(left, right)))


def _scene_compatible(left: AnalysisResult | None, right: AnalysisResult | None) -> bool:
    if left is None or right is None:
        return True
    if left.scene_type == right.scene_type:
        return True
    generic = {"generic_scene", "unknown", ""}
    return left.scene_type in generic or right.scene_type in generic


def _group_level(matches: list[_PairMatch], score: float) -> str:
    levels = {match.level for match in matches}
    if _HIGH_LEVEL in levels and score >= 0.84:
        return _HIGH_LEVEL
    if _MEDIUM_LEVEL in levels or score >= 0.70:
        return _MEDIUM_LEVEL
    return _LOW_CONFIDENCE_LEVEL


def _summarize_evidence(
    matches: list[_PairMatch],
    paths: list[Path],
    features: dict[Path, _ImageFeature],
) -> list[str]:
    evidence: list[str] = []
    reason_counts: dict[str, int] = {}
    for match in matches:
        for reason in match.reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    priority = {
        "拍摄/文件时间接近": 0,
        "文件编号连续": 1,
        "主体/中心区域相似": 2,
        "场景摘要相似": 3,
        "颜色分布相近": 4,
        "亮度分布相近": 5,
        "结构/边缘摘要相近": 6,
        "多尺度感知哈希接近": 7,
    }
    for reason, _count in sorted(reason_counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[:5]:
        evidence.append(reason)
    return evidence[:5]


def _build_group_reason(level: str, score: float, possible_burst: bool, evidence: list[str]) -> str:
    level_label = {
        _HIGH_LEVEL: "高相似",
        _MEDIUM_LEVEL: "中等相似",
        _LOW_CONFIDENCE_LEVEL: "低置信候选",
    }.get(level, "相似候选")
    burst_label = "，可能为连拍/同组拍摄" if possible_burst else ""
    evidence_text = "、".join(evidence) if evidence else "缩略图摘要接近"
    return f"{level_label}{burst_label}：相似度 {score:.2f}；依据：{evidence_text}"
