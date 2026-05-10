from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app_metadata import APP_BUILD_ID, APP_NAME, APP_VERSION, APP_VERSION_ID
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
from developer_mode import developer_session
from gpu_accel import detect_gpu_backend
from ui.themes import THEME_OPTIONS, normalize_theme_id
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


class AppSettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, settings: AppSettings, update_check_callback=None) -> None:
        super().__init__(parent)
        self._update_check_callback = update_check_callback
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

        backend_status = detect_gpu_backend()
        backend_label = backend_status.backend_name if backend_status.available else "未检测到"
        ttk.Label(performance_tab, text="加速状态：").grid(row=7, column=0, sticky="w", pady=(12, 0))
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
        ttk.Label(
            appearance_tab,
            text="这里只显示配色名称。具体颜色细节不在用户设置页公开。",
            wraplength=680,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(14, 0))

        update_tab = ttk.Frame(notebook, padding=14)
        update_tab.columnconfigure(1, weight=1)
        notebook.add(update_tab, text="更新")
        ttk.Label(update_tab, text="当前版本", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            update_tab,
            text=f"{APP_NAME} v{APP_VERSION}    version_id={APP_VERSION_ID}    build_id={APP_BUILD_ID}",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        ttk.Button(update_tab, text="检查更新", command=self._check_updates_now).grid(row=2, column=0, sticky="w")
        ttk.Label(update_tab, text="自动检查更新", font=("Microsoft YaHei UI", 11, "bold")).grid(row=3, column=0, columnspan=2, sticky="w", pady=(22, 0))
        self.auto_update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(update_tab, text="启动后自动检查更新", variable=self.auto_update_var, state="disabled").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 12)
        )
        ttk.Label(update_tab, text="更新地址由 Shape Your Photo 自动管理。", wraplength=680, justify="left").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

        message_tab = ttk.Frame(notebook, padding=14)
        message_tab.columnconfigure(1, weight=1)
        notebook.add(message_tab, text="公告")
        ttk.Label(message_tab, text="云端公告", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            message_tab,
            text="启动后自动查询重要提示。网络失败时不会打扰你。",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        ttk.Label(message_tab, text="公告地址由 Shape Your Photo 自动管理。").grid(row=2, column=0, columnspan=2, sticky="w")

        developer_tab = ttk.Frame(notebook, padding=14)
        developer_tab.columnconfigure(1, weight=1)
        notebook.add(developer_tab, text="开发者模式")
        ttk.Label(developer_tab, text="高级开发者能力", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        self.developer_status_var = tk.StringVar(value="已解锁（本次运行有效）" if developer_session.unlocked else "未解锁")
        ttk.Label(developer_tab, textvariable=self.developer_status_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        ttk.Label(developer_tab, text="开发者密码：").grid(row=2, column=0, sticky="w")
        self.developer_password_var = tk.StringVar()
        ttk.Entry(developer_tab, textvariable=self.developer_password_var, show="*").grid(row=2, column=1, sticky="ew")
        ttk.Button(developer_tab, text="本次运行解锁", command=self._unlock_developer_mode).grid(row=3, column=1, sticky="w", pady=(10, 0))
        ttk.Label(
            developer_tab,
            text="仅用于本机调试和高级维护。本次运行有效，重启后会自动关闭。",
            wraplength=680,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(16, 0))

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
            auto_check_updates=True,
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _unlock_developer_mode(self) -> None:
        ok, message = developer_session.unlock(self.developer_password_var.get())
        if ok:
            self.developer_password_var.set("")
            self.developer_status_var.set("已解锁（本次运行有效）")
            messagebox.showinfo("开发者模式", message, parent=self)
        else:
            self.developer_status_var.set("未解锁")
            messagebox.showwarning("开发者模式", message, parent=self)

    def _check_updates_now(self) -> None:
        if self._update_check_callback is None:
            messagebox.showinfo("检查更新", "当前无法从设置窗口发起检查。", parent=self)
            return
        self._update_check_callback()


def show_app_settings_dialog(parent: tk.Widget, settings: AppSettings, update_check_callback=None) -> AppSettings | None:
    dialog = AppSettingsDialog(parent, settings, update_check_callback=update_check_callback)
    dialog.wait_window()
    return dialog.result
