from __future__ import annotations

from pathlib import Path

from models import CleanupCandidate, Issue


def cleanup_severity(score: float) -> str:
    if score >= 0.82:
        return "critical"
    if score >= 0.64:
        return "high"
    if score >= 0.46:
        return "medium"
    return "low"


def build_cleanup_candidates(image_path: Path, issues: list[Issue]) -> list[CleanupCandidate]:
    cleanup_candidates: list[CleanupCandidate] = []
    for item in issues:
        reason_code = item.meta.get("cleanup_reason_code", "")
        reason_text = item.meta.get("cleanup_reason_text", "")
        severity = item.meta.get("cleanup_severity", "")
        confidence_text = item.meta.get("cleanup_confidence", "")
        enabled = item.meta.get("cleanup_candidate", "false").lower() == "true"
        if not enabled:
            if item.code == "out_of_focus" and item.score >= 0.86:
                enabled = True
                reason_code = "global_out_of_focus"
                reason_text = "整张图片严重模糊，主体辨识度很低。"
            elif item.code == "overexposed" and item.score >= 0.92:
                enabled = True
                reason_code = "severe_overexposed"
                reason_text = "大面积高光已不可恢复，主体信息明显丢失。"
            elif item.code == "underexposed" and item.score >= 0.94:
                enabled = True
                reason_code = "severe_underexposed"
                reason_text = "整体暗部信息极少，主体已接近不可辨认。"
        if not enabled:
            continue
        try:
            confidence = float(confidence_text or item.score)
        except ValueError:
            confidence = item.score
        cleanup_candidates.append(
            CleanupCandidate(
                image_path=image_path,
                thumbnail_path=None,
                reason_code=reason_code or item.code,
                reason_text=reason_text or item.suggestion,
                severity=severity or cleanup_severity(item.score),
                confidence=confidence,
                source_issue=item.code,
            )
        )
    return cleanup_candidates
