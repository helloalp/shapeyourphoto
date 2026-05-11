from __future__ import annotations

from models import AnalysisResult, RepairMethod, RepairPlan, RepairSelection


REPAIR_METHODS = [
    RepairMethod("auto_tone", "自动层次校正", "拉开黑白场，快速改善整体灰感。"),
    RepairMethod("recover_highlights", "压高光", "压住过亮区域，尽量保留亮部细节。"),
    RepairMethod("lift_shadows", "提暗部", "提升阴影和中间调，减少欠曝带来的细节损失。"),
    RepairMethod("boost_contrast", "增强对比度", "提升全局反差，让层次更清楚。"),
    RepairMethod("boost_vibrance", "增强自然饱和度", "适合色彩寡淡但不希望整体过饱和的画面。"),
    RepairMethod("reduce_saturation", "降低饱和度", "压住过强颜色，减少刺眼和失真。"),
    RepairMethod("boost_clarity", "增强清晰度", "用轻量锐化提升主体边缘和微对比。"),
    RepairMethod("reduce_noise", "自适应降噪", "按场景与区域抑制噪点，优先保护人像纹理、建筑边缘和纯净背景。"),
    RepairMethod("cool_down", "降低色温 / 去偏暖", "适合整体偏黄、偏红、偏暖的画面。"),
    RepairMethod("warm_up", "升高色温 / 去偏冷", "适合整体偏蓝、偏青、偏冷的画面。"),
    RepairMethod("add_magenta", "补品红 / 去偏绿", "适合整体发绿的画面。"),
    RepairMethod("add_green", "补绿色 / 去偏洋红", "适合整体发紫或偏洋红的画面。"),
    RepairMethod("portrait_local_face_enhance", "人像局部面部增强", "对脸部做轻微局部清晰感与微对比增强，尽量不改变肤色和亮度。"),
    RepairMethod("portrait_subject_midcontrast", "人像主体中间调增强", "对人物主体做轻微局部中间调对比增强，保持整体自然。"),
    RepairMethod("portrait_dark_clothing_detail", "深色服装细节增强", "轻微提升深色衣物纹理感，避免把黑色抬成灰色。"),
    RepairMethod("protect_high_key_background", "保护高调背景", "保护白墙、浅色建筑等高调背景，避免自动修复把背景压成灰白。"),
]

REPAIR_METHOD_MAP = {method.method_id: method for method in REPAIR_METHODS}


def get_repair_methods() -> list[RepairMethod]:
    return list(REPAIR_METHODS)


