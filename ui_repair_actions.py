from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import messagebox

from analyzer import analyze_image
from app_settings import (
    REPAIR_SUMMARY_FILTER_ALL,
    REPAIR_SUMMARY_FILTER_DISCARD_RELATED,
    REPAIR_SUMMARY_FILTER_FAILED,
    REPAIR_SUMMARY_FILTER_FORCED_SAVED,
    REPAIR_SUMMARY_FILTER_FORCED_UNSAVED,
    REPAIR_SUMMARY_FILTER_REPAIRED,
    REPAIR_SUMMARY_FILTER_ROLLBACK_NOOP,
    REPAIR_SUMMARY_FILTER_SKIPPED,
)
from debug_open_dialog import DebugOpenEntry, show_debug_open_dialog
from models import RepairRecord, RepairSelection
from repair_completion_dialog import RepairCompletionEntry, show_repair_completion_dialog
from repair_dialog import show_repair_dialog
from repair_engine import repair_image_file
from repair_planner import get_method_labels, get_repair_methods, suggest_methods_for_results
from stats_store import record_repair, save_stats


class UiRepairActionsMixin:
    def repair_current(self) -> None:
        path = self._current_path()
        if path is None:
            messagebox.showinfo("提示", "请先在列表中选中一张图片。")
            return
        self._open_repair_dialog([path], "修复当前图片")

    def repair_checked(self) -> None:
        targets, source_label = self._batch_repair_targets()
        if not targets:
            messagebox.showinfo("提示", "请先多选或勾选至少一张图片。")
            return
        self._log_console(f"batch repair target source: {source_label} | count={len(targets)}")
        self._open_repair_dialog(targets, f"批量修复 {len(targets)} 张图片")

    def _batch_repair_targets(self) -> tuple[list[Path], str]:
        multi_selected = [path for path in self._selected_tree_paths() if path.exists()]
        if len(multi_selected) > 1:
            return self._dedupe_repair_targets(multi_selected), "multi_select"
        checked = [path for path in self.image_paths if self.selected_flags.get(path) and self.selected_flags[path].get() and path.exists()]
        if checked:
            return self._dedupe_repair_targets(checked), "checked"
        return [], "empty"

    def _dedupe_repair_targets(self, paths: list[Path]) -> list[Path]:
        seen: set[Path] = set()
        targets: list[Path] = []
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            targets.append(path)
        return targets

    def _open_repair_dialog(self, targets: list[Path], title: str) -> None:
        existing_results = [self.results[path] for path in targets if path in self.results]
        recommended = suggest_methods_for_results(existing_results)
        selection = show_repair_dialog(
            self.root,
            title,
            get_repair_methods(),
            recommended,
            allow_adaptive=True,
            target_count=len(targets),
            analyzed_count=len(existing_results),
            recommendation_note=self._repair_recommendation_note(targets, existing_results),
        )
        if selection is not None:
            self._run_repair(targets, selection)

    def _repair_recommendation_note(self, targets: list[Path], existing_results: list) -> str:
        if len(targets) <= 1:
            return ""
        issue_counts: dict[str, int] = {}
        policy_counts: dict[str, int] = {}
        for result in existing_results:
            if result.issues:
                for issue in result.issues:
                    issue_counts[issue.label] = issue_counts.get(issue.label, 0) + 1
            else:
                issue_counts["无明显问题"] = issue_counts.get("无明显问题", 0) + 1
            if result.portrait_repair_policy:
                policy_counts[result.portrait_repair_policy] = policy_counts.get(result.portrait_repair_policy, 0) + 1
            elif result.exposure_type:
                policy_counts[result.exposure_type] = policy_counts.get(result.exposure_type, 0) + 1

        if not existing_results:
            return f"已选择 {len(targets)} 张，其中尚无已分析结果；修复前会先补分析，并逐张生成独立修复计划。"

        issue_text = "、".join(list(issue_counts)[:4])
        if len(issue_counts) > 4:
            issue_text += "等"
        policy_text = "、".join(list(policy_counts)[:3])
        if issue_text and policy_text:
            return f"已选择 {len(targets)} 张：包含 {issue_text}，策略/场景含 {policy_text}；将逐张生成独立修复计划。"
        if issue_text:
            return f"已选择 {len(targets)} 张：包含 {issue_text} 等不同类型，将按各自分析结果使用不同修复方案和力度。"
        return f"已选择 {len(targets)} 张：多张图片将按各自分析结果使用不同修复方案和力度。"

    def _resolve_base_folder(self) -> str:
        raw = self.folder_var.get().strip()
        if not raw:
            return "."
        candidate = Path(raw)
        if candidate.is_file():
            return str(candidate.parent)
        return str(candidate)

    def _run_repair(self, targets: list[Path], selection: RepairSelection) -> None:
        if self.is_busy:
            messagebox.showinfo("提示", "当前已有任务正在运行。")
            return

        missing = [path for path in targets if path not in self.results and path not in self.errors]
        total_steps = len(missing) + len(targets)
        analysis_worker_plan = self._analysis_worker_plan(len(missing)) if missing else None
        analysis_workers = analysis_worker_plan.actual_workers if analysis_worker_plan is not None else 0
        repair_workers = self._repair_workers(len(targets))
        base_folder = self._resolve_base_folder()
        self._log_console(
            f"repair started: count={len(targets)} pre_analyze={len(missing)} mode={selection.mode} overwrite={selection.overwrite_original} "
            f"analysis_workers={self._analysis_concurrency_label(analysis_worker_plan) if analysis_worker_plan else 0} repair_workers={repair_workers}"
        )
        self._begin_task(
            total_steps,
            f"修复准备 0/{total_steps}",
            "正在准备修复任务...",
            show_dialog=True,
            dialog_title="修复图片中",
            dialog_header="正在分析并修复图片",
        )

        def worker() -> None:
            step = 0
            repaired: list[RepairRecord] = []
            skipped: list[RepairRecord] = []
            failed: list[tuple[Path, str]] = []
            failed_paths: set[Path] = set()

            if missing:
                with ThreadPoolExecutor(max_workers=analysis_workers) as pool:
                    futures = {pool.submit(analyze_image, path): path for path in missing}
                    for future in as_completed(futures):
                        path = futures[future]
                        try:
                            result = future.result()
                        except Exception as exc:
                            with self.worker_lock:
                                self.errors[path] = str(exc)
                            failed.append((path, str(exc)))
                            failed_paths.add(path)
                            self._log_console(f"repair pre-analysis failed: {path.name} | {exc}")
                        else:
                            with self.worker_lock:
                                self.results[path] = result
                                self.errors.pop(path, None)
                        step += 1
                        self._dispatch_ui(lambda s=step, t=total_steps, name=path.name: self._update_progress(s, t, name, "修复前分析"))

            repair_targets = [path for path in targets if path not in failed_paths]
            with ThreadPoolExecutor(max_workers=repair_workers) as pool:
                futures = {}
                for path in repair_targets:
                    if path in self.errors:
                        if path not in failed_paths:
                            failed.append((path, self.errors[path]))
                            failed_paths.add(path)
                        step += 1
                        self._dispatch_ui(lambda s=step, t=total_steps, name=path.name: self._update_progress(s, t, name, "跳过失败项"))
                        continue
                    def repair_progress(phase: str, p: Path = path) -> None:
                        self._dispatch_ui(
                            lambda s=step, t=total_steps, name=p.name, phase=phase: self._update_repair_phase(
                                s, t, name, phase
                            )
                        )

                    futures[
                        pool.submit(
                            repair_image_file,
                            path,
                            self.results.get(path),
                            selection,
                            base_folder,
                            repair_progress,
                        )
                    ] = path

                for future in as_completed(futures):
                    path = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        failed.append((path, str(exc)))
                        failed_paths.add(path)
                        self._log_console(f"repair failed: {path.name} | {exc}")
                    else:
                        if record is None:
                            skipped.append(
                                RepairRecord(
                                    source_path=path,
                                    output_path=path,
                                    method_ids=[],
                                    op_strengths={},
                                    saved_output=False,
                                    skipped_reason="修复引擎未返回可保存结果。",
                                )
                            )
                            self._log_console(f"repair skipped: {path.name} | 修复引擎未返回可保存结果。")
                        else:
                            if not record.saved_output:
                                skipped.append(record)
                                reason = record.skipped_reason or "当前方案未生成修复输出。"
                                self._log_console(f"repair skipped: {path.name} | {reason}")
                                for note in record.policy_notes:
                                    self._log_console(f"repair note: {path.name} | {note}")
                                for note in record.perf_notes:
                                    self._log_console(f"repair perf: {path.name} | {note}")
                            else:
                                repaired.append(record)
                                self._log_console(f"repair done: {path.name} -> {record.output_path}")
                                for note in record.policy_notes:
                                    self._log_console(f"repair note: {path.name} | {note}")
                                for note in record.perf_notes:
                                    self._log_console(f"repair perf: {path.name} | {note}")
                                self.stats = record_repair(
                                    self.stats,
                                    image_bytes=record.output_path.stat().st_size if record.output_path.exists() else 0,
                                )
                                save_stats(self.stats)
                            self._log_console(self._format_repair_perf_line(record))

                    step += 1
                    self._dispatch_ui(lambda s=step, t=total_steps, name=path.name: self._update_progress(s, t, name, "修复中"))

            for path in targets:
                if path in self.errors:
                    if path not in failed_paths:
                        failed.append((path, self.errors[path]))
                        failed_paths.add(path)
                    if path not in repair_targets:
                        step += 1
                        self._dispatch_ui(lambda s=step, t=total_steps, name=path.name: self._update_progress(s, t, name, "跳过失败项"))

            self._dispatch_ui(lambda: self._repair_finished(repaired, skipped, failed, selection))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, done: int, total: int, filename: str, phase: str) -> None:
        friendly_phase = self._friendly_repair_phase(phase)
        self.progress_controller.update(
            done=done,
            total=total,
            title=f"{friendly_phase} {done}/{total}",
            detail=f"{friendly_phase}：处理第 {done}/{total} 张，当前 {filename} | {self._elapsed_task_text()}",
            status=f"{friendly_phase} {done}/{total}，当前：{filename}",
            dialog_title="修复图片中",
            dialog_header="正在分析并修复图片",
        )

    def _update_repair_phase(self, done: int, total: int, filename: str, phase: str) -> None:
        now = time.monotonic()
        if now - self._last_repair_phase_update < 0.12:
            return
        self._last_repair_phase_update = now
        friendly_phase = self._friendly_repair_phase(phase)
        current_index = min(total, done + 1)
        self.progress_controller.update(
            done=done,
            total=total,
            title=f"修复中 {done}/{total}",
            detail=f"{friendly_phase}：处理第 {current_index}/{total} 张，当前 {filename} | {self._elapsed_task_text()}",
            status=f"{friendly_phase}，当前：{filename}",
            dialog_title="修复图片中",
            dialog_header="正在分析并修复图片",
        )

    def _friendly_repair_phase(self, phase: str) -> str:
        if "修复前分析" in phase:
            return "读取图片并补充分析"
        if "跳过失败项" in phase:
            return "整理不可处理图片"
        if "生成修复方案" in phase:
            return "生成修复方案"
        if "读取图片" in phase or "元数据" in phase:
            return "读取图片与元数据"
        if "曝光" in phase or "色彩" in phase or "清晰度" in phase:
            return "处理曝光、色彩与清晰度"
        if "人像" in phase:
            return "处理人像与画面细节"
        if "准备保存" in phase:
            return "准备保存结果"
        if "保存" in phase:
            return "保存结果"
        return "生成并保存修复结果" if "修复" in phase else phase

    def _repair_finished(
        self,
        repaired: list[RepairRecord],
        skipped: list[RepairRecord],
        failed: list[tuple[Path, str]],
        selection: RepairSelection,
    ) -> None:
        total = len(repaired) + len(skipped) + len(failed)
        detail = f"修复完成：成功 {len(repaired)} 张，跳过 {len(skipped)} 张，失败 {len(failed)} 张。"
        self._log_console(
            f"repair finished: success={len(repaired)} skipped={len(skipped)} failed={len(failed)} overwrite={selection.overwrite_original}"
        )
        self._log_repair_perf_rollup(repaired + skipped)
        self.progress_controller.update(
            done=total,
            total=max(1, total),
            title=f"修复完成 {total}/{total}",
            detail=detail,
            status=detail,
            dialog_title="修复图片中",
            dialog_header="正在分析并修复图片",
        )
        self._finish_task(f"修复完成 {total}/{total}", detail)

        for record in repaired:
            if record.source_path in self.selected_flags:
                self.selected_flags[record.source_path].set(False)

        self.refresh_tree()

        outcome_counts = {
            "normal_saved": 0,
            "forced_saved": 0,
            "forced_rollback": 0,
            "forced_skip_unsuitable": 0,
            "discard_candidate_skipped": 0,
        }
        for record in repaired + skipped:
            outcome_counts[record.outcome_category] = outcome_counts.get(record.outcome_category, 0) + 1
        rollback_noop_count = sum(
            1
            for record in skipped
            if REPAIR_SUMMARY_FILTER_ROLLBACK_NOOP in self._repair_entry_filter_tags(record, saved_output=False)
        )

        lines = [
            f"批量目标 {total} 张",
            f"已修复 {len(repaired)} 张",
            f"已跳过 {len(skipped)} 张",
            f"失败 {len(failed)} 张",
            f"候选回退 / no-op {rollback_noop_count} 张",
            f"强制尝试后保存 {outcome_counts['forced_saved']} 张",
            f"强制尝试但未保存 {outcome_counts['forced_rollback'] + outcome_counts['forced_skip_unsuitable']} 张",
        ]
        if selection.mode == "manual":
            labels = "、".join(get_method_labels(selection.selected_method_ids)) or "无"
            lines.append(f"统一方法：{labels}")
        else:
            lines.append("修复模式：按检测结果自动推荐")
        lines.append(
            "强制修复不值得保留图片："
            + ("已启用（仅允许尝试，仍会回退或跳过保存）" if selection.force_repair_cleanup_candidates else "未启用")
        )

        if selection.overwrite_original:
            lines.append("输出方式：覆盖原文件")
        else:
            lines.append(f"输出目录：{Path(self._resolve_base_folder()).resolve() / selection.output_folder_name}")
            lines.append(f"文件后缀：{selection.filename_suffix or '(无后缀)'}")
        if outcome_counts["normal_saved"]:
            lines.append(f"正常修复：{outcome_counts['normal_saved']} 张")
        if outcome_counts["forced_rollback"]:
            lines.append(f"强制尝试修复但回退：{outcome_counts['forced_rollback']} 张")
        if outcome_counts["forced_skip_unsuitable"] or outcome_counts["discard_candidate_skipped"]:
            lines.append(
                f"因仍不适合而跳过：{outcome_counts['forced_skip_unsuitable'] + outcome_counts['discard_candidate_skipped']} 张"
            )

        outcome_labels = {
            "normal_saved": "正常修复",
            "forced_saved": "强制尝试修复后保存",
            "forced_rollback": "强制尝试修复但回退",
            "forced_skip_unsuitable": "因仍不适合而跳过",
            "discard_candidate_skipped": "默认跳过不值得保留图片",
            "normal_skipped": "常规跳过",
        }
        show_repair_completion_dialog(
            self.root,
            title="修复完成",
            summary_lines=lines,
            entries=self._build_repair_completion_entries(repaired, skipped, failed, outcome_labels),
            default_filter=self.settings.repair_summary_default_filter or REPAIR_SUMMARY_FILTER_ALL,
        )

        if self.debug_open_after_repair_var.get() and repaired:
            entries = [
                DebugOpenEntry(
                    display_name=record.source_path.name,
                    source_path=record.source_path,
                    output_path=record.output_path,
                )
                for record in repaired
            ]
            chosen = show_debug_open_dialog(self.root, entries)
            if chosen:
                self._open_debug_pairs(chosen)

    def _ops_text(self, record: RepairRecord) -> str:
        parts: list[str] = []
        if record.method_ids:
            parts.append("ops=" + ",".join(record.method_ids))
        if record.op_strengths:
            strength_text = ", ".join(f"{name}:{value:.2f}" for name, value in record.op_strengths.items())
            parts.append(f"strengths={strength_text}")
        return " | ".join(parts) if parts else "ops=none"

    def _repair_entry_filter_tags(self, record: RepairRecord, *, saved_output: bool) -> set[str]:
        tags = {REPAIR_SUMMARY_FILTER_REPAIRED if saved_output else REPAIR_SUMMARY_FILTER_SKIPPED}
        if record.forced_repair:
            if saved_output:
                tags.add(REPAIR_SUMMARY_FILTER_FORCED_SAVED)
            else:
                tags.add(REPAIR_SUMMARY_FILTER_FORCED_UNSAVED)
            tags.add(REPAIR_SUMMARY_FILTER_DISCARD_RELATED)
        if record.outcome_category == "discard_candidate_skipped":
            tags.add(REPAIR_SUMMARY_FILTER_DISCARD_RELATED)
        if record.outcome_category in {"forced_rollback", "normal_skipped"}:
            reason_text = (record.skipped_reason or "").lower()
            note_text = " ".join(record.policy_notes).lower()
            if "no-op" in reason_text or "回退" in record.skipped_reason or "no-op" in note_text or "回退" in note_text:
                tags.add(REPAIR_SUMMARY_FILTER_ROLLBACK_NOOP)
        if record.outcome_category == "forced_rollback":
            tags.add(REPAIR_SUMMARY_FILTER_ROLLBACK_NOOP)
        return tags

    def _build_repair_detail_lines(self, record: RepairRecord, *, include_output: bool) -> list[str]:
        lines = [self._ops_text(record)]
        if include_output:
            lines.append(f"输出文件：{record.output_path}")
        if record.skipped_reason:
            lines.append(f"skip reason：{record.skipped_reason}")
        if record.applied_strength is not None:
            lines.append(f"applied strength：{record.applied_strength:.2f}")
        denoise_strength = record.op_strengths.get("reduce_noise")
        if denoise_strength is not None:
            lines.append(f"denoise：{denoise_strength:.2f}")
        for note in record.policy_notes:
            lines.append(f"note：{note}")
        for warning in record.warnings:
            lines.append(f"warning：{warning}")
        for note in record.perf_notes:
            lines.append(f"perf：{note}")
        return lines

    def _build_repair_completion_entries(
        self,
        repaired: list[RepairRecord],
        skipped: list[RepairRecord],
        failed: list[tuple[Path, str]],
        outcome_labels: dict[str, str],
    ) -> list[RepairCompletionEntry]:
        entries: list[RepairCompletionEntry] = []
        for record in repaired:
            status = outcome_labels.get(record.outcome_category, record.outcome_category)
            primary_reason = "已生成修复输出。"
            if record.forced_repair:
                primary_reason = "强制尝试后通过评分与安全检查，已保存修复结果。"
            entries.append(
                RepairCompletionEntry(
                    file_name=record.source_path.name,
                    status=status,
                    primary_reason=primary_reason,
                    ops_or_skip=self._ops_text(record),
                    forced=record.forced_repair,
                    filter_tags=self._repair_entry_filter_tags(record, saved_output=True),
                    detail_lines=self._build_repair_detail_lines(record, include_output=True),
                )
            )
        for record in skipped:
            status = outcome_labels.get(record.outcome_category, record.outcome_category)
            reason = record.skipped_reason or "当前方案未生成修复输出。"
            entries.append(
                RepairCompletionEntry(
                    file_name=record.source_path.name,
                    status=status,
                    primary_reason=reason,
                    ops_or_skip=reason if not record.method_ids else f"{reason} | {self._ops_text(record)}",
                    forced=record.forced_repair,
                    filter_tags=self._repair_entry_filter_tags(record, saved_output=False),
                    detail_lines=self._build_repair_detail_lines(record, include_output=False),
                )
            )
        for path, message in failed:
            entries.append(
                RepairCompletionEntry(
                    file_name=path.name,
                    status="失败",
                    primary_reason=message,
                    ops_or_skip=message,
                    forced=False,
                    filter_tags={REPAIR_SUMMARY_FILTER_FAILED},
                    detail_lines=[f"文件：{path}", f"错误：{message}"],
                )
            )
        return entries

    def _open_debug_pairs(self, entries: list[DebugOpenEntry]) -> None:
        missing: list[str] = []
        open_targets: list[Path] = []
        for entry in entries:
            for path, label in ((entry.source_path, "原图"), (entry.output_path, "修复图")):
                if not path.exists():
                    message = f"{entry.display_name} 的{label}不存在：{path}"
                    missing.append(message)
                    self._log_console(f"debug open missing: {message}")
                    continue
                open_targets.append(path)

        if missing:
            messagebox.showwarning("打开失败", "以下文件不存在，已跳过：\n\n" + "\n".join(missing[:8]))

        if not open_targets:
            return

        def worker() -> None:
            import subprocess

            from paths import IS_MAC

            errors: list[str] = []
            startfile = getattr(os, "startfile", None)
            for path in open_targets:
                try:
                    if startfile is not None:
                        startfile(str(path))
                    elif IS_MAC:
                        subprocess.run(["open", str(path)], check=False)
                    else:
                        subprocess.run(["xdg-open", str(path)], check=False)
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
                    self._log_console(f"debug open failed: {path} | {exc}")
            if errors:
                self._dispatch_ui(
                    lambda msgs=errors: messagebox.showwarning("打开失败", "部分文件未能打开：\n\n" + "\n".join(msgs[:8]))
                )

        threading.Thread(target=worker, daemon=True).start()
