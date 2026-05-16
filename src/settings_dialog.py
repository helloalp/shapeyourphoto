from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from app_metadata import APP_NAME, APP_VERSION, APP_VERSION_ID
from app_settings import (
    ANALYSIS_CONCURRENCY_OPTIONS,
    AppSettings,
    CONSOLE_TIME_MODE_OPTIONS,
    DEFAULT_SCAN_IGNORE_PREFIXES,
    DEFAULT_SCAN_IGNORE_SUFFIXES,
    DEFAULT_SCAN_IGNORE_CONTAINS,
    GPU_ACCELERATION_OPTIONS,
    REPAIR_SUMMARY_FILTER_OPTIONS,
    SCAN_MODE_OPTIONS,
    UI_DENSITY_OPTIONS,
    normalize_analysis_concurrency_mode,
    normalize_analysis_custom_workers,
    normalize_default_scan_mode,
    normalize_gpu_acceleration_mode,
    normalize_console_time_mode,
    normalize_repair_summary_filter,
    normalize_scan_ignore_prefixes,
    normalize_scan_ignore_suffixes,
    normalize_scan_ignore_contains,
    normalize_ui_density,
    validate_settings_payload,
)
from cloud_client import fetch_cloud_messages
from gpu_accel import detect_gpu_backend
from ui.language import LANGUAGE_OPTIONS, language_label, normalize_language, set_current_language
from ui.themes import THEME_OPTIONS, normalize_theme_id
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


class AppSettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, settings: AppSettings, update_check_callback=None, log_callback=None) -> None:
        super().__init__(parent)
        self._update_check_callback = update_check_callback
        self._log_callback = log_callback
        self.title(app_window_title("应用设置"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(760, 560)
        self.result: AppSettings | None = None
        self._size_notice_var = tk.StringVar(value="")
        self._initial_language = settings.language

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
        self._density_value_to_label = dict(UI_DENSITY_OPTIONS)
        self._density_label_to_value = {label: value for value, label in UI_DENSITY_OPTIONS}
        self._language_value_to_label = dict(LANGUAGE_OPTIONS)
        self._language_label_to_value = {label: value for value, label in LANGUAGE_OPTIONS}

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="应用设置", font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")

        notebook = ttk.Notebook(outer)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(12, 0))

        scan_tab = ttk.Frame(notebook, padding=14)
        scan_tab.columnconfigure(0, weight=1)
        scan_tab.rowconfigure(2, weight=1)
        notebook.add(scan_tab, text="扫描")

        ttk.Label(scan_tab, text="扫描忽略规则", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            scan_tab,
            text="这些规则只作用于文件夹名称。命中的文件夹和里面的图片会被跳过；_repair 会始终保留，避免修复输出被重新扫入。",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 10))

        rule_book = ttk.Notebook(scan_tab)
        rule_book.grid(row=2, column=0, sticky="nsew")
        self._scan_rule_widgets: dict[str, tuple[tk.Listbox, tk.StringVar]] = {}
        self._build_scan_rule_page(
            rule_book,
            key="prefix",
            title="前缀",
            description="文件夹名称以规则开头时跳过，例如 _repair、_old。",
            values=normalized.scan_ignore_prefixes,
        )
        self._build_scan_rule_page(
            rule_book,
            key="suffix",
            title="后缀",
            description="文件夹名称以规则结尾时跳过，例如 _backup、_old。",
            values=normalized.scan_ignore_suffixes,
        )
        self._build_scan_rule_page(
            rule_book,
            key="contains",
            title="包含",
            description="文件夹名称中包含规则文字时跳过。请谨慎添加，避免误跳过正常相册。",
            values=normalized.scan_ignore_contains,
        )

        behavior_tab = ttk.Frame(notebook, padding=14)
        behavior_tab.columnconfigure(1, weight=1)
        notebook.add(behavior_tab, text="行为偏好")

        ttk.Label(behavior_tab, text="默认扫描行为", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            behavior_tab,
            text="当文件夹包含子文件夹时，可以选择每次询问，或使用固定扫描模式。",
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
            text="这些选项只影响之后的新任务，不会改动已经完成的分析结果。",
            wraplength=680,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(18, 0))

        performance_tab = ttk.Frame(notebook, padding=14)
        performance_tab.columnconfigure(1, weight=1)
        notebook.add(performance_tab, text="性能")

        ttk.Label(performance_tab, text="分析并发", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            performance_tab,
            text="控制同时分析图片的数量。通常保持自动即可；如果电脑变卡，可以调低。",
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

        ttk.Label(performance_tab, text="同时处理数量：").grid(row=3, column=0, sticky="w", pady=(12, 0))
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
            text="有可用加速能力时可以尝试开启；没有检测到时会自动使用 CPU。",
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

        self.gpu_hardware_var = tk.StringVar(value="正在检测...")
        self.gpu_backend_var = tk.StringVar(value="正在检测...")
        self.gpu_reason_var = tk.StringVar(value="正在后台检测 GPU 硬件和可用后端，设置窗口可以继续使用。")
        ttk.Label(performance_tab, text="硬件状态：").grid(row=7, column=0, sticky="w", pady=(12, 0))
        ttk.Label(performance_tab, textvariable=self.gpu_hardware_var).grid(row=7, column=1, sticky="w", pady=(12, 0))
        ttk.Label(performance_tab, text="加速状态：").grid(row=8, column=0, sticky="w", pady=(8, 0))
        ttk.Label(performance_tab, textvariable=self.gpu_backend_var).grid(row=8, column=1, sticky="w", pady=(8, 0))
        ttk.Label(
            performance_tab,
            textvariable=self.gpu_reason_var,
            wraplength=680,
            justify="left",
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._start_gpu_status_refresh()

        console_tab = ttk.Frame(notebook, padding=14)
        console_tab.columnconfigure(1, weight=1)
        notebook.add(console_tab, text="Console")
        ttk.Label(console_tab, text="Console 时间显示", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            console_tab,
            text="选择 Console 新日志的时间显示方式。",
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
            text="跨时区沟通或排查问题时，可以选择带时区的时间格式。",
            wraplength=680,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(14, 0))

        appearance_tab = ttk.Frame(notebook, padding=14)
        appearance_tab.columnconfigure(1, weight=1)
        notebook.add(appearance_tab, text="外观 / 风格")
        ttk.Label(appearance_tab, text="应用风格", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            appearance_tab,
            text="选择你喜欢的界面配色。",
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
        ttk.Label(appearance_tab, text="界面清晰度 / 密度：").grid(row=3, column=0, sticky="w", pady=(14, 0))
        self.density_var = tk.StringVar(value=self._density_value_to_label[normalized.ui_density])
        ttk.Combobox(
            appearance_tab,
            textvariable=self.density_var,
            state="readonly",
            values=[label for _value, label in UI_DENSITY_OPTIONS],
            width=28,
        ).grid(row=3, column=1, sticky="w", pady=(14, 0))
        ttk.Label(
            appearance_tab,
            text="高清细节会略微提高字体、行高和按钮留白，适合 2K/4K 或高缩放屏幕。",
            wraplength=680,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
        language_tab = ttk.Frame(notebook, padding=14)
        language_tab.columnconfigure(1, weight=1)
        notebook.add(language_tab, text="语言")
        ttk.Label(language_tab, text="界面语言", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(language_tab, text="语言：").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.language_var = tk.StringVar(value=language_label(normalized.language))
        ttk.Combobox(
            language_tab,
            textvariable=self.language_var,
            state="readonly",
            values=[label for _value, label in LANGUAGE_OPTIONS],
            width=28,
        ).grid(row=1, column=1, sticky="w", pady=(12, 0))

        update_tab = ttk.Frame(notebook, padding=14)
        update_tab.columnconfigure(1, weight=1)
        notebook.add(update_tab, text="更新")
        ttk.Label(update_tab, text="当前版本", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            update_tab,
            text=f"{APP_NAME} v{APP_VERSION}\n版本ID {APP_VERSION_ID}",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        ttk.Button(update_tab, text="检查更新", command=self._check_updates_now).grid(row=2, column=0, sticky="w")
        ttk.Label(update_tab, text="可以随时手动检查是否有新版本。", wraplength=680, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(14, 0)
        )

        message_tab = ttk.Frame(notebook, padding=14)
        message_tab.columnconfigure(1, weight=1)
        message_tab.rowconfigure(2, weight=1)
        notebook.add(message_tab, text="公告")
        ttk.Label(message_tab, text="公告", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(message_tab, text="刷新公告", command=self._refresh_announcements_now).grid(row=0, column=1, sticky="e")
        self.announcement_status_var = tk.StringVar(value="暂无公告。")
        ttk.Label(message_tab, textvariable=self.announcement_status_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 8))
        message_frame = ttk.Frame(message_tab)
        message_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        message_frame.columnconfigure(0, weight=1)
        message_frame.rowconfigure(0, weight=1)
        self.announcement_text = tk.Text(
            message_frame,
            height=10,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
            bg="#f8fbf8",
            relief="flat",
            padx=10,
            pady=10,
        )
        announcement_scroll = ttk.Scrollbar(message_frame, orient="vertical", command=self.announcement_text.yview)
        self.announcement_text.configure(yscrollcommand=announcement_scroll.set)
        self.announcement_text.grid(row=0, column=0, sticky="nsew")
        announcement_scroll.grid(row=0, column=1, sticky="ns")
        self._set_announcement_text("暂无公告。")

        buttons = ttk.Frame(outer)
        buttons.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(buttons, textvariable=self._size_notice_var).pack(side="left")
        ttk.Button(buttons, text="取消", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="保存设置", command=self._confirm).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        bind_minimum_size_notice(self, self._size_notice_var, 760, 560)
        center_window(self, 820, 620)

    def _normalize_rule_values(self, key: str, values: list[str]) -> list[str]:
        if key == "prefix":
            return normalize_scan_ignore_prefixes(values)
        if key == "suffix":
            return normalize_scan_ignore_suffixes(values)
        return normalize_scan_ignore_contains(values)

    def _build_scan_rule_page(
        self,
        notebook: ttk.Notebook,
        *,
        key: str,
        title: str,
        description: str,
        values: list[str],
    ) -> None:
        page = ttk.Frame(notebook, padding=12)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)
        notebook.add(page, text=title)
        ttk.Label(page, text=description, wraplength=640, justify="left").grid(row=0, column=0, sticky="w")

        add_row = ttk.Frame(page)
        add_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        add_row.columnconfigure(0, weight=1)
        value_var = tk.StringVar()
        entry = ttk.Entry(add_row, textvariable=value_var)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", lambda _event, k=key: self._add_rule(k))
        ttk.Button(add_row, text=f"添加{title}", command=lambda k=key: self._add_rule(k)).grid(row=0, column=1, padx=(8, 0))

        hint = "列表支持按 Ctrl 或 Shift 多选后一次删除。"
        ttk.Label(page, text=hint).grid(row=2, column=0, sticky="w", pady=(8, 0))

        list_frame = ttk.Frame(page)
        list_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        listbox = tk.Listbox(
            list_frame,
            activestyle="none",
            font=("Consolas", 11),
            exportselection=False,
            selectmode="extended",
        )
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scroll.set)
        listbox.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self._scan_rule_widgets[key] = (listbox, value_var)
        self._refresh_rule_list(key, values)

        actions = ttk.Frame(page)
        actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="删除选中", command=lambda k=key: self._remove_selected_rules(k)).pack(side="left")
        ttk.Button(actions, text="恢复默认", command=lambda k=key: self._restore_default_rules(k)).pack(side="left", padx=(8, 0))

    def _current_rules(self, key: str) -> list[str]:
        listbox, _value_var = self._scan_rule_widgets[key]
        values = [listbox.get(index).split(". ", 1)[-1] for index in range(listbox.size())]
        return self._normalize_rule_values(key, values)

    def _refresh_rule_list(self, key: str, values: list[str], *, select_value: str | None = None) -> None:
        listbox, _value_var = self._scan_rule_widgets[key]
        normalized_values = self._normalize_rule_values(key, values)
        listbox.delete(0, "end")
        for index, value in enumerate(normalized_values, start=1):
            listbox.insert("end", f"{index}. {value}")
        if select_value is not None:
            for index in range(listbox.size()):
                if listbox.get(index).split(". ", 1)[-1].casefold() == select_value.casefold():
                    listbox.selection_clear(0, "end")
                    listbox.selection_set(index)
                    listbox.see(index)
                    break

    def _add_rule(self, key: str) -> None:
        _listbox, value_var = self._scan_rule_widgets[key]
        raw_value = value_var.get().strip()
        if not raw_value:
            return
        merged = self._current_rules(key) + [raw_value]
        self._refresh_rule_list(key, merged, select_value=raw_value)
        value_var.set("")

    def _remove_selected_rules(self, key: str) -> None:
        listbox, _value_var = self._scan_rule_widgets[key]
        selection = set(listbox.curselection())
        if not selection:
            return
        values = [
            listbox.get(index).split(". ", 1)[-1]
            for index in range(listbox.size())
            if index not in selection
        ]
        self._refresh_rule_list(key, values)

    def _restore_default_rules(self, key: str) -> None:
        defaults = {
            "prefix": list(DEFAULT_SCAN_IGNORE_PREFIXES),
            "suffix": list(DEFAULT_SCAN_IGNORE_SUFFIXES),
            "contains": list(DEFAULT_SCAN_IGNORE_CONTAINS),
        }[key]
        self._refresh_rule_list(key, defaults, select_value=defaults[0] if defaults else None)

    def _current_prefixes(self) -> list[str]:
        return self._current_rules("prefix")

    def _current_suffixes(self) -> list[str]:
        return self._current_rules("suffix")

    def _current_contains(self) -> list[str]:
        return self._current_rules("contains")

    def _refresh_prefix_list(self, prefixes: list[str], *, select_value: str | None = None) -> None:
        self._refresh_rule_list("prefix", prefixes, select_value=select_value)

    def _add_prefix(self) -> None:
        self._add_rule("prefix")

    def _remove_selected(self) -> None:
        self._remove_selected_rules("prefix")

    def _restore_defaults(self) -> None:
        self._refresh_prefix_list(list(DEFAULT_SCAN_IGNORE_PREFIXES), select_value=DEFAULT_SCAN_IGNORE_PREFIXES[0])

    def _start_gpu_status_refresh(self) -> None:
        def _worker() -> None:
            status = detect_gpu_backend()

            def _finish() -> None:
                if not self.winfo_exists():
                    return
                hardware = status.hardware_name if status.hardware_detected else "未检测到 GPU 硬件"
                if status.driver_version:
                    hardware = f"{hardware}（驱动 {status.driver_version}）"
                backend = status.backend_name if status.available else "未检测到可用后端"
                self.gpu_hardware_var.set(hardware)
                self.gpu_backend_var.set(backend)
                self.gpu_reason_var.set(status.reason)

            self.after(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()

    def _confirm(self) -> None:
        prefixes = self._current_prefixes()
        suffixes = self._current_suffixes()
        contains = self._current_contains()
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
        ui_density = normalize_ui_density(self._density_label_to_value.get(self.density_var.get()))
        language = normalize_language(self._language_label_to_value.get(self.language_var.get()))
        self.result = AppSettings(
            scan_ignore_prefixes=prefixes,
            scan_ignore_suffixes=suffixes,
            scan_ignore_contains=contains,
            default_scan_mode=scan_mode,
            repair_summary_default_filter=summary_filter,
            analysis_concurrency_mode=concurrency_mode,
            analysis_custom_workers=custom_workers,
            gpu_acceleration_mode=gpu_mode,
            console_time_mode=console_time_mode,
            theme_id=theme_id,
            ui_density=ui_density,
            language=language,
            auto_check_updates=True,
        )
        if language != self._initial_language:
            set_current_language(language)
            messagebox.showinfo("语言设置", "界面语言已更改。部分文案可能需要重启应用后才会完全生效。", parent=self)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _check_updates_now(self) -> None:
        if self._update_check_callback is None:
            messagebox.showinfo("检查更新", "当前无法从设置窗口发起检查。", parent=self)
            return
        try:
            self._update_check_callback(self)
        except TypeError:
            self._update_check_callback()

    def _log(self, message: str) -> None:
        if self._log_callback is not None:
            try:
                self._log_callback(message)
            except Exception:
                pass

    def _set_announcement_text(self, text: str) -> None:
        self.announcement_text.config(state="normal")
        self.announcement_text.delete("1.0", "end")
        self.announcement_text.insert("1.0", text)
        self.announcement_text.config(state="disabled")

    def _refresh_announcements_now(self) -> None:
        self.announcement_status_var.set("正在刷新公告...")
        self._set_announcement_text("正在获取公告。")
        self._log("cloud message manual refresh requested from settings")

        def _worker() -> None:
            result = fetch_cloud_messages("")

            def _finish() -> None:
                if not self.winfo_exists():
                    return
                if not result.ok or result.payload is None:
                    self.announcement_status_var.set("暂时没有获取到公告。")
                    self._set_announcement_text("稍后可以再试一次。")
                    self._log(f"cloud message manual refresh failed: {result.error}")
                    return
                messages = result.payload.get("messages", [])
                if isinstance(messages, dict):
                    messages = [messages]
                if not isinstance(messages, list):
                    messages = []
                enabled_messages = [item for item in messages if isinstance(item, dict) and item.get("enabled", True)]
                if not enabled_messages:
                    self.announcement_status_var.set("暂无公告。")
                    self._set_announcement_text("暂无公告。")
                    self._log("cloud message manual refresh completed: empty")
                    return
                lines: list[str] = []
                for item in enabled_messages[:5]:
                    title = str(item.get("title") or "公告")
                    body = str(item.get("body") or "").strip()
                    lines.append(title)
                    if body:
                        lines.append(body)
                    lines.append("")
                self.announcement_status_var.set(f"已获取 {len(enabled_messages)} 条公告。")
                self._set_announcement_text("\n".join(lines).strip())
                self._log(f"cloud message manual refresh completed: count={len(enabled_messages)}")

            self.after(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()


def show_app_settings_dialog(parent: tk.Widget, settings: AppSettings, update_check_callback=None, log_callback=None) -> AppSettings | None:
    dialog = AppSettingsDialog(parent, settings, update_check_callback=update_check_callback, log_callback=log_callback)
    dialog.wait_window()
    return dialog.result
