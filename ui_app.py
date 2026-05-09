from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from app_settings import AppSettings, load_app_settings, save_app_settings
from app_console import AppConsole
from app_metadata import APP_NAME, APP_VERSION
from diagnostics_chart import DiagnosticsChart
from dnd_support import install_drop_target
from file_actions import ScanResult
from history_dialog import show_history_dialog
from models import AnalysisResult, SimilarImageGroup
from preview_cache import ThumbnailCache
from progress_dialog import TaskProgressController
from settings_dialog import show_app_settings_dialog
from stats_dialog import show_stats_dialog
from stats_store import load_stats
from ui_analysis_actions import UiAnalysisActionsMixin
from ui_constants import FILTER_OPTIONS
from ui_file_list import UiFileListMixin
from ui_repair_actions import UiRepairActionsMixin
from ui_review_actions import UiReviewActionsMixin
from ui_scan_actions import UiScanActionsMixin
from ui_task_console import UiTaskConsoleMixin


class PhotoAnalyzerApp(
    UiTaskConsoleMixin,
    UiScanActionsMixin,
    UiAnalysisActionsMixin,
    UiRepairActionsMixin,
    UiReviewActionsMixin,
    UiFileListMixin,
):
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.root.geometry("1700x1020")
        self.root.minsize(1380, 880)

        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar(value="请选择图片目录开始分析。")
        self.filter_var = tk.StringVar(value="全部")
        self.only_problem_var = tk.BooleanVar(value=True)
        self.debug_open_after_repair_var = tk.BooleanVar(value=False)
        self.progress_text_var = tk.StringVar(value="等待任务")
        self.progress_detail_var = tk.StringVar(value="尚未开始。")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.hud_name_var = tk.StringVar(value="未选择图片")
        self.hud_risk_var = tk.StringVar(value="风险值 --")
        self.hud_tags_var = tk.StringVar(value="识别结果：等待分析")
        self.hud_methods_var = tk.StringVar(value="推荐修复：等待分析")

        self.image_paths: list[Path] = []
        self.results: dict[Path, AnalysisResult] = {}
        self.errors: dict[Path, str] = {}
        self.selected_flags: dict[Path, tk.BooleanVar] = {}
        self.cleanup_flags: dict[Path, tk.BooleanVar] = {}
        self.similar_groups: list[SimilarImageGroup] = []
        self.item_lookup: dict[str, Path] = {}
        self.path_item_lookup: dict[Path, str] = {}
        self.cleanup_item_lookup: dict[str, Path] = {}
        self.worker_lock = threading.Lock()
        self.is_busy = False
        self.control_widgets: list[ttk.Widget] = []
        self.thumb_cache = ThumbnailCache()
        self.list_menu: tk.Menu | None = None
        self.stats = load_stats()
        self.console = AppConsole()
        self._console_update_pending = False
        self._last_progress_ui_update = 0.0
        self._last_repair_phase_update = 0.0
        self._settings_warnings: list[str] = []
        self.settings: AppSettings = load_app_settings(report_warning=self._settings_warnings.append, create_if_missing=True)
        self.drop_target = None
        self.sort_column = "name"
        self.sort_reverse = False
        self.analysis_phase_progress: dict[Path, int] = {}
        self._last_scan_update = 0.0
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._last_analysis_targets: list[Path] = []
        self._analysis_run_id = 0
        self._analysis_cancel_event: threading.Event | None = None
        self._analysis_cancel_targets: list[Path] = []
        self._task_started_at = 0.0
        self._last_scan_summary: str = ""
        self._last_scan_results: list[ScanResult] = []
        self._auto_analyze_after_scan = False
        self._console_flush_total_ms = 0.0
        self._console_flush_count = 0

        self._configure_style()
        self._build_ui()
        self.progress_controller = TaskProgressController(
            self.root,
            self.progress_bar,
            self.progress_value,
            self.progress_text_var,
            self.progress_detail_var,
            self.status_var,
        )
        self.root.after(25, self._drain_ui_queue)
        self._install_drag_drop()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after_idle(self._apply_initial_layout)
        for warning in self._settings_warnings:
            self._log_console(warning)
        self._log_console(f"scan ignore prefixes: {', '.join(self.settings.scan_ignore_prefixes)}")

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg="#eef3ef")
        style.configure("TFrame", background="#eef3ef")
        style.configure("Panel.TFrame", background="#fbfcfa")
        style.configure("TopCard.TFrame", background="#f5faf6")
        style.configure("TLabel", background="#eef3ef", foreground="#1f3527", font=("Microsoft YaHei UI", 11))
        style.configure("Header.TLabel", background="#eef3ef", foreground="#17361f", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("Sub.TLabel", background="#eef3ef", foreground="#45604d", font=("Microsoft YaHei UI", 11))
        style.configure("PanelTitle.TLabel", background="#fbfcfa", foreground="#1f3527", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("HudTitle.TLabel", background="#f5faf6", foreground="#163624", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("HudValue.TLabel", background="#f5faf6", foreground="#2d5640", font=("Microsoft YaHei UI", 9))
        style.configure("Treeview", font=("Microsoft YaHei UI", 10), rowheight=90)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(10, 7))
        style.configure("Soft.TButton", font=("Microsoft YaHei UI", 11), padding=(10, 7))
        style.configure("TLabelframe", background="#fbfcfa", bordercolor="#d7e3da")
        style.configure("TLabelframe.Label", background="#fbfcfa", foreground="#244333", font=("Microsoft YaHei UI", 11, "bold"))

    def _build_ui(self) -> None:
        menu_bar = tk.Menu(self.root)
        review_menu = tk.Menu(menu_bar, tearoff=False)
        review_menu.add_command(label="打开不适合保留候选", command=self.open_cleanup_review_window)
        review_menu.add_command(label="打开相似图片组", command=self.open_similar_group_window)
        review_menu.add_command(label="最近扫描摘要", command=self.show_last_scan_summary)
        menu_bar.add_cascade(label="查看", menu=review_menu)
        settings_menu = tk.Menu(menu_bar, tearoff=False)
        settings_menu.add_command(label="应用设置", command=self.open_settings_panel)
        menu_bar.add_cascade(label="设置", menu=settings_menu)
        self.root.configure(menu=menu_bar)

        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        top_shell = ttk.Frame(outer, style="TopCard.TFrame", padding=14)
        top_shell.pack(fill="x")
        body_shell = ttk.Frame(outer, style="Panel.TFrame", padding=(0, 12, 0, 0))
        body_shell.pack(fill="both", expand=True)

        header = ttk.Frame(top_shell, style="TopCard.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=f"{APP_NAME} v{APP_VERSION}", style="Header.TLabel").pack(anchor="w")
        subtitle = "逐张实时分析、缩略图预览、条图诊断、自动修复与批量清理。"
        ttk.Label(header, text=subtitle, style="Sub.TLabel").pack(anchor="w", pady=(4, 12))

        controls = ttk.Frame(top_shell, style="Panel.TFrame", padding=14)
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)

        path_entry = ttk.Entry(controls, textvariable=self.folder_var, font=("Consolas", 11))
        path_entry.grid(row=0, column=0, rowspan=2, sticky="ew", padx=(0, 12), pady=(0, 4))

        choose_folder_button = ttk.Button(controls, text="选择目录", command=self.choose_folder)
        choose_image_button = ttk.Button(controls, text="选择图片", command=self.choose_image)
        scan_button = ttk.Button(
            controls,
            text="读取目录",
            style="Soft.TButton",
            command=self.scan_folder,
        )
        analyze_all_button = ttk.Button(controls, text="分析全部", style="Accent.TButton", command=self.analyze_all)
        analyze_selected_button = ttk.Button(controls, text="分析选中", command=self.analyze_selected)
        repair_current_button = ttk.Button(controls, text="修复当前", command=self.repair_current)
        repair_checked_button = ttk.Button(controls, text="批量修复勾选", command=self.repair_checked)
        stats_button = ttk.Button(controls, text="累计统计", command=self.show_stats)
        history_button = ttk.Button(controls, text="更新历史", command=lambda: show_history_dialog(self.root))
        export_button = ttk.Button(controls, text="导出清理清单", command=self.export_selected)
        cleanup_button = ttk.Button(controls, text="清理勾选项", command=self.cleanup_selected)

        button_specs: list[ttk.Button] = []
        button_specs.append(choose_folder_button)
        button_specs.extend(
            [
                choose_image_button,
                scan_button,
                analyze_all_button,
                analyze_selected_button,
                repair_current_button,
                repair_checked_button,
                stats_button,
                history_button,
                export_button,
                cleanup_button,
            ]
        )
        button_columns = 6
        for offset in range(button_columns):
            controls.columnconfigure(offset + 1, weight=1)
        for index, button in enumerate(button_specs):
            row = index // button_columns
            column = 1 + (index % button_columns)
            button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)

        self.control_widgets.extend(button_specs)

        toolbar = ttk.Frame(top_shell, padding=(0, 10), style="TopCard.TFrame")
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="筛选：").pack(side="left")
        filter_box = ttk.Combobox(toolbar, textvariable=self.filter_var, state="readonly", values=FILTER_OPTIONS, width=14)
        filter_box.pack(side="left", padx=(0, 12))
        filter_box.bind("<<ComboboxSelected>>", lambda _: self.refresh_tree())
        auto_check = ttk.Checkbutton(toolbar, text="默认勾选问题图", variable=self.only_problem_var)
        auto_check.pack(side="left")
        debug_open_check = ttk.Checkbutton(
            toolbar,
            text="调试模式：修复后选择打开前后对比",
            variable=self.debug_open_after_repair_var,
        )
        debug_open_check.pack(side="left", padx=(12, 0))
        ttk.Label(toolbar, text="提示：支持目录/图片拖入，分栏边界可拖动调整。", style="Sub.TLabel").pack(side="right")
        self.control_widgets.extend([filter_box, auto_check, debug_open_check])

        progress_panel = ttk.LabelFrame(top_shell, text="任务进度", padding=14)
        progress_panel.pack(fill="x", pady=(0, 2))
        self.progress_bar = ttk.Progressbar(progress_panel, mode="determinate", maximum=1, variable=self.progress_value)
        self.progress_bar.pack(fill="x", pady=(2, 6))
        ttk.Label(progress_panel, textvariable=self.progress_text_var, style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(progress_panel, textvariable=self.progress_detail_var).pack(anchor="w", pady=(4, 0))
        self.scan_summary_button = ttk.Button(
            progress_panel,
            text="查看最近扫描摘要",
            command=self.show_last_scan_summary,
            state="disabled",
        )
        self.scan_summary_button.pack(anchor="e", pady=(8, 0))

        main = ttk.PanedWindow(body_shell, orient="horizontal")
        main.pack(fill="both", expand=True)
        self.main_pane = main

        left = ttk.Frame(main, style="Panel.TFrame", padding=12)
        right = ttk.Frame(main, style="Panel.TFrame", padding=12)
        main.add(left, weight=2)
        main.add(right, weight=3)

        ttk.Label(left, text="缩略图结果列表", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        tree_frame = ttk.Frame(left, style="Panel.TFrame")
        tree_frame.pack(fill="both", expand=True)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("pick", "status", "risk", "tags"),
            show=("tree", "headings"),
            selectmode="extended",
        )
        self.tree.heading("#0", text="预览 / 文件名", command=lambda: self._toggle_sort("name"))
        self.tree.column("#0", width=370, anchor="w")
        self.tree.heading("pick", text="处理状态")
        self.tree.column("pick", width=92, anchor="center")
        self.tree.heading("status", text="状态", command=lambda: self._toggle_sort("status"))
        self.tree.heading("risk", text="风险值", command=lambda: self._toggle_sort("risk"))
        self.tree.heading("tags", text="识别结果", command=lambda: self._toggle_sort("tags"))
        self.tree.column("status", width=90, anchor="center")
        self.tree.column("risk", width=90, anchor="center")
        self.tree.column("tags", width=340, anchor="w")

        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.toggle_cleanup_flag)
        self.tree.bind("<Button-1>", self.on_tree_click, add="+")
        self.tree.bind("<Button-3>", self.open_context_menu)

        self.list_menu = tk.Menu(self.root, tearoff=False)
        self.list_menu.add_command(label="切换处理状态", command=self.toggle_cleanup_flag)
        self.list_menu.add_separator()
        self.list_menu.add_command(label="移出此列表", command=self.remove_current_from_list)

        action_bar = ttk.Frame(left)
        action_bar.pack(fill="x", pady=(10, 0))
        ttk.Button(action_bar, text="选中当前", command=self.select_current).pack(side="left")
        ttk.Button(action_bar, text="取消当前", command=self.unselect_current).pack(side="left", padx=6)
        ttk.Button(action_bar, text="全选问题图", command=self.select_problem_items).pack(side="left")
        ttk.Button(action_bar, text="取消全部勾选", command=self.unselect_all).pack(side="left", padx=6)
        ttk.Button(action_bar, text="刷新列表", command=self.refresh_tree).pack(side="left")
        ttk.Label(action_bar, text="单击处理状态可切换，右键可移出列表。").pack(side="right")

        cleanup_frame = ttk.LabelFrame(left, text="不适合保留候选", padding=10)
        cleanup_frame.pack(fill="both", expand=False, pady=(12, 0))
        cleanup_frame.columnconfigure(0, weight=1)
        cleanup_frame.rowconfigure(1, weight=1)
        ttk.Label(
            cleanup_frame,
            text="分析完成后会在这里汇总高风险清理候选。默认全部不勾选，需要用户确认后才会执行安全清理。",
            style="Sub.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        cleanup_tree_frame = ttk.Frame(cleanup_frame, style="Panel.TFrame")
        cleanup_tree_frame.grid(row=1, column=0, sticky="nsew")
        cleanup_tree_frame.columnconfigure(0, weight=1)
        cleanup_tree_frame.rowconfigure(0, weight=1)

        self.cleanup_tree = ttk.Treeview(
            cleanup_tree_frame,
            columns=("pick", "severity", "confidence", "reason"),
            show=("tree", "headings"),
            selectmode="extended",
            height=5,
        )
        self.cleanup_tree.heading("#0", text="缩略图 / 文件名")
        self.cleanup_tree.column("#0", width=260, anchor="w")
        self.cleanup_tree.heading("pick", text="待处理")
        self.cleanup_tree.column("pick", width=72, anchor="center")
        self.cleanup_tree.heading("severity", text="严重度")
        self.cleanup_tree.column("severity", width=72, anchor="center")
        self.cleanup_tree.heading("confidence", text="置信度")
        self.cleanup_tree.column("confidence", width=72, anchor="center")
        self.cleanup_tree.heading("reason", text="主要原因")
        self.cleanup_tree.column("reason", width=360, anchor="w")
        cleanup_scroll = ttk.Scrollbar(cleanup_tree_frame, orient="vertical", command=self.cleanup_tree.yview)
        self.cleanup_tree.configure(yscrollcommand=cleanup_scroll.set)
        self.cleanup_tree.grid(row=0, column=0, sticky="nsew")
        cleanup_scroll.grid(row=0, column=1, sticky="ns")
        self.cleanup_tree.bind("<<TreeviewSelect>>", self.on_cleanup_tree_select)
        self.cleanup_tree.bind("<Button-1>", self.on_cleanup_tree_click, add="+")

        cleanup_action_bar = ttk.Frame(cleanup_frame)
        cleanup_action_bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.cleanup_delete_button = ttk.Button(
            cleanup_action_bar,
            text="移入安全清理",
            command=self.cleanup_selected_candidates,
            state="disabled",
        )
        self.cleanup_delete_button.pack(side="left")
        ttk.Button(cleanup_action_bar, text="勾选当前", command=self.select_cleanup_current).pack(side="left", padx=(6, 0))
        ttk.Button(cleanup_action_bar, text="切换所选", command=self.toggle_selected_cleanup_candidates).pack(side="left", padx=6)
        ttk.Button(cleanup_action_bar, text="全选", command=self.select_all_cleanup_candidates).pack(side="left")
        ttk.Button(cleanup_action_bar, text="取消全选", command=self.unselect_all_cleanup_candidates).pack(side="left", padx=6)
        self.cleanup_hint_var = tk.StringVar(value="当前没有勾选候选，可直接跳过。")
        ttk.Label(cleanup_action_bar, textvariable=self.cleanup_hint_var, style="Sub.TLabel").pack(side="right")

        ttk.Label(right, text="预览、指标、诊断与信息", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.right_stack_pane = ttk.PanedWindow(right, orient="vertical")
        self.right_stack_pane.pack(fill="both", expand=True)

        self.bottom_right_pane = ttk.PanedWindow(self.right_stack_pane, orient="horizontal")
        chart_frame = ttk.Frame(self.right_stack_pane, style="Panel.TFrame", padding=10)
        summary_frame = ttk.Frame(self.bottom_right_pane, style="Panel.TFrame", padding=10)
        info_frame = ttk.Frame(self.bottom_right_pane, style="Panel.TFrame", padding=10)
        self.right_stack_pane.add(chart_frame, weight=4)
        self.right_stack_pane.add(self.bottom_right_pane, weight=2)
        self.bottom_right_pane.add(summary_frame, weight=3)
        self.bottom_right_pane.add(info_frame, weight=2)

        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(1, weight=1)

        hud_frame = ttk.Frame(chart_frame, style="TopCard.TFrame", padding=(10, 8))
        hud_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        hud_frame.columnconfigure(0, weight=3)
        hud_frame.columnconfigure(1, weight=1)
        ttk.Label(hud_frame, textvariable=self.hud_name_var, style="HudTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(hud_frame, textvariable=self.hud_risk_var, style="HudTitle.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(hud_frame, textvariable=self.hud_tags_var, style="HudValue.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 0))
        ttk.Label(hud_frame, textvariable=self.hud_methods_var, style="HudValue.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.chart = DiagnosticsChart(chart_frame)
        self.chart.grid(row=1, column=0, sticky="nsew")

        summary_frame.columnconfigure(0, weight=1)
        summary_frame.rowconfigure(0, weight=1)
        self.summary_text = tk.Text(
            summary_frame,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
            bg="#f8fbf8",
            relief="flat",
            padx=10,
            pady=10,
        )
        summary_scroll = ttk.Scrollbar(summary_frame, orient="vertical", command=self.summary_text.yview)
        self.summary_text.configure(yscrollcommand=summary_scroll.set)
        self.summary_text.grid(row=0, column=0, sticky="nsew")
        summary_scroll.grid(row=0, column=1, sticky="ns")
        self.summary_text.insert("1.0", "右下区域会显示当前图片的诊断说明、建议和推荐修复方法。")
        self.summary_text.config(state="disabled")

        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        info_book = ttk.Notebook(info_frame)
        info_book.grid(row=0, column=0, sticky="nsew")

        meta_tab = ttk.Frame(info_book)
        meta_tab.columnconfigure(0, weight=1)
        meta_tab.rowconfigure(0, weight=1)
        self.meta_text = tk.Text(meta_tab, wrap="word", font=("Microsoft YaHei UI", 10), bg="#f8fbf8", relief="flat", padx=10, pady=10)
        meta_scroll = ttk.Scrollbar(meta_tab, orient="vertical", command=self.meta_text.yview)
        self.meta_text.configure(yscrollcommand=meta_scroll.set)
        self.meta_text.grid(row=0, column=0, sticky="nsew")
        meta_scroll.grid(row=0, column=1, sticky="ns")
        self.meta_text.insert("1.0", "这里会显示 EXIF、DPI、ICC、XMP 等属性信息。")
        self.meta_text.config(state="disabled")

        console_tab = ttk.Frame(info_book)
        console_tab.columnconfigure(0, weight=1)
        console_tab.rowconfigure(0, weight=1)
        self.console_text = tk.Text(console_tab, wrap="word", font=("Consolas", 9), bg="#f8fbf8", relief="flat", padx=10, pady=10)
        console_scroll = ttk.Scrollbar(console_tab, orient="vertical", command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=console_scroll.set)
        self.console_text.grid(row=0, column=0, sticky="nsew")
        console_scroll.grid(row=0, column=1, sticky="ns")
        self.console_text.insert("1.0", self.console.dump())
        self.console_text.config(state="disabled")

        info_book.add(meta_tab, text="属性 / EXIF")
        info_book.add(console_tab, text="Console")

        status = ttk.Label(body_shell, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", pady=(10, 0))

    def _apply_initial_layout(self) -> None:
        try:
            self.main_pane.sashpos(0, 620)
            self.bottom_right_pane.sashpos(0, 610)
            self.right_stack_pane.sashpos(0, 560)
        except Exception:
            pass

    def _install_drag_drop(self) -> None:
        try:
            self.drop_target = install_drop_target(self.root, self._handle_dropped_paths)
            self._log_console("drag and drop ready")
        except Exception as exc:
            self._log_console(f"drag and drop init failed: {exc}")

    def _on_close(self) -> None:
        try:
            if self.drop_target is not None:
                self.drop_target.uninstall()
        finally:
            self.root.destroy()

    def show_stats(self) -> None:
        show_stats_dialog(self.root, self.stats)

    def open_settings_panel(self) -> None:
        settings = show_app_settings_dialog(self.root, self.settings)
        if settings is None:
            return
        try:
            save_app_settings(settings, report_warning=lambda message: self._log_console(message))
        except Exception as exc:
            messagebox.showerror("保存失败", f"应用设置保存失败：\n{exc}")
            self._log_console(f"settings save failed: {exc}")
            return
        self.settings = settings
        self.status_var.set("应用设置已保存，新的扫描和修复详情窗口会立即使用最新配置。")
        self._log_console(
            "settings updated: "
            f"ignore={','.join(self.settings.scan_ignore_prefixes)} | "
            f"default_scan={self.settings.default_scan_mode} | "
            f"repair_summary_filter={self.settings.repair_summary_default_filter} | "
            f"analysis_concurrency={self.settings.analysis_concurrency_mode}:{self.settings.analysis_custom_workers or 'auto'} | "
            f"gpu={self.settings.gpu_acceleration_mode}"
        )
