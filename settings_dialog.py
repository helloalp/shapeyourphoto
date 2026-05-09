from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app_settings import (
    ANALYSIS_CONCURRENCY_OPTIONS,
    AppSettings,
    CONSOLE_TIME_MODE_OPTIONS,
    DEFAULT_SCAN_IGNORE_PREFIXES,
    GPU_ACCELERATION_OPTIONS,
    REPAIR_SUMMARY_FILTER_OPTIONS,
    SCAN_MODE_OPTIONS,
    normalize_analysis_concurrency_mode,
    normalize_analysis_custom_workers,
    normalize_default_scan_mode,
    normalize_gpu_acceleration_mode,
    normalize_console_time_mode,
    normalize_repair_summary_filter,
    normalize_scan_ignore_prefixes,
    validate_settings_payload,
)
from gpu_accel import detect_gpu_backend
from ui.themes import THEME_OPTIONS, get_theme, normalize_theme_id
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


class AppSettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, settings: AppSettings) -> None:
        super().__init__(parent)
        self.title(app_window_title("应用设置"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(760, 560)
        self.result: AppSettings | None = None
        self._size_notice_var = tk.StringVar(value="")

        normalized = validate_settings_payload(settings.__dict__)
        self._scan_mode_value_to_label = dict(SCAN_MODE_OPTIONS)
        self._scan_mode_label_to_value = {label: value for value, label in SCAN_MODE_OPTIONS}
        self._summary_filter_value_to_label = dict(REPAIR_SUMMARY_FILTER_OPTIONS)
        self._summary_filter_label_to_value = {label: value for value, label in REPAIR_SUMMARY_FILTER_OPTIONS}
        self._concurrency_value_to_label = dict(ANALYSIS_CONCURRENCY_OPTIONS)
        self._concurrency_label_to_value = {label: value for value, label in ANALYSIS_CONCURRENCY_OPTIONS}
        self._gpu_value_to_label = dict(GPU_ACCELERATION_OPTIONS)
        self._gpu_label_to_value = {label: value for value, label in GPU_ACCELERATION_OPTIONS}
        self._console_time_value_to_label = dict(CONSOLE_TIME_MODE_OPTIONS)
        self._console_time_label_to_value = {label: value for value, label in CONSOLE_TIME_MODE_OPTIONS}
        self._theme_value_to_label = dict(THEME_OPTIONS)
        self._theme_label_to_value = {label: value for value, label in THEME_OPTIONS}

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="应用设置", font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")

        notebook = ttk.Notebook(outer)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(12, 0))

        scan_tab = ttk.Frame(notebook, padding=14)
        scan_tab.columnconfigure(0, weight=1)
        scan_tab.rowconfigure(3, weight=1)
        notebook.add(scan_tab, text="扫描")

        ttk.Label(scan_tab, text="扫描忽略目录前缀", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            scan_tab,
            text="命中前缀的目录及其全部子目录都不会被扫描。默认至少保留 `_repair`，避免误扫输出目录。",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 10))

        add_row = ttk.Frame(scan_tab)
        add_row.grid(row=2, column=0, sticky="ew")
        add_row.columnconfigure(0, weight=1)
        self.prefix_var = tk.StringVar()
        entry = ttk.Entry(add_row, textvariable=self.prefix_var)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", lambda _event: self._add_prefix())
        ttk.Button(add_row, text="添加前缀", command=self._add_prefix).grid(row=0, column=1, padx=(8, 0))

        list_frame = ttk.Frame(scan_tab)
        list_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.prefix_list = tk.Listbox(list_frame, activestyle="none", font=("Consolas", 11), exportselection=False)
        prefix_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.prefix_list.yview)
        self.prefix_list.configure(yscrollcommand=prefix_scroll.set)
        self.prefix_list.grid(row=0, column=0, sticky="nsew")
        prefix_scroll.grid(row=0, column=1, sticky="ns")
        for prefix in normalized.scan_ignore_prefixes:
            self.prefix_list.insert("end", prefix)

        prefix_actions = ttk.Frame(scan_tab)
        prefix_actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(prefix_actions, text="删除选中", command=self._remove_selected).pack(side="left")
        ttk.Button(prefix_actions, text="恢复默认", command=self._restore_defaults).pack(side="left", padx=(8, 0))

        behavior_tab = ttk.Frame(notebook, padding=14)
        behavior_tab.columnconfigure(1, weight=1)
        notebook.add(behavior_tab, text="行为偏好")

        ttk.Label(behavior_tab, text="默认扫描行为", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            behavior_tab,
            text="当目录包含子目录时，可以选择每次询问，或直接使用固定扫描模式。",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 10))

        ttk.Label(behavior_tab, text="默认扫描模式：").grid(row=2, column=0, sticky="w")
        self.scan_mode_var = tk.StringVar(value=self._scan_mode_value_to_label[normalized.default_scan_mode])
        ttk.Combobox(
            behavior_tab,
            textvariable=self.scan_mode_var,
            state="readonly",
            values=[label for _value, label in SCAN_MODE_OPTIONS],
            width=28,
        ).grid(row=2, column=1, sticky="w")

        ttk.Label(behavior_tab, text="修复完成详情默认筛选：").grid(row=3, column=0, sticky="w", pady=(16, 0))
        self.summary_filter_var = tk.StringVar(value=self._summary_filter_value_to_label[normalized.repair_summary_default_filter])
        ttk.Combobox(
            behavior_tab,
            textvariable=self.summary_filter_var,
            state="readonly",
            values=[label for _value, label in REPAIR_SUMMARY_FILTER_OPTIONS],
            width=28,
        ).grid(row=3, column=1, sticky="w", pady=(16, 0))

        ttk.Label(
            behavior_tab,
            text="后续新增设置应继续复用 app_settings.py 的统一默认值、校验、读写和容错接口。",
            wraplength=680,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(18, 0))

        performance_tab = ttk.Frame(notebook, padding=14)
        performance_tab.columnconfigure(1, weight=1)
        notebook.add(performance_tab, text="性能")

        ttk.Label(performance_tab, text="分析并发", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            performance_tab,
            text="控制批量分析 worker 数。自动模式会按 CPU 核心数和任务数量选择安全值；大图很多时建议先使用自动或中等。",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 10))

        ttk.Label(performance_tab, text="并发模式：").grid(row=2, column=0, sticky="w")
        self.concurrency_var = tk.StringVar(value=self._concurrency_value_to_label[normalized.analysis_concurrency_mode])
        ttk.Combobox(
            performance_tab,
            textvariable=self.concurrency_var,
            state="readonly",
            values=[label for _value, label in ANALYSIS_CONCURRENCY_OPTIONS],
            width=28,
        ).grid(row=2, column=1, sticky="w")

        ttk.Label(performance_tab, text="自定义 worker 数：").grid(row=3, column=0, sticky="w", pady=(12, 0))
        self.custom_workers_var = tk.StringVar(value=str(normalized.analysis_custom_workers or ""))
        ttk.Spinbox(
            performance_tab,
            from_=1,
            to=32,
            textvariable=self.custom_workers_var,
            width=10,
        ).grid(row=3, column=1, sticky="w", pady=(12, 0))

        ttk.Label(performance_tab, text="GPU 加速", font=("Microsoft YaHei UI", 11, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(22, 0))
        ttk.Label(
            performance_tab,
            text="GPU 是可选能力；未检测到可用后端时会自动回退 CPU，不会影响启动和现有分析流程。",
            wraplength=680,
            justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 10))

        ttk.Label(performance_tab, text="GPU 加速：").grid(row=6, column=0, sticky="w")
        self.gpu_mode_var = tk.StringVar(value=self._gpu_value_to_label[normalized.gpu_acceleration_mode])
        ttk.Combobox(
            performance_tab,
            textvariable=self.gpu_mode_var,
            state="readonly",
            values=[label for _value, label in GPU_ACCELERATION_OPTIONS],
            width=28,
        ).grid(row=6, column=1, sticky="w")

        backend_status = detect_gpu_backend()
        backend_label = backend_status.backend_name if backend_status.available else "未检测到"
        ttk.Label(performance_tab, text="可用后端：").grid(row=7, column=0, sticky="w", pady=(12, 0))
        ttk.Label(performance_tab, text=backend_label).grid(row=7, column=1, sticky="w", pady=(12, 0))
        ttk.Label(
            performance_tab,
            text=backend_status.reason,
            wraplength=680,
            justify="left",
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        console_tab = ttk.Frame(notebook, padding=14)
        console_tab.columnconfigure(1, weight=1)
        notebook.add(console_tab, text="Console")
        ttk.Label(console_tab, text="Console 时间显示", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            console_tab,
            text="只影响保存设置之后新写入的 Console 日志；旧日志不会重写。",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 10))
        ttk.Label(console_tab, text="时间格式：").grid(row=2, column=0, sticky="w")
        self.console_time_var = tk.StringVar(value=self._console_time_value_to_label[normalized.console_time_mode])
        ttk.Combobox(
            console_tab,
            textvariable=self.console_time_var,
            state="readonly",
            values=[label for _value, label in CONSOLE_TIME_MODE_OPTIONS],
            width=34,
        ).grid(row=2, column=1, sticky="w")
        ttk.Label(
            console_tab,
            text="24 小时制适合日常记录；12 小时制会明确显示 AM/PM；启动后经过时间适合排查长任务耗时。",
            wraplength=680,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(14, 0))

        appearance_tab = ttk.Frame(notebook, padding=14)
        appearance_tab.columnconfigure(1, weight=1)
        notebook.add(appearance_tab, text="外观 / 风格")
        ttk.Label(appearance_tab, text="应用风格", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            appearance_tab,
            text="风格通过颜色 token、字体微调和间距微调应用到主窗口及主要弹窗。默认“经典清绿”尽量贴近当前视觉。",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 10))
        ttk.Label(appearance_tab, text="预置风格：").grid(row=2, column=0, sticky="w")
        self.theme_var = tk.StringVar(value=self._theme_value_to_label[normalized.theme_id])
        theme_box = ttk.Combobox(
            appearance_tab,
            textvariable=self.theme_var,
            state="readonly",
            values=[label for _value, label in THEME_OPTIONS],
            width=28,
        )
        theme_box.grid(row=2, column=1, sticky="w")
        self.theme_preview_var = tk.StringVar()
        ttk.Label(appearance_tab, textvariable=self.theme_preview_var, wraplength=680, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(14, 0)
        )

        def _refresh_theme_preview(_event=None) -> None:
            theme_id = normalize_theme_id(self._theme_label_to_value.get(self.theme_var.get()))
            theme = get_theme(theme_id)
            self.theme_preview_var.set(
                f"主色 {theme.primary}；强调色 {theme.accent}；背景 {theme.background}；"
                f"面板 {theme.panel}；按钮 {theme.button}；选中 {theme.selection}。"
            )

        theme_box.bind("<<ComboboxSelected>>", _refresh_theme_preview)
        _refresh_theme_preview()

        buttons = ttk.Frame(outer)
        buttons.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(buttons, textvariable=self._size_notice_var).pack(side="left")
        ttk.Button(buttons, text="取消", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="保存设置", command=self._confirm).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        bind_minimum_size_notice(self, self._size_notice_var, 760, 560)
        center_window(self, 820, 620)

    def _current_prefixes(self) -> list[str]:
        values = [self.prefix_list.get(index) for index in range(self.prefix_list.size())]
        return normalize_scan_ignore_prefixes(values)

    def _refresh_prefix_list(self, prefixes: list[str], *, select_value: str | None = None) -> None:
        self.prefix_list.delete(0, "end")
        for prefix in normalize_scan_ignore_prefixes(prefixes):
            self.prefix_list.insert("end", prefix)
        if select_value is not None:
            for index in range(self.prefix_list.size()):
                if self.prefix_list.get(index).casefold() == select_value.casefold():
                    self.prefix_list.selection_clear(0, "end")
                    self.prefix_list.selection_set(index)
                    self.prefix_list.see(index)
                    break

    def _add_prefix(self) -> None:
        raw_value = self.prefix_var.get().strip()
        if not raw_value:
            return
        prefixes = self._current_prefixes()
        merged = normalize_scan_ignore_prefixes(prefixes + [raw_value])
        self._refresh_prefix_list(merged, select_value=raw_value)
        self.prefix_var.set("")

    def _remove_selected(self) -> None:
        selection = self.prefix_list.curselection()
        if not selection:
            return
        remove_indexes = set(selection)
        prefixes = [self.prefix_list.get(index) for index in range(self.prefix_list.size()) if index not in remove_indexes]
        self._refresh_prefix_list(prefixes)

    def _restore_defaults(self) -> None:
        self._refresh_prefix_list(list(DEFAULT_SCAN_IGNORE_PREFIXES), select_value=DEFAULT_SCAN_IGNORE_PREFIXES[0])

    def _confirm(self) -> None:
        prefixes = self._current_prefixes()
        if not prefixes:
            messagebox.showwarning("提示", "至少需要保留一个目录忽略前缀。", parent=self)
            return

        scan_mode = normalize_default_scan_mode(self._scan_mode_label_to_value.get(self.scan_mode_var.get()))
        summary_filter = normalize_repair_summary_filter(self._summary_filter_label_to_value.get(self.summary_filter_var.get()))
        concurrency_mode = normalize_analysis_concurrency_mode(self._concurrency_label_to_value.get(self.concurrency_var.get()))
        custom_workers = normalize_analysis_custom_workers(self.custom_workers_var.get())
        gpu_mode = normalize_gpu_acceleration_mode(self._gpu_label_to_value.get(self.gpu_mode_var.get()))
        console_time_mode = normalize_console_time_mode(self._console_time_label_to_value.get(self.console_time_var.get()))
        theme_id = normalize_theme_id(self._theme_label_to_value.get(self.theme_var.get()))
        self.result = AppSettings(
            scan_ignore_prefixes=prefixes,
            default_scan_mode=scan_mode,
            repair_summary_default_filter=summary_filter,
            analysis_concurrency_mode=concurrency_mode,
            analysis_custom_workers=custom_workers,
            gpu_acceleration_mode=gpu_mode,
            console_time_mode=console_time_mode,
            theme_id=theme_id,
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def show_app_settings_dialog(parent: tk.Widget, settings: AppSettings) -> AppSettings | None:
    dialog = AppSettingsDialog(parent, settings)
    dialog.wait_window()
    return dialog.result