def suggest_methods_for_result(result: AnalysisResult | None) -> list[str]:
    if result is None:
        return []

    ordered: list[str] = []
    seen: set[str] = set()
    portrait_enabled = result.portrait_likely and result.validated_face_count > 0
    cleanup_reason_codes = {candidate.reason_code for candidate in result.cleanup_candidates}
    severe_portrait_focus_failure = (
        any(issue.code == "portrait_out_of_focus" and issue.score >= 0.58 for issue in result.issues)
        or "portrait_out_of_focus" in cleanup_reason_codes
    )
    portrait_subject_ok = result.portrait_exposure_status == "subject_normal" or "portrait_subject_ok" in result.diagnostic_tags
    dark_background_portrait = portrait_subject_ok and "dark_background" in result.diagnostic_tags
    high_key_portrait = result.portrait_scene_type == "high_key_portrait"
    backlit_portrait = result.portrait_scene_type == "backlit_portrait"
    multi_person_portrait = result.portrait_scene_type == "multi_person_portrait"
    denoise_needed = bool(result.denoise_recommended or result.noise_level in {"elevated", "high"})

    def add(method_id: str) -> None:
        if method_id not in seen and method_id in REPAIR_METHOD_MAP:
            seen.add(method_id)
            ordered.append(method_id)

    if severe_portrait_focus_failure:
        return []

    if denoise_needed and result.denoise_profile in {"night_high_iso", "indoor_shadow", "smooth_sky", "portrait_protect"}:
        add("reduce_noise")

    if portrait_enabled:
        if high_key_portrait:
            add("protect_high_key_background")
            add("portrait_subject_midcontrast")
            add("portrait_local_face_enhance")
        elif dark_background_portrait:
            add("portrait_subject_midcontrast")
            add("portrait_local_face_enhance")
            add("portrait_dark_clothing_detail")
        elif backlit_portrait:
            add("protect_high_key_background")
            add("portrait_subject_midcontrast")
            add("portrait_local_face_enhance")
        elif multi_person_portrait:
            add("portrait_subject_midcontrast")
            add("portrait_local_face_enhance")
        elif portrait_subject_ok or result.portrait_exposure_status == "subject_bright":
            add("portrait_local_face_enhance")
            if result.portrait_exposure_status == "subject_bright":
                add("protect_high_key_background")

    for issue in result.issues:
        if issue.code == "overexposed":
            if result.portrait_scene_type not in {"high_key_portrait", "backlit_portrait"}:
                add("recover_highlights")
            elif high_key_portrait or backlit_portrait:
                add("protect_high_key_background")
                add("portrait_local_face_enhance")
                if high_key_portrait:
                    add("portrait_subject_midcontrast")
        elif issue.code == "underexposed":
            if portrait_subject_ok:
                add("portrait_subject_midcontrast")
                if denoise_needed:
                    add("reduce_noise")
                if dark_background_portrait:
                    add("portrait_dark_clothing_detail")
                if any(color_issue.code == "color_cast" for color_issue in result.issues):
                    add(next((color_issue.meta.get("method_hint", "cool_down") for color_issue in result.issues if color_issue.code == "color_cast"), "cool_down"))
            else:
                add("lift_shadows")
                if issue.score >= 0.55 or denoise_needed:
                    add("reduce_noise")
                if issue.score >= 0.72:
                    add("boost_contrast")
        elif issue.code == "low_contrast":
            if not dark_background_portrait and not high_key_portrait:
                add("auto_tone")
            if portrait_enabled:
                add("portrait_subject_midcontrast")
            else:
                add("boost_contrast")
        elif issue.code == "flat_tone":
            if portrait_enabled:
                add("portrait_subject_midcontrast")
            else:
                add("boost_contrast")
        elif issue.code == "muted_colors":
            add("boost_vibrance")
            if issue.score >= 0.55:
                if portrait_enabled:
                    add("portrait_subject_midcontrast")
                else:
                    add("boost_contrast")
        elif issue.code == "over_saturated":
            add("reduce_saturation")
        elif issue.code == "out_of_focus":
            if portrait_enabled:
                add("portrait_local_face_enhance")
            else:
                add("boost_clarity")
        elif issue.code == "high_noise":
            add("reduce_noise")
        elif issue.code == "color_cast":
            add(issue.meta.get("method_hint", "cool_down"))

    if denoise_needed and "reduce_noise" not in seen and result.noise_level == "high":
        add("reduce_noise")

    return ordered


