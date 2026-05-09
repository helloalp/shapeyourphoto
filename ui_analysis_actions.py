from __future__ import annotations

import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import messagebox

from analyzer import analyze_image
from app_settings import ANALYSIS_CONCURRENCY_AUTO, AnalysisWorkerPlan, GPU_ACCELERATION_OFF
from gpu_accel import GPUBackendStatus, gpu_console_label, resolve_gpu_status
from models import AnalysisResult, SimilarImageGroup
from similar_detector import detect_similar_groups
from stats_store import record_analysis, record_analysis_batch, save_stats
from ui_constants import ANALYSIS_PROGRESS_STEPS, AnalysisCanceled


class UiAnalysisActionsMixin:
    def analyze_all(self) -> None:
        if not self.image_paths:
            self._auto_analyze_after_scan = True
            self.scan_folder()
            return
        self._auto_analyze_after_scan = False
        if self.image_paths:
            self._run_analysis(self.image_paths)

    def analyze_selected(self) -> None:
        targets = [path for path in self._selected_tree_paths() if path in self.image_paths]
        if not targets:
            targets = [path for path, flag in self.selected_flags.items() if flag.get() and path in self.image_paths]
        if not targets:
            path = self._current_path()
            if path is not None:
                targets = [path]
        if not targets:
            messagebox.showinfo("提示", "请先选择至少一张图片。")
            return
        self._run_analysis(targets)

    def _run_analysis(self, targets: list[Path]) -> None:
        if self.is_busy:
            messagebox.showinfo("提示", "当前已有任务正在运行。")
            return

        total = len(targets)
        if total == 0:
            return
        self._analysis_run_id += 1
        run_id = self._analysis_run_id
        cancel_event = threading.Event()
        self._analysis_cancel_event = cancel_event
        self._analysis_cancel_targets = list(targets)
        self.analysis_phase_progress = {path: 0 for path in targets}
        self._last_analysis_targets = list(targets)
        worker_plan = self._analysis_worker_plan(total)
        worker_count = worker_plan.actual_workers
        gpu_status = resolve_gpu_status(getattr(self.settings, "gpu_acceleration_mode", GPU_ACCELERATION_OFF))
        self._console_flush_total_ms = 0.0
        self._console_flush_count = 0

        self._log_console(
            f"analysis started: count={total} mode={self._analysis_concurrency_label(worker_plan)} "
            f"gpu={gpu_console_label(gpu_status)}"
        )
        self._log_console(gpu_status.reason)
        self._begin_task(
            total * ANALYSIS_PROGRESS_STEPS,
            f"分析中 0/{total}",
            f"正在分析 {total} 张图片，请稍候...",
            show_dialog=True,
            dialog_title="分析图片中",
            dialog_header="正在逐张分析图片",
            cancel_callback=lambda rid=run_id: self.cancel_analysis(rid),
            cancel_text="取消分析",
        )

        for path in targets:
            self.results.pop(path, None)
            self.errors.pop(path, None)
            self.cleanup_flags.pop(path, None)
        target_set = set(targets)
        self.similar_groups = [
            group for group in self.similar_groups if not any(path in target_set for path in group.paths)
        ]
        self.refresh_tree()
        current = self._current_path()
        if current in targets:
            self.show_preview(current)

        def worker() -> None:
            done = 0
            batch_results: dict[Path, AnalysisResult] = {}
            batch_timings: dict[str, float] = {}
            batch_started_at = time.perf_counter()
            pool = ThreadPoolExecutor(max_workers=worker_count)
            futures = {}
            try:
                for path in targets:
                    if cancel_event.is_set():
                        break

                    def progress_callback(step: int, steps: int, phase: str, p: Path = path) -> None:
                        if cancel_event.is_set():
                            raise AnalysisCanceled("analysis canceled")
                        self._dispatch_ui(
                            lambda p=p, step=step, steps=steps, phase=phase, rid=run_id: self._update_analysis_phase(
                                p, step, steps, phase, total, rid
                            )
                        )

                    queued_at = time.perf_counter()

                    def analyze_job(p: Path = path, queued: float = queued_at, cb=progress_callback):
                        started = time.perf_counter()
                        result = analyze_image(p, cb)
                        finished = time.perf_counter()
                        result.perf_timings["worker_queue_wait"] = (started - queued) * 1000.0
                        result.perf_timings["worker_wall_time"] = (finished - started) * 1000.0
                        return result

                    futures[pool.submit(analyze_job)] = path

                for future in as_completed(futures):
                    path = futures[future]
                    if cancel_event.is_set():
                        break
                    result: AnalysisResult | None = None
                    error: str | None = None
                    try:
                        result = future.result()
                    except AnalysisCanceled:
                        cancel_event.set()
                        break
                    except Exception as exc:
                        error = str(exc)
                    if result is not None:
                        batch_results[path] = result
                    done += 1
                    self._dispatch_ui(
                        lambda p=path, r=result, e=error, d=done, t=total, rid=run_id: self._handle_analysis_item_done(
                            p, r, e, d, t, rid
                        )
                    )
            finally:
                if cancel_event.is_set():
                    shutdown_started_at = time.perf_counter()
                    for future in futures:
                        future.cancel()
                    pool.shutdown(wait=True, cancel_futures=True)
                    shutdown_ms = (time.perf_counter() - shutdown_started_at) * 1000.0
                    elapsed_ms = (time.perf_counter() - batch_started_at) * 1000.0
                    submitted = len(futures)
                    discarded_results = len(batch_results)
                    canceled_or_pending = max(0, total - done)
                    self._dispatch_ui(
                        lambda rid=run_id, elapsed=elapsed_ms, shutdown=shutdown_ms, sub=submitted, completed=done,
                        discarded=discarded_results, canceled=canceled_or_pending: self._analysis_cancel_worker_finished(
                            rid,
                            total=total,
                            elapsed_ms=elapsed,
                            shutdown_ms=shutdown,
                            submitted=sub,
                            completed=completed,
                            discarded_results=discarded,
                            canceled_or_pending=canceled,
                        )
                    )
                else:
                    pool.shutdown(wait=True)

            if not cancel_event.is_set():
                self._dispatch_ui(lambda rid=run_id, t=total: self._update_similarity_detection_phase(t, rid))
                similar_started_at = time.perf_counter()
                similar_groups = detect_similar_groups(
                    targets,
                    batch_results,
                    max_workers=worker_count,
                    perf_timings=batch_timings,
                )
                similar_ms = (time.perf_counter() - similar_started_at) * 1000.0
                batch_timings["similar_detection"] = max(batch_timings.get("similar_detection", 0.0), similar_ms)
                batch_timings["wall_time"] = (time.perf_counter() - batch_started_at) * 1000.0
                batch_timings["total_wall_time"] = batch_timings["wall_time"]
                batch_timings["worker_cumulative_time"] = sum(
                    result.perf_timings.get("worker_wall_time", result.perf_timings.get("analyze_total", 0.0))
                    for result in batch_results.values()
                )
                batch_timings["total_worker_time"] = batch_timings["worker_cumulative_time"]
                batch_timings["analyze_cumulative_time"] = sum(result.perf_timings.get("analyze_total", 0.0) for result in batch_results.values())
                batch_timings["average_wall_time_per_image"] = batch_timings["wall_time"] / max(1, total)
                batch_timings["average_worker_time_per_image"] = batch_timings["worker_cumulative_time"] / max(1, len(batch_results))
                batch_timings["queue_wait_cumulative"] = sum(result.perf_timings.get("worker_queue_wait", 0.0) for result in batch_results.values())
                batch_timings["queue_wait"] = batch_timings["queue_wait_cumulative"]
                self._dispatch_ui(
                    lambda rid=run_id, groups=similar_groups, timings=batch_timings: self._analysis_finished(
                        total,
                        rid,
                        groups,
                        timings,
                        worker_plan,
                        gpu_status,
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    def cancel_analysis(self, run_id: int | None = None) -> None:
        if run_id is not None and run_id != self._analysis_run_id:
            return
        canceled_run_id = self._analysis_run_id
        cancel_event = self._analysis_cancel_event
        if cancel_event is not None:
            cancel_event.set()
        self._analysis_run_id += 1
        targets = list(self._analysis_cancel_targets or self._last_analysis_targets)
        cleared_results = sum(1 for path in targets if path in self.results)
        cleared_errors = sum(1 for path in targets if path in self.errors)
        for path in targets:
            self.results.pop(path, None)
            self.errors.pop(path, None)
            self.cleanup_flags.pop(path, None)
            self.analysis_phase_progress[path] = 0
        target_set = set(targets)
        self.similar_groups = [
            group for group in self.similar_groups if not any(path in target_set for path in group.paths)
        ]
        self.analysis_phase_progress = {}
        self._last_analysis_targets = []
        self._analysis_cancel_targets = []
        self._analysis_cancel_event = None
        detail = f"已取消本轮分析，{len(targets)} 张图片保留在列表中，可重新点击“分析全部”。"
        elapsed_ms = max(0.0, (time.monotonic() - self._task_started_at) * 1000.0) if self._task_started_at else 0.0
        self._log_console(
            f"analysis cancel requested: run={canceled_run_id} | elapsed={self._format_ms(elapsed_ms)} | "
            f"targets={len(targets)} | cleared_results={cleared_results} | cleared_errors={cleared_errors} | "
            f"canceled={len(targets)}"
        )
        self.is_busy = False
        self._set_controls_enabled(True)
        self.progress_controller.finish(title="分析已取消", detail=detail, status=detail, close_dialog=True)
        self._flush_console()
        self.refresh_tree()
        current = self._current_path()
        if current is not None:
            self.show_preview(current)
        elif targets:
            self._select_path(targets[0])

    def _analysis_cancel_worker_finished(
        self,
        run_id: int,
        *,
        total: int,
        elapsed_ms: float,
        shutdown_ms: float,
        submitted: int,
        completed: int,
        discarded_results: int,
        canceled_or_pending: int,
    ) -> None:
        self._log_console(
            f"analysis cancel confirmed: run={run_id} | wall={self._format_ms(elapsed_ms)} | "
            f"submitted={submitted}/{total} | completed_before_stop={completed} | "
            f"discarded_results={discarded_results} | canceled_or_pending={canceled_or_pending} | "
            f"worker_shutdown_wait={self._format_ms(shutdown_ms)}"
        )

    def _handle_analysis_item_done(
        self,
        path: Path,
        result: AnalysisResult | None,
        error: str | None,
        done: int,
        total: int,
        run_id: int,
    ) -> None:
        if run_id != self._analysis_run_id or (self._analysis_cancel_event is not None and self._analysis_cancel_event.is_set()):
            return
        with self.worker_lock:
            if error:
                self.errors[path] = error
                self.results.pop(path, None)
                self._log_console(f"analysis failed: {path.name} | {error}")
            elif result is not None:
                self.results[path] = result
                self.errors.pop(path, None)
                labels = ",".join(issue.code for issue in result.issues) if result.issues else "ok"
                face_total = result.face_count
                face_validated = result.validated_face_count
                self._log_console(
                    f"analysis done: {path.name} | score={result.overall_score:.2f} | {labels} | "
                    f"faces={face_total}/{face_validated} | portrait={result.portrait_likely}"
                )
                for candidate in result.face_candidates:
                    if candidate.accepted or not candidate.rejection_reasons:
                        continue
                    self._log_console(
                        f"face candidate rejected: {path.name} | box={candidate.box} | "
                        f"conf={candidate.confidence:.2f} | {' / '.join(candidate.rejection_reasons)}"
                    )
                if result.portrait_rejection_reason:
                    self._log_console(f"portrait-aware skipped: {path.name} | {result.portrait_rejection_reason}")
                for cleanup_candidate in result.cleanup_candidates:
                    self._log_console(
                        f"cleanup candidate: {path.name} | {cleanup_candidate.reason_code} | "
                        f"{cleanup_candidate.severity} | conf={cleanup_candidate.confidence:.2f}"
                    )
                for note in result.perf_notes:
                    self._log_console(f"analysis perf: {path.name} | {note}")
                if self.only_problem_var.get() and result.issues:
                    self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
                    self.selected_flags[path].set(True)
                if path in self.cleanup_flags and path not in self._primary_cleanup_candidates():
                    self.cleanup_flags.pop(path, None)
                self.stats = record_analysis(
                    self.stats,
                    image_bytes=path.stat().st_size if path.exists() else 0,
                    has_issue=bool(result.issues),
                    cleanup_candidate_count=len(result.cleanup_candidates),
                )
                save_stats(self.stats)

        ui_started_at = time.perf_counter()
        self.progress_controller.update(
            done=sum(self.analysis_phase_progress.values()),
            total=total * ANALYSIS_PROGRESS_STEPS,
            title=f"分析中 {done}/{total}",
            detail=f"已完成第 {done}/{total} 张：{path.name} | 生成建议与诊断信息 | {self._elapsed_task_text()}",
            status=f"分析进度 {done}/{total}，最近完成：{path.name}",
            dialog_title="分析图片中",
            dialog_header="正在逐张分析图片",
        )
        if not self._refresh_tree_item(path):
            self.refresh_tree()
        self._refresh_cleanup_tree()
        current = self._current_path()
        if current is None:
            self._select_path(path)
        elif current == path:
            self.show_preview(path)
        if result is not None:
            ui_ms = (time.perf_counter() - ui_started_at) * 1000.0
            result.perf_timings["UI_update"] = result.perf_timings.get("UI_update", 0.0) + ui_ms
            self._log_console(self._format_analysis_perf_line(result, ui_ms))

    def _friendly_analysis_phase(self, phase: str) -> str:
        if "读取" in phase or "图像" in phase:
            return "读取图片"
        if "亮度" in phase or "主体" in phase or "背景" in phase:
            return "分析曝光与画面结构"
        if "锐度" in phase or "色彩" in phase or "人像" in phase:
            return "分析色彩与清晰度"
        if "问题" in phase or "建议" in phase:
            return "生成问题与修复建议"
        if "指标" in phase or "最终" in phase:
            return "整理诊断结果"
        return phase

    def _update_analysis_phase(self, path: Path, step: int, steps: int, phase: str, total_images: int, run_id: int) -> None:
        if run_id != self._analysis_run_id or (self._analysis_cancel_event is not None and self._analysis_cancel_event.is_set()):
            return
        normalized_step = max(0, min(ANALYSIS_PROGRESS_STEPS, int(round(step * ANALYSIS_PROGRESS_STEPS / max(1, steps)))))
        previous = self.analysis_phase_progress.get(path, 0)
        if normalized_step > previous:
            self.analysis_phase_progress[path] = normalized_step
        aggregate_done = sum(self.analysis_phase_progress.values())
        finished_images = sum(1 for value in self.analysis_phase_progress.values() if value >= ANALYSIS_PROGRESS_STEPS)
        now = time.monotonic()
        force_update = normalized_step >= ANALYSIS_PROGRESS_STEPS or aggregate_done >= total_images * ANALYSIS_PROGRESS_STEPS
        if not force_update and now - self._last_progress_ui_update < 0.10:
            return
        self._last_progress_ui_update = now
        friendly_phase = self._friendly_analysis_phase(phase)
        detail = f"处理第 {finished_images + 1}/{total_images} 张：{path.name} | {friendly_phase} | {self._elapsed_task_text()}"
        if total_images > 1:
            detail = f"批量分析 {finished_images}/{total_images} | 第 {min(total_images, finished_images + 1)}/{total_images} 张：{path.name} | {friendly_phase} | {self._elapsed_task_text()}"
        self.progress_controller.update(
            done=aggregate_done,
            total=max(1, total_images * ANALYSIS_PROGRESS_STEPS),
            title=f"分析中 {finished_images}/{total_images}",
            detail=detail,
            status=detail,
            dialog_title="分析图片中",
            dialog_header="正在逐张分析图片",
        )

    def _update_similarity_detection_phase(self, total: int, run_id: int) -> None:
        if run_id != self._analysis_run_id or (self._analysis_cancel_event is not None and self._analysis_cancel_event.is_set()):
            return
        self.progress_controller.update(
            done=total * ANALYSIS_PROGRESS_STEPS,
            total=max(1, total * ANALYSIS_PROGRESS_STEPS),
            title="检测相似图片",
            detail=f"分析已完成，正在使用缩略图哈希和摘要特征检测本轮相似图片组。{self._elapsed_task_text()}",
            status="正在检测相似图片组",
            dialog_title="分析图片中",
            dialog_header="正在逐张分析图片",
        )

    def _analysis_finished(
        self,
        total: int,
        run_id: int,
        similar_groups: list[SimilarImageGroup] | None = None,
        batch_timings: dict[str, float] | None = None,
        worker_plan: AnalysisWorkerPlan | None = None,
        gpu_status: GPUBackendStatus | None = None,
    ) -> None:
        if run_id != self._analysis_run_id or (self._analysis_cancel_event is not None and self._analysis_cancel_event.is_set()):
            return
        batch_timings = dict(batch_timings or {})
        worker_plan = worker_plan or AnalysisWorkerPlan(
            mode=getattr(self.settings, "analysis_concurrency_mode", ANALYSIS_CONCURRENCY_AUTO),
            requested_workers=1,
            actual_workers=1,
        )
        gpu_status = gpu_status or resolve_gpu_status(getattr(self.settings, "gpu_acceleration_mode", GPU_ACCELERATION_OFF))
        target_paths = list(self._last_analysis_targets)
        issue_count = sum(1 for path in target_paths if path in self.results and self.results[path].issues)
        error_count = sum(1 for path in target_paths if path in self.errors)
        success_count = sum(1 for path in target_paths if path in self.results)
        similar_groups = similar_groups or []
        target_set = set(self._last_analysis_targets)
        self.similar_groups = [
            group for group in self.similar_groups if not any(path in target_set for path in group.paths)
        ]
        self.similar_groups.extend(similar_groups)
        similar_count = len(similar_groups)
        detail = f"分析完成：问题图片 {issue_count} 张，失败 {error_count} 张，相似组 {similar_count} 组。"
        self._log_console(f"analysis finished: count={total} issues={issue_count} errors={error_count} similar_groups={similar_count}")
        self._log_analysis_perf_rollup(
            self._last_analysis_targets,
            batch_timings,
            total=total,
            success=success_count,
            failed=error_count,
            canceled=0,
            worker_plan=worker_plan,
            gpu_status=gpu_status,
        )
        self.stats = record_analysis_batch(
            self.stats,
            wall_ms=batch_timings.get("total_wall_time", batch_timings.get("wall_time", 0.0)),
            similar_groups=similar_count,
        )
        save_stats(self.stats)
        for group in similar_groups:
            self._log_console(
                f"similar group: #{group.group_id} count={len(group.paths)} score={group.similarity:.2f} | {group.reason}"
            )
        self.analysis_phase_progress = {}
        self.refresh_tree()
        self.progress_controller.update(
            done=total * ANALYSIS_PROGRESS_STEPS,
            total=max(1, total * ANALYSIS_PROGRESS_STEPS),
            title=f"分析完成 {total}/{total}",
            detail=detail,
            status=detail,
            dialog_title="分析图片中",
            dialog_header="正在逐张分析图片",
        )
        self._finish_task(f"分析完成 {total}/{total}", detail)
        self._analysis_cancel_event = None
        self._analysis_cancel_targets = []
        current = self._current_path()
        if current is not None:
            self.show_preview(current)
        self._maybe_prompt_cleanup_candidates(self._last_analysis_targets)
        self._maybe_prompt_similar_groups(similar_groups)
        self._last_analysis_targets = []
