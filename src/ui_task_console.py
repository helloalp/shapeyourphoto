from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from pathlib import Path

from app_settings import ANALYSIS_CONCURRENCY_AUTO, AnalysisWorkerPlan, resolve_analysis_worker_plan
from gpu_accel import GPUBackendStatus, gpu_console_label
from models import AnalysisResult, RepairRecord
from ui.display_names import display_name
from ui_constants import (
    ANALYSIS_BATCH_TIMING_LABELS,
    ANALYSIS_TIMING_LABELS,
    DEFAULT_REPAIR_WORKERS,
    REPAIR_TIMING_LABELS,
)


class UiTaskConsoleMixin:
    def _dispatch_ui(self, callback) -> None:
        self._ui_queue.put(callback)

    def _drain_ui_queue(self) -> None:
        drained = 0
        started_at = time.perf_counter()
        try:
            while drained < 80 and (time.perf_counter() - started_at) < 0.012:
                callback = self._ui_queue.get_nowait()
                callback()
                drained += 1
        except queue.Empty:
            pass
        finally:
            if self.root.winfo_exists():
                delay = 1 if drained >= 80 else 25
                self.root.after(delay, self._drain_ui_queue)

    def _log_console(self, message: str) -> None:
        self.console.log(message)
        if not hasattr(self, "console_text"):
            return

        def _schedule_flush() -> None:
            if self._console_update_pending:
                return
            self._console_update_pending = True
            self.root.after(120, self._flush_console)

        if threading.current_thread() is threading.main_thread():
            _schedule_flush()
        else:
            self._dispatch_ui(_schedule_flush)

    def _flush_console(self) -> None:
        self._console_update_pending = False
        if not hasattr(self, "console_text"):
            return
        started_at = time.perf_counter()
        try:
            self.console_text.config(state="normal")
            self.console_text.delete("1.0", "end")
            self.console_text.insert("1.0", self.console.dump())
            self.console_text.config(state="disabled")
            self.console_text.see("end")
        except tk.TclError:
            return
        self._console_flush_total_ms += (time.perf_counter() - started_at) * 1000.0
        self._console_flush_count += 1

    def _analysis_worker_plan(self, total: int) -> AnalysisWorkerPlan:
        return resolve_analysis_worker_plan(
            total,
            getattr(self.settings, "analysis_concurrency_mode", ANALYSIS_CONCURRENCY_AUTO),
            getattr(self.settings, "analysis_custom_workers", 0),
        )

    def _analysis_workers(self, total: int) -> int:
        return self._analysis_worker_plan(total).actual_workers

    def _analysis_concurrency_label(self, plan: AnalysisWorkerPlan | int) -> str:
        if isinstance(plan, int):
            plan = AnalysisWorkerPlan(
                mode=getattr(self.settings, "analysis_concurrency_mode", ANALYSIS_CONCURRENCY_AUTO),
                requested_workers=plan,
                actual_workers=plan,
            )
        detail = (
            f"线程池 {display_name('worker', plan.mode)} "
            f"请求 {plan.requested_workers} 个，实际 {plan.actual_workers} 个"
        )
        if plan.reason:
            detail += f" ({plan.reason})"
        return detail

    def _repair_workers(self, total: int) -> int:
        return max(1, min(DEFAULT_REPAIR_WORKERS, total))

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in self.control_widgets:
            widget.configure(state=state)

    def _begin_task(
        self,
        total: int,
        title: str,
        detail: str,
        *,
        show_dialog: bool = False,
        dialog_title: str | None = None,
        dialog_header: str | None = None,
        cancel_callback=None,
        cancel_text: str = "取消",
    ) -> None:
        self._task_started_at = time.monotonic()
        self._last_progress_ui_update = 0.0
        self._last_repair_phase_update = 0.0
        self.is_busy = True
        self._set_controls_enabled(False)
        self._active_task_cancel_callback = cancel_callback
        if hasattr(self, "task_cancel_button"):
            if cancel_callback is None:
                self.task_cancel_button.configure(state="disabled")
            else:
                self.task_cancel_button.configure(state="normal", text=cancel_text)
        self.progress_controller.begin(
            total=max(1, total),
            title=title,
            detail=detail,
            status=detail,
            show_dialog=show_dialog,
            dialog_title=dialog_title,
            dialog_header=dialog_header,
            cancel_callback=cancel_callback,
            cancel_text=cancel_text,
        )

    def _finish_task(self, title: str, detail: str) -> None:
        self.is_busy = False
        self._set_controls_enabled(True)
        self._active_task_cancel_callback = None
        if hasattr(self, "task_cancel_button"):
            self.task_cancel_button.configure(state="disabled", text="取消任务")
        self.progress_controller.finish(title=title, detail=detail, status=detail, close_dialog=True)
        self._flush_console()

    def cancel_current_task(self) -> None:
        callback = getattr(self, "_active_task_cancel_callback", None)
        if callback is None:
            return
        if hasattr(self, "task_cancel_button"):
            self.task_cancel_button.configure(state="disabled")
        callback()

    def _elapsed_task_text(self) -> str:
        seconds = max(0, int(time.monotonic() - self._task_started_at)) if self._task_started_at else 0
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"耗时 {hours:02d}:{minutes:02d}:{sec:02d}"
        return f"耗时 {minutes:02d}:{sec:02d}"

    def _format_ms(self, value: float) -> str:
        if value >= 1000.0:
            return f"{value / 1000.0:.2f}s"
        return f"{value:.0f}ms"

    def _sum_timings(self, timings: dict[str, float], keys: tuple[str, ...]) -> float:
        return sum(float(timings.get(key, 0.0)) for key in keys)

    def _format_timing_parts(self, timings: dict[str, float], labels: list[tuple[str, tuple[str, ...]]]) -> str:
        parts = []
        for label, keys in labels:
            value = self._sum_timings(timings, keys)
            if value > 0.0:
                parts.append(f"{label} {self._format_ms(value)}")
        return " | ".join(parts) if parts else "暂无阶段耗时"

    def _slowest_stage(self, timings: dict[str, float], labels: list[tuple[str, tuple[str, ...]]]) -> tuple[str, float]:
        candidates = [(label, self._sum_timings(timings, keys)) for label, keys in labels]
        return max(candidates, key=lambda item: item[1], default=("未记录", 0.0))

    def _top_stage_totals(
        self,
        records: list[AnalysisResult] | list[RepairRecord],
        labels: list[tuple[str, tuple[str, ...]]],
        *,
        extra_timings: dict[str, float] | None = None,
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        totals: dict[str, float] = {}
        for record in records:
            timings = getattr(record, "perf_timings", {})
            for label, keys in labels:
                totals[label] = totals.get(label, 0.0) + self._sum_timings(timings, keys)
        if extra_timings:
            for label, keys in labels:
                totals[label] = totals.get(label, 0.0) + self._sum_timings(extra_timings, keys)
        return [(label, value) for label, value in sorted(totals.items(), key=lambda item: item[1], reverse=True) if value > 0.0][:limit]

    def _format_analysis_perf_line(self, result: AnalysisResult, ui_ms: float) -> str:
        timings = dict(result.perf_timings)
        timings["ui_refresh"] = ui_ms
        parts = self._format_timing_parts(timings, ANALYSIS_TIMING_LABELS + [("UI 刷新", ("ui_refresh",))])
        total = timings.get("analyze_total", 0.0)
        return f"analysis timing: {result.path.name} | total {self._format_ms(total)} | {parts}"

    def _format_repair_perf_line(self, record: RepairRecord) -> str:
        parts = self._format_timing_parts(record.perf_timings, REPAIR_TIMING_LABELS)
        total = record.perf_timings.get("repair_total", 0.0)
        return f"repair timing: {record.source_path.name} | total {self._format_ms(total)} | {parts}"

    def _log_analysis_perf_rollup(
        self,
        paths: list[Path],
        batch_timings: dict[str, float],
        *,
        total: int,
        success: int,
        failed: int,
        canceled: int,
        worker_plan: AnalysisWorkerPlan,
        gpu_status: GPUBackendStatus,
    ) -> None:
        records = [self.results[path] for path in paths if path in self.results]
        batch_timings["console_flush"] = self._console_flush_total_ms
        batch_timings["UI_update"] = sum(record.perf_timings.get("UI_update", 0.0) for record in records)
        wall_ms = batch_timings.get("wall_time", batch_timings.get("total_wall_time", 0.0))
        worker_cumulative_ms = batch_timings.get(
            "worker_cumulative_time",
            sum(record.perf_timings.get("worker_wall_time", record.perf_timings.get("analyze_total", 0.0)) for record in records),
        )
        analyze_cumulative_ms = batch_timings.get(
            "analyze_cumulative_time",
            sum(record.perf_timings.get("analyze_total", 0.0) for record in records),
        )
        queue_wait_ms = batch_timings.get("queue_wait_cumulative", batch_timings.get("queue_wait", 0.0))
        avg_wall_ms = wall_ms / max(1, total)
        avg_worker_ms = worker_cumulative_ms / max(1, len(records))
        parallel_factor = worker_cumulative_ms / max(1.0, wall_ms)
        if not records:
            self._log_console(
                f"本轮分析完成：{total} 张，成功 {success}，失败 {failed}，取消 {canceled} | "
                f"本轮分析真实耗时 {self._format_ms(wall_ms)} | "
                f"并发模式 {self._analysis_concurrency_label(worker_plan)} | CPU/GPU {gpu_console_label(gpu_status)}"
            )
            return
        self._log_console(
            f"本轮分析完成：{total} 张，成功 {success}，失败 {failed}，取消 {canceled} | "
            f"本轮分析真实耗时 {self._format_ms(wall_ms)} | 平均真实等待折算 {self._format_ms(avg_wall_ms)}/张 | "
            f"并发模式 {self._analysis_concurrency_label(worker_plan)} | "
            f"CPU/GPU {gpu_console_label(gpu_status)}"
        )
        self._log_console(
            f"analysis audit: total_wall_time={self._format_ms(wall_ms)} | "
            f"worker_cumulative_time={self._format_ms(worker_cumulative_ms)}（并发 worker 单图耗时累计，不是用户等待时间） | "
            f"analyze_cumulative_time={self._format_ms(analyze_cumulative_ms)} | "
            f"average_wall_time_per_image={self._format_ms(avg_wall_ms)} | "
            f"average_worker_time_per_image={self._format_ms(avg_worker_ms)} | "
            f"parallel_efficiency={parallel_factor:.2f}x | "
            f"queue/wait_cumulative={self._format_ms(queue_wait_ms)} | "
            f"similar_detection={self._format_ms(batch_timings.get('similar_detection', 0.0))} | "
            f"UI_update={self._format_ms(batch_timings.get('UI_update', 0.0))} | "
            f"console_flush={self._format_ms(batch_timings.get('console_flush', 0.0))}/{self._console_flush_count}次"
        )
        for record in sorted(records, key=lambda item: item.perf_timings.get("analyze_total", 0.0), reverse=True)[:5]:
            stage, stage_ms = self._slowest_stage(record.perf_timings, ANALYSIS_TIMING_LABELS)
            self._log_console(
                f"analysis slow image: {record.path.name} | total={self._format_ms(record.perf_timings.get('analyze_total', 0.0))} "
                f"| slowest={stage} {self._format_ms(stage_ms)}"
            )
        top_stages = self._top_stage_totals(records, ANALYSIS_BATCH_TIMING_LABELS, extra_timings=batch_timings, limit=5)
        if top_stages:
            self._log_console(
                "analysis slow stages top5: "
                + " | ".join(f"{label} {self._format_ms(value)}" for label, value in top_stages)
            )
        wall_ms = max(1.0, wall_ms)
        ui_console_ms = batch_timings.get("UI_update", 0.0) + batch_timings.get("console_flush", 0.0)
        similar_ms = batch_timings.get("similar_detection", 0.0)
        notes: list[str] = []
        if parallel_factor < max(1.0, worker_plan.actual_workers * 0.35) and len(records) >= worker_plan.actual_workers:
            notes.append("worker 并行度偏低，可能受磁盘 IO、Python/GIL 阶段或主线程刷新牵制")
        if ui_console_ms >= wall_ms * 0.18:
            notes.append("UI/Console 刷新占比较高")
        if similar_ms >= wall_ms * 0.20:
            notes.append("相似图检测占比较高")
        if queue_wait_ms >= wall_ms * 0.35:
            notes.append("排队等待较多，可考虑提高并发或减少单张分析耗时")
        if not notes:
            notes.append("本轮主要耗时集中在 worker 图像分析阶段")
        self._log_console("analysis bottleneck notes: " + "；".join(notes))

    def _log_repair_perf_rollup(
        self,
        records: list[RepairRecord],
        batch_timings: dict[str, float] | None = None,
        *,
        total: int | None = None,
        failed: int = 0,
        canceled: int = 0,
    ) -> None:
        if not records and not batch_timings:
            return
        batch_timings = dict(batch_timings or {})
        totals = [record.perf_timings.get("repair_total", 0.0) for record in records if record.perf_timings]
        wall_ms = batch_timings.get("total_wall_time", batch_timings.get("wall_time", 0.0))
        worker_cumulative_ms = batch_timings.get("worker_cumulative_time", sum(totals))
        if wall_ms <= 0.0 and not totals:
            return
        if wall_ms <= 0.0:
            wall_ms = worker_cumulative_ms
        total_images = total if total is not None else len(records) + failed + canceled
        avg_wall_ms = wall_ms / max(1, total_images)
        avg_worker_ms = worker_cumulative_ms / max(1, len(totals))
        saved = sum(1 for record in records if record.saved_output)
        skipped = sum(1 for record in records if not record.saved_output)
        rollback_noop = sum(1 for record in records if record.outcome_category in {"forced_rollback", "normal_skipped"} or "rollback" in record.outcome_category or "noop" in record.outcome_category)
        self._log_console(
            f"本轮修复总耗时：{self._format_ms(wall_ms)} | "
            f"平均真实等待折算 {self._format_ms(avg_wall_ms)}/张 | "
            f"保存 {saved}，跳过 {skipped}，失败 {failed}，取消 {canceled}，回退或未保存 {rollback_noop}"
        )
        self._log_console(
            f"repair audit: total_wall_time={self._format_ms(wall_ms)} | "
            f"worker_cumulative_time={self._format_ms(worker_cumulative_ms)}（并发 worker 累计耗时，不是用户等待时间） | "
            f"average_wall_time_per_image={self._format_ms(avg_wall_ms)} | "
            f"average_worker_time_per_image={self._format_ms(avg_worker_ms)}"
        )
        for record in sorted(records, key=lambda item: item.perf_timings.get("repair_total", 0.0), reverse=True)[:5]:
            stage, stage_ms = self._slowest_stage(record.perf_timings, REPAIR_TIMING_LABELS)
            self._log_console(
                f"repair slow image: {record.source_path.name} | total={self._format_ms(record.perf_timings.get('repair_total', 0.0))} "
                f"| slowest={stage} {self._format_ms(stage_ms)}"
            )
        top_stages = self._top_stage_totals(records, REPAIR_TIMING_LABELS, limit=5)
        if top_stages:
            self._log_console(
                "repair slow stages top5: "
                + " | ".join(f"{label} {self._format_ms(value)}" for label, value in top_stages)
            )