def suggest_methods_for_results(results: list[AnalysisResult]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for result in results:
        for method_id in suggest_methods_for_result(result):
            if method_id not in seen:
                seen.add(method_id)
                ordered.append(method_id)
    return ordered


def get_method_labels(method_ids: list[str]) -> list[str]:
    return [REPAIR_METHOD_MAP[method_id].label for method_id in method_ids if method_id in REPAIR_METHOD_MAP]


def build_repair_plan(result: AnalysisResult | None, selection: RepairSelection) -> RepairPlan:
    method_ids = suggest_methods_for_result(result) if selection.mode in {"adaptive", "auto"} else list(selection.selected_method_ids)
    if result is None:
        return RepairPlan(mode=selection.mode, method_ids=method_ids)

    issue_scores = {item.code: item.score for item in result.issues}
    under = issue_scores.get("underexposed", 0.0)
    over = issue_scores.get("overexposed", 0.0)
    low_contrast = issue_scores.get("low_contrast", 0.0)
    muted = issue_scores.get("muted_colors", 0.0)
    over_sat = issue_scores.get("over_saturated", 0.0)
    blur = max(issue_scores.get("out_of_focus", 0.0), issue_scores.get("portrait_out_of_focus", 0.0))
    high_noise = issue_scores.get("high_noise", 0.0)
    color_cast = issue_scores.get("color_cast", 0.0)
    noise_score = max(high_noise, float(getattr(result, "noise_score", 0.0)) / 0.02)

    window_guard = result.exposure_type in {"high_contrast_window_scene", "silhouette_scene", "low_key_scene"}
    unrecoverable_highlights = result.highlight_recovery_type == "unrecoverable_highlights"
    natural_vivid = result.color_type == "natural_vivid"
    restrained_natural = result.color_type == "restrained_natural"
    portrait_enabled = result.portrait_likely and result.validated_face_count > 0
    denoise_profile = result.denoise_profile or "none"

    op_strengths: dict[str, float] = {}
    notes = [
        f"scene_type={result.scene_type}",
        f"portrait_type={result.portrait_type}",
        f"exposure_type={result.exposure_type}",
        f"color_type={result.color_type}",
        f"denoise_profile={denoise_profile}",
    ]

    def set_strength(method_id: str, value: float) -> None:
        op_strengths[method_id] = max(0.06, min(1.0, value))

    for method_id in method_ids:
        if method_id == "auto_tone":
            value = 0.44 + low_contrast * 0.26
            if window_guard:
                value = min(value, 0.18)
        elif method_id == "recover_highlights":
            value = 0.46 + over * 0.34
            if unrecoverable_highlights:
                value = min(value, 0.14)
                notes.append("不可恢复高光：recover_highlights 已限幅，避免天空或白墙压灰。")
            elif result.exposure_type == "high_contrast_window_scene":
                value = min(value, 0.16)
        elif method_id == "lift_shadows":
            value = 0.44 + under * 0.34
            if window_guard:
                value = min(value, 0.12)
                notes.append("高反差/低调场景：lift_shadows 已强限幅，避免破坏氛围。")
        elif method_id == "boost_contrast":
            value = 0.30 + max(low_contrast, muted) * 0.28
            if window_guard:
                value = min(value, 0.18)
        elif method_id == "boost_vibrance":
            value = 0.18 + muted * 0.24
            if restrained_natural:
                value = min(value, 0.14)
                notes.append("色彩克制但自然：boost_vibrance 已降为保守档。")
        elif method_id == "reduce_saturation":
            value = 0.18 + over_sat * 0.24
            if natural_vivid:
                value = min(value, 0.14)
                notes.append("自然高饱和场景：reduce_saturation 已限幅，避免把画面洗灰。")
        elif method_id == "boost_clarity":
            value = 0.20 + blur * 0.22
        elif method_id == "reduce_noise":
            value = 0.12 + max(noise_score, under * 0.42) * 0.22
            if denoise_profile == "portrait_protect":
                value = min(max(value, 0.18), 0.30)
                notes.append("人像降噪：优先保护脸部与皮肤纹理，限制过度磨皮。")
            elif denoise_profile == "architecture_texture":
                value = min(value, 0.22)
                notes.append("建筑/纹理降噪：对强边缘与文字区域保持保守。")
            elif denoise_profile == "smooth_sky":
                value = min(0.42, value + 0.06)
                notes.append("纯净背景降噪：允许对低纹理天空和墙面做更明显抑噪。")
            elif denoise_profile in {"night_high_iso", "indoor_shadow"}:
                value = min(0.52, value + 0.08)
                notes.append("暗部/夜景降噪：优先处理阴影噪点与提亮后颗粒。")
            elif not result.denoise_recommended and high_noise < 0.35:
                value = min(value, 0.18)
                notes.append("当前噪点不重：reduce_noise 自动降为轻度。")
        elif method_id in {"cool_down", "warm_up", "add_magenta", "add_green"}:
            value = 0.22 + color_cast * 0.20
        elif method_id == "portrait_local_face_enhance":
            value = 0.16 if result.portrait_scene_type != "multi_person_portrait" else 0.12
        elif method_id == "portrait_subject_midcontrast":
            value = 0.18 if result.portrait_exposure_status == "subject_normal" else 0.22
        elif method_id == "portrait_dark_clothing_detail":
            value = 0.16
        elif method_id == "protect_high_key_background":
            value = 0.26 if unrecoverable_highlights or result.portrait_scene_type in {"high_key_portrait", "backlit_portrait"} else 0.18
        else:
            value = 0.22
        if selection.mode == "manual" and method_id in {"lift_shadows", "recover_highlights"} and window_guard:
            notes.append(f"手动选择 {method_id} 仍会遵循场景保护限幅。")
        set_strength(method_id, value)

    policy = result.portrait_repair_policy or "standard"
    if not portrait_enabled:
        if window_guard:
            policy = "scene_guarded_no_global_lift"
        elif unrecoverable_highlights:
            policy = "highlight_rolloff_guard"
        elif natural_vivid:
            policy = "natural_vivid_protection"
    return RepairPlan(
        mode=selection.mode,
        method_ids=method_ids,
        op_strengths=op_strengths,
        policy=policy,
        notes=notes,
    )
