from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from app_settings import scan_mode_label
from file_actions import ScanResult, scan_image_paths_with_progress
from scan_dialogs import SCAN_MODE_ALL, show_scan_mode_dialog
from scan_summary_dialog import show_scan_summary_dialog


class UiScanActionsMixin:
    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(title="选择图片目录")
        if chosen:
            self._log_console(f"selected folder: {chosen}")
            self.folder_var.set(chosen)
            self.scan_folder()

    def choose_image(self) -> None:
        chosen = filedialog.askopenfilename(
            title="选择单张图片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.jfif"),
                ("所有文件", "*.*"),
            ],
        )
        if chosen:
            self._log_console(f"selected image: {chosen}")
            self.load_single_image(Path(chosen))

    def _handle_dropped_paths(self, dropped: list[Path]) -> None:
        image_paths: list[Path] = []
        scan_requests: list[tuple[Path, str]] = []
        for item in dropped:
            if item.is_dir():
                plan = self._resolve_scan_plan(item)
                if plan is None:
                    continue
                scan_requests.append((item, plan))
            elif item.is_file():
                image_paths.append(item)
        if scan_requests:
            self.folder_var.set(str(scan_requests[0][0]))
            self._start_directory_scans(scan_requests, initial_paths=image_paths, origin="drag_drop")
            return
        if not image_paths:
            self._log_console("drag drop ignored: no supported image or scan canceled")
            return
        self._merge_paths(image_paths)
        self.folder_var.set(str(dropped[0]))
        self.thumb_cache.clear()
        self.refresh_tree()
        self._select_path(image_paths[0])
        self._log_console(f"drag drop added: {len(image_paths)} image(s)")

    def load_single_image(self, path: Path) -> None:
        if self.is_busy:
            messagebox.showinfo("提示", "当前有任务正在运行，请稍后。")
            return
        if not path.exists():
            messagebox.showerror("错误", "选中的图片不存在，请重新选择。")
            return

        self.folder_var.set(str(path))
        self.thumb_cache.clear()
        self._merge_paths([path])
        self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
        self.selected_flags[path].set(True)
        self.status_var.set(f"已载入图片：{path.name}")
        self.progress_text_var.set("已载入图片")
        self.progress_detail_var.set("可直接分析当前图片，或继续向列表添加更多图片。")
        self.progress_bar.configure(maximum=max(1, len(self.image_paths)))
        self.progress_value.set(0.0)
        self.refresh_tree()
        self._select_path(path)
        self.show_preview(path)
        self._log_console(f"loaded image: {path}")

    def scan_folder(self) -> None:
        if self.is_busy:
            self._auto_analyze_after_scan = False
            messagebox.showinfo("提示", "当前有任务正在运行，请稍后。")
            return

        folder = self.folder_var.get().strip()
        if not folder:
            self._auto_analyze_after_scan = False
            messagebox.showwarning("提示", "请先选择图片目录。")
            return

        root = Path(folder)
        if not root.exists():
            self._auto_analyze_after_scan = False
            messagebox.showerror("错误", "目录不存在，请重新选择。")
            return

        scan_mode = self._resolve_scan_plan(root)
        if scan_mode is None:
            self._auto_analyze_after_scan = False
            self._log_console(f"scan canceled: {root}")
            return
        self._start_directory_scans([(root, scan_mode)], origin="button")

    def show_last_scan_summary(self) -> None:
        if not self._last_scan_results:
            messagebox.showinfo("提示", "当前还没有可查看的扫描摘要。")
            return
        show_scan_summary_dialog(self.root, self._last_scan_results)

    def _resolve_scan_plan(self, root: Path) -> str | None:
        has_subdirs = any(child.is_dir() for child in root.iterdir())
        if not has_subdirs:
            return SCAN_MODE_ALL
        if self.settings.default_scan_mode != "ask":
            return self.settings.default_scan_mode
        return show_scan_mode_dialog(self.root, root, self.settings.scan_ignore_prefixes)

    def _scan_mode_label(self, mode: str) -> str:
        return scan_mode_label(mode)

    def _start_directory_scans(
        self,
        scan_requests: list[tuple[Path, str]],
        *,
        initial_paths: list[Path] | None = None,
        origin: str,
    ) -> None:
        requests = [(root, mode) for root, mode in scan_requests if root.exists()]
        initial = [path for path in (initial_paths or []) if path.exists()]
        if not requests and initial:
            self._merge_paths(initial)
            self.thumb_cache.clear()
            self.refresh_tree()
            self._select_path(initial[0])
            self._log_console(f"drag drop added: {len(initial)} image(s)")
            return
        if not requests:
            return

        self._last_scan_update = 0.0
        self._begin_task(
            1,
            "正在扫描目录 0/0",
            f"正在扫描目录：{requests[0][0]}",
            show_dialog=True,
            dialog_title="目录扫描中",
            dialog_header="正在扫描目录 / 加载图片",
        )
        for root, mode in requests:
            self._log_console(
                f"scan started: root={root} mode={self._scan_mode_label(mode)} ignore={','.join(self.settings.scan_ignore_prefixes)} origin={origin}"
            )

        def worker() -> None:
            merged_paths = list(initial)
            scan_results: list[ScanResult] = []
            try:
                for root, mode in requests:
                    def progress_callback(done: int, total: int, found: int, current: Path | None, scan_root: Path = root, scan_mode: str = mode) -> None:
                        current_label = "准备扫描..."
                        if current is not None:
                            try:
                                current_label = str(current.relative_to(scan_root))
                            except ValueError:
                                current_label = current.name
                        prefix = f"{scan_root.name} | {self._scan_mode_label(scan_mode)}"
                        self._dispatch_ui(
                            lambda d=done, t=total, f=found, label=f"{prefix} | {current_label}": self._update_scan_progress(d, t, f, label)
                        )

                    scan_result = scan_image_paths_with_progress(
                        root,
                        progress_callback,
                        mode=mode,
                        ignored_dir_prefixes=self.settings.scan_ignore_prefixes,
                    )
                    merged_paths.extend(scan_result.paths)
                    scan_results.append(scan_result)
                    self._log_scan_console_summary(scan_result)
            except Exception as exc:
                self._dispatch_ui(lambda: self._scan_failed(str(exc)))
                return
            self._dispatch_ui(lambda paths=merged_paths, results=scan_results: self._scan_finished(paths, results))

        threading.Thread(target=worker, daemon=True).start()

    def _format_scan_summary(self, scan_result: ScanResult) -> str:
        summary = scan_result.summary
        prefix_counts = summary.skipped_prefix_counts
        prefix_text = "；".join(f"{prefix}：{count} 个" for prefix, count in prefix_counts.items()) if prefix_counts else "无"
        return (
            f"[{summary.root.name}] 扫描模式：{self._scan_mode_label(summary.mode)} | "
            f"跳过目录 {summary.skipped_directory_count} 个 | "
            f"导入图片 {summary.imported_count} 张 | "
            f"命中前缀：{prefix_text}"
        )

    def _log_scan_console_summary(self, scan_result: ScanResult) -> None:
        summary = scan_result.summary
        prefix_counts = summary.skipped_prefix_counts
        if prefix_counts:
            prefix_text = "；".join(f"{prefix}:{count}" for prefix, count in prefix_counts.items())
            self._log_console(
                f"scan skipped summary: root={summary.root} skipped={summary.skipped_directory_count} prefixes={prefix_text}"
            )
            self._log_console(f"跳过目录明细已收进“最近扫描摘要”，共 {summary.skipped_directory_count} 个。")
        else:
            self._log_console(f"scan skipped summary: root={summary.root} skipped=0")

    def _update_scan_progress(self, done: int, total: int, found: int, current_label: str) -> None:
        import time
        now = time.time()
        if now - self._last_scan_update < 0.1 and done < total:
            return
        self._last_scan_update = now
        self.progress_controller.update(
            done=done,
            total=max(1, total),
            title=f"正在扫描目录 {done}/{total}",
            detail=f"已发现 {found} 张图片，当前：{current_label}",
            status=f"扫描目录 {done}/{total}，已发现 {found} 张图片",
            dialog_title="目录扫描中",
            dialog_header="正在扫描目录 / 加载图片",
        )

    def _scan_finished(self, paths: list[Path], scan_results: list[ScanResult]) -> None:
        total_paths = len(paths)
        self.progress_controller.update(
            done=0,
            total=max(1, total_paths),
            title="正在加载图片",
            detail=f"扫描完成，正在导入 {total_paths} 张图片到结果列表。",
            status=f"正在加载图片，已导入 0/{total_paths}",
            dialog_title="目录扫描中",
            dialog_header="正在扫描目录 / 加载图片",
        )
        self.root.after(20, lambda p=paths, r=scan_results: self._finish_scan_loading(p, r))

    def _finish_scan_loading(self, paths: list[Path], scan_results: list[ScanResult]) -> None:
        self._merge_paths(paths)
        self.thumb_cache.clear()
        self.progress_bar.configure(maximum=max(1, len(self.image_paths)))
        self.progress_value.set(0.0)
        self._last_scan_results = list(scan_results)
        self.scan_summary_button.configure(state="normal" if self._last_scan_results else "disabled")
        summary_lines = [self._format_scan_summary(result) for result in scan_results]
        self._last_scan_summary = "；".join(summary_lines)
        for line in summary_lines:
            self._log_console(f"scan summary: {line}")
        self._log_console(f"scan finished: new={len(paths)} total={len(self.image_paths)}")
        detail = f"当前列表共 {len(self.image_paths)} 张图片，本次新读取 {len(paths)} 张。"
        if self._last_scan_summary:
            detail = f"{detail}\n{self._last_scan_summary}\n可点击“查看最近扫描摘要”查看跳过目录明细。"
        self._finish_task("目录扫描和加载完成", detail)
        self.refresh_tree()
        if self.image_paths:
            self._select_path(self.image_paths[0])
        if self._auto_analyze_after_scan and self.image_paths:
            self._auto_analyze_after_scan = False
            self._run_analysis(self.image_paths)
        else:
            self._auto_analyze_after_scan = False

    def _scan_failed(self, error: str) -> None:
        self._auto_analyze_after_scan = False
        self._log_console(f"scan failed: {error}")
        self._finish_task("目录读取失败", error)
        messagebox.showerror("读取失败", f"扫描目录时发生错误：\n{error}")
