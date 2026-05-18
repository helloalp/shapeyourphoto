from __future__ import annotations

import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk

from app_metadata import APP_NAME, APP_VERSION, APP_VERSION_ID
from app_settings import (
    ANALYSIS_CONCURRENCY_OPTIONS,
    ANALYSIS_CONCURRENCY_CUSTOM,
    AppSettings,
    CONSOLE_TIME_MODE_OPTIONS,
    DEFAULT_SCAN_IGNORE_CONTAINS,
    DEFAULT_SCAN_IGNORE_PREFIXES,
    DEFAULT_SCAN_IGNORE_SUFFIXES,
    GPU_ACCELERATION_OPTIONS,
    REPAIR_SUMMARY_FILTER_OPTIONS,
    SCAN_MODE_OPTIONS,
    UI_DENSITY_OPTIONS,
    max_analysis_workers,
    normalize_analysis_concurrency_mode,
    normalize_analysis_custom_workers,
    normalize_console_time_mode,
    normalize_default_scan_mode,
    normalize_gpu_acceleration_mode,
    normalize_repair_summary_filter,
    normalize_scan_ignore_contains,
    normalize_scan_ignore_prefixes,
    normalize_scan_ignore_suffixes,
    normalize_ui_density,
    resolve_analysis_worker_plan,
    validate_settings_payload,
)
from cloud_client import fetch_cloud_messages
from gpu_accel import detect_gpu_backend
from ui.language import LANGUAGE_OPTIONS, language_label, normalize_language, set_current_language, tr
from ui.themes import THEME_OPTIONS, normalize_theme_id
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


THEME_LABEL_KEYS = {
    "classic_green": {"zh_CN": "经典清绿", "en_US": "Classic Green", "ja_JP": "クラシックグリーン"},
    "graphite": {"zh_CN": "石墨灰", "en_US": "Graphite", "ja_JP": "グラファイト"},
    "studio_blue": {"zh_CN": "影像蓝", "en_US": "Studio Blue", "ja_JP": "スタジオブルー"},
    "warm_paper": {"zh_CN": "暖白纸", "en_US": "Warm Paper", "ja_JP": "ウォームペーパー"},
    "high_contrast": {"zh_CN": "高对比", "en_US": "High Contrast", "ja_JP": "高コントラスト"},
    "forest_mist": {"zh_CN": "森林薄雾", "en_US": "Forest Mist", "ja_JP": "森の薄霧"},
    "clear_sky": {"zh_CN": "晴空", "en_US": "Clear Sky", "ja_JP": "晴れ空"},
    "rose_gray": {"zh_CN": "玫瑰灰", "en_US": "Rose Gray", "ja_JP": "ローズグレー"},
}


class ScrollablePage(ttk.Frame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid(row=0, column=1, sticky="ns")
        self.content = ttk.Frame(self.canvas, padding=14)
        self.content.columnconfigure(1, weight=1)
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._sync_scroll)
        self.canvas.bind("<Configure>", self._fit_width)

    def _sync_scroll(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _fit_width(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=max(360, event.width))


class AppSettingsDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        settings: AppSettings,
        update_check_callback=None,
        log_callback=None,
        apply_callback=None,
        initial_tab: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._update_check_callback = update_check_callback
        self._log_callback = log_callback
        self._apply_callback = apply_callback
        self._initial_tab = initial_tab or ""
        self.title(app_window_title(tr("settings.app")))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(820, 620)
        self.result: AppSettings | None = None
        self._size_notice_var = tk.StringVar(value="")
        self._save_status_var = tk.StringVar(value="")
        self._initial_language = settings.language
        self._text_widgets: list[tuple[tk.Widget, str]] = []
        self._settings_tabs: list[tuple[tk.Widget, str, str]] = []
        self._notebook_tab_labels: list[tuple[ttk.Notebook, tk.Widget, str]] = []
        self._option_boxes: list[tuple[ttk.Combobox, tk.StringVar, str, list[str]]] = []
        self._last_gpu_status = None
        self._status_after_id: str | None = None
        self._status_kind = ""

        normalized = validate_settings_payload(settings.__dict__)
        self._scan_rule_widgets: dict[str, tuple[tk.Listbox, tk.StringVar, ttk.Button]] = {}
        self._option_vars: dict[str, tk.StringVar] = {}

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        self.header_label = ttk.Label(outer, text=tr("settings.app"), font=("Microsoft YaHei UI", 12, "bold"))
        self.header_label.grid(row=0, column=0, sticky="w")
        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self._clear_temporary_status(), add="+")

        self._build_scan_tab(normalized)
        self._build_behavior_tab(normalized)
        self._build_performance_tab(normalized)
        self._build_console_tab(normalized)
        self._build_appearance_tab(normalized)
        self._build_language_tab(normalized)
        self._build_update_tab()
        self._build_announcements_tab()

        buttons = ttk.Frame(outer)
        buttons.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        buttons.configure(height=52)
        buttons.grid_propagate(False)
        buttons.columnconfigure(1, weight=1)
        ttk.Label(buttons, textvariable=self._size_notice_var).grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(buttons, textvariable=self._save_status_var, anchor="e", justify="right", wraplength=480)
        self.status_label.grid(row=0, column=1, sticky="ew", padx=(12, 10))
        buttons.bind("<Configure>", self._sync_footer_status_wrap, add="+")
        self.save_button = ttk.Button(buttons, text=tr("settings.save"), command=self._confirm)
        self.save_button.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.cancel_button = ttk.Button(buttons, text=tr("settings.cancel"), command=self._cancel)
        self.cancel_button.grid(row=0, column=3, sticky="e")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        bind_minimum_size_notice(self, self._size_notice_var, 820, 620)
        center_window(self, 900, 700)
        self._refresh_option_labels()
        self._update_concurrency_hint()
        self._select_initial_tab()
        self._start_gpu_status_refresh(force_refresh=False)

    def _sync_footer_status_wrap(self, event=None) -> None:
        width = 480
        if event is not None:
            width = max(180, event.width - 260)
        self.status_label.configure(wraplength=width)

    def _tr_widget(self, widget: tk.Widget, key: str) -> tk.Widget:
        self._text_widgets.append((widget, key))
        return widget

    def _label(self, parent: tk.Widget, key: str, *, row: int, column: int = 0, columnspan: int = 1, bold: bool = False, pady=0, wrap: bool = False) -> ttk.Label:
        label = ttk.Label(
            parent,
            text=tr(key),
            font=("Microsoft YaHei UI", 11, "bold") if bold else None,
            wraplength=700 if wrap else 0,
            justify="left",
        )
        label.grid(row=row, column=column, columnspan=columnspan, sticky="w", pady=pady)
        self._tr_widget(label, key)
        return label

    def _make_page(self, tab_key: str, tab_id: str) -> ScrollablePage:
        page = ScrollablePage(self.notebook)
        self.notebook.add(page, text=tr(tab_key))
        self._settings_tabs.append((page, tab_key, tab_id))
        self._notebook_tab_labels.append((self.notebook, page, tab_key))
        return page

    def _build_scan_tab(self, settings: AppSettings) -> None:
        page = self._make_page("settings.tab.scan", "scan")
        c = page.content
        self._label(c, "settings.section.scan_rules", row=0, bold=True)
        self._label(c, "settings.desc.scan_rules", row=1, columnspan=2, wrap=True, pady=(8, 10))
        rule_book = ttk.Notebook(c)
        rule_book.grid(row=2, column=0, columnspan=2, sticky="nsew")
        c.rowconfigure(2, weight=1)
        for key, values in (
            ("prefix", settings.scan_ignore_prefixes),
            ("suffix", settings.scan_ignore_suffixes),
            ("contains", settings.scan_ignore_contains),
        ):
            self._build_scan_rule_page(rule_book, key, values)

    def _build_scan_rule_page(self, notebook: ttk.Notebook, key: str, values: list[str]) -> None:
        page = ttk.Frame(notebook, padding=12)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)
        notebook.add(page, text=tr(f"settings.rule.{key}"))
        self._notebook_tab_labels.append((notebook, page, f"settings.rule.{key}"))
        self._label(page, f"settings.rule.{key}_desc", row=0, wrap=True)
        add_row = ttk.Frame(page)
        add_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        add_row.columnconfigure(0, weight=1)
        value_var = tk.StringVar()
        entry = ttk.Entry(add_row, textvariable=value_var)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", lambda _event, k=key: self._add_rule(k))
        add_button = ttk.Button(add_row, text=f"{tr('settings.rule.add')} {tr(f'settings.rule.{key}')}", command=lambda k=key: self._add_rule(k))
        add_button.grid(row=0, column=1, padx=(8, 0))
        self._label(page, "settings.rule.multi_hint", row=2, pady=(8, 0))
        list_frame = ttk.Frame(page)
        list_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        listbox = tk.Listbox(list_frame, activestyle="none", font=("Consolas", 11), exportselection=False, selectmode="extended")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scroll.set)
        listbox.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        actions = ttk.Frame(page)
        actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        remove_button = ttk.Button(actions, text=tr("settings.rule.remove"), command=lambda k=key: self._remove_selected_rules(k))
        remove_button.pack(side="left")
        restore_button = ttk.Button(actions, text=tr("settings.rule.restore"), command=lambda k=key: self._restore_default_rules(k))
        restore_button.pack(side="left", padx=(8, 0))
        self._tr_widget(remove_button, "settings.rule.remove")
        self._tr_widget(restore_button, "settings.rule.restore")
        self._scan_rule_widgets[key] = (listbox, value_var, add_button)
        self._refresh_rule_list(key, values)

    def _build_behavior_tab(self, settings: AppSettings) -> None:
        page = self._make_page("settings.tab.behavior", "behavior")
        c = page.content
        self._label(c, "settings.section.default_scan", row=0, bold=True)
        self._label(c, "settings.desc.default_scan", row=1, columnspan=2, wrap=True, pady=(8, 10))
        self._label(c, "settings.default_scan_mode", row=2)
        self.scan_mode_var = tk.StringVar(value=settings.default_scan_mode)
        self._option_combobox(c, self.scan_mode_var, "scan", [v for v, _ in SCAN_MODE_OPTIONS], row=2)
        self._label(c, "settings.repair_summary_filter", row=3, pady=(14, 0))
        self.summary_filter_var = tk.StringVar(value=settings.repair_summary_default_filter)
        self._option_combobox(c, self.summary_filter_var, "summary", [v for v, _ in REPAIR_SUMMARY_FILTER_OPTIONS], row=3, pady=(14, 0))
        self._label(c, "settings.desc.future_tasks", row=4, columnspan=2, wrap=True, pady=(18, 0))

    def _build_performance_tab(self, settings: AppSettings) -> None:
        page = self._make_page("settings.tab.performance", "performance")
        c = page.content
        self._label(c, "settings.section.concurrency", row=0, bold=True)
        self._label(c, "settings.desc.concurrency", row=1, columnspan=3, wrap=True, pady=(8, 10))
        self._label(c, "settings.concurrency_mode", row=2)
        self.concurrency_var = tk.StringVar(value=settings.analysis_concurrency_mode)
        box = self._option_combobox(c, self.concurrency_var, "worker", [v for v, _ in ANALYSIS_CONCURRENCY_OPTIONS], row=2)
        box.bind("<<ComboboxSelected>>", lambda _event: self._update_concurrency_hint(), add="+")
        self.concurrency_default_var = tk.StringVar(value="")
        ttk.Label(c, textvariable=self.concurrency_default_var).grid(row=2, column=2, sticky="w", padx=(12, 0))
        self._label(c, "settings.concurrent_workers", row=3, pady=(12, 0))
        self.custom_workers_var = tk.StringVar(value=str(settings.analysis_custom_workers or ""))
        worker_box = ttk.Frame(c)
        worker_box.grid(row=3, column=1, sticky="w", pady=(12, 0))
        self.custom_workers_spin = ttk.Spinbox(worker_box, from_=1, to=max_analysis_workers(), textvariable=self.custom_workers_var, width=8)
        self.custom_workers_spin.grid(row=0, column=0, sticky="w")
        self.worker_minus_button = ttk.Button(worker_box, text="-", width=3, command=lambda: self._step_custom_workers(-1))
        self.worker_minus_button.grid(row=0, column=1, padx=(8, 0), ipady=3)
        self.worker_plus_button = ttk.Button(worker_box, text="+", width=3, command=lambda: self._step_custom_workers(1))
        self.worker_plus_button.grid(row=0, column=2, padx=(4, 0), ipady=3)
        self.worker_range_var = tk.StringVar(value="")
        self.worker_range_label = ttk.Label(c, textvariable=self.worker_range_var)
        self.worker_range_label.grid(row=3, column=2, sticky="w", padx=(12, 0), pady=(12, 0))
        self._label(c, "settings.section.gpu", row=4, columnspan=3, bold=True, pady=(22, 0))
        self._label(c, "settings.desc.gpu", row=5, columnspan=3, wrap=True, pady=(8, 10))
        self._label(c, "settings.gpu_mode", row=6)
        self.gpu_mode_var = tk.StringVar(value=settings.gpu_acceleration_mode)
        self._option_combobox(c, self.gpu_mode_var, "gpu", [v for v, _ in GPU_ACCELERATION_OPTIONS], row=6)
        self._label(c, "settings.gpu_hardware", row=7, pady=(12, 0))
        self.gpu_hardware_var = tk.StringVar(value=tr("settings.gpu_detecting"))
        ttk.Label(c, textvariable=self.gpu_hardware_var).grid(row=7, column=1, columnspan=2, sticky="w", pady=(12, 0))
        self._label(c, "settings.gpu_backend", row=8, pady=(8, 0))
        self.gpu_backend_var = tk.StringVar(value=tr("settings.gpu_detecting"))
        ttk.Label(c, textvariable=self.gpu_backend_var).grid(row=8, column=1, columnspan=2, sticky="w", pady=(8, 0))
        self.gpu_reason_var = tk.StringVar(value=tr("settings.gpu_reason_detecting"))
        ttk.Label(c, textvariable=self.gpu_reason_var, wraplength=700, justify="left").grid(row=9, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.gpu_next_step_var = tk.StringVar(value="")
        ttk.Label(c, textvariable=self.gpu_next_step_var, wraplength=700, justify="left").grid(row=10, column=0, columnspan=3, sticky="w", pady=(6, 0))
        gpu_actions = ttk.Frame(c)
        gpu_actions.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        for key, command in (
            ("settings.gpu_check", lambda: self._start_gpu_status_refresh(force_refresh=True)),
            ("settings.gpu_prepare", self._open_gpu_prepare_help),
            ("settings.gpu_copy", self._copy_gpu_diagnostics),
            ("settings.gpu_help", self._open_gpu_help),
        ):
            button = ttk.Button(gpu_actions, text=tr(key), command=command)
            button.pack(side="left", padx=(0, 8))
            self._tr_widget(button, key)

    def _build_console_tab(self, settings: AppSettings) -> None:
        page = self._make_page("settings.tab.console", "console")
        c = page.content
        self._label(c, "settings.section.console", row=0, bold=True)
        self._label(c, "settings.desc.console", row=1, columnspan=2, wrap=True, pady=(8, 10))
        self._label(c, "settings.console_time", row=2)
        self.console_time_var = tk.StringVar(value=settings.console_time_mode)
        self._option_combobox(c, self.console_time_var, "console", [v for v, _ in CONSOLE_TIME_MODE_OPTIONS], row=2, width=34)
        self._label(c, "settings.desc.console_tz", row=3, columnspan=2, wrap=True, pady=(14, 0))

    def _build_appearance_tab(self, settings: AppSettings) -> None:
        page = self._make_page("settings.tab.appearance", "appearance")
        c = page.content
        self._label(c, "settings.section.appearance", row=0, bold=True)
        self._label(c, "settings.desc.appearance", row=1, columnspan=2, wrap=True, pady=(8, 10))
        self._label(c, "settings.theme", row=2)
        self.theme_var = tk.StringVar(value=settings.theme_id)
        self._option_combobox(c, self.theme_var, "theme", [v for v, _ in THEME_OPTIONS], row=2)
        self._label(c, "settings.density", row=3, pady=(14, 0))
        self.density_var = tk.StringVar(value=settings.ui_density)
        self._option_combobox(c, self.density_var, "density", [v for v, _ in UI_DENSITY_OPTIONS], row=3, pady=(14, 0))
        self._label(c, "settings.desc.density", row=4, columnspan=2, wrap=True, pady=(10, 0))

    def _build_language_tab(self, settings: AppSettings) -> None:
        page = self._make_page("settings.tab.language", "language")
        c = page.content
        self._label(c, "settings.section.language", row=0, bold=True)
        self._label(c, "settings.language", row=1, pady=(12, 0))
        self.language_var = tk.StringVar(value=settings.language)
        self._option_combobox(c, self.language_var, "language", [value for value, _ in LANGUAGE_OPTIONS], row=1, pady=(12, 0))

    def _build_update_tab(self) -> None:
        page = self._make_page("settings.tab.update", "update")
        c = page.content
        self._label(c, "settings.section.version", row=0, bold=True)
        self.version_var = tk.StringVar(value=f"{APP_NAME} v{APP_VERSION}\n{tr('settings.version_id').format(id=APP_VERSION_ID)}")
        ttk.Label(c, textvariable=self.version_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        self.update_button = ttk.Button(c, text=tr("settings.check_updates"), command=self._check_updates_now)
        self.update_button.grid(row=2, column=0, sticky="w")
        self._tr_widget(self.update_button, "settings.check_updates")
        self._label(c, "settings.desc.update", row=3, columnspan=2, wrap=True, pady=(14, 0))

    def _build_announcements_tab(self) -> None:
        page = self._make_page("settings.tab.announcements", "announcements")
        c = page.content
        c.rowconfigure(2, weight=1)
        self._label(c, "settings.section.announcements", row=0, bold=True)
        self.announcement_button = ttk.Button(c, text=tr("settings.refresh_announcements"), command=self._refresh_announcements_now)
        self.announcement_button.grid(row=0, column=1, sticky="e")
        self._tr_widget(self.announcement_button, "settings.refresh_announcements")
        self.announcement_status_var = tk.StringVar(value=tr("settings.no_announcements"))
        ttk.Label(c, textvariable=self.announcement_status_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 8))
        message_frame = ttk.Frame(c)
        message_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        message_frame.columnconfigure(0, weight=1)
        message_frame.rowconfigure(0, weight=1)
        self.announcement_text = tk.Text(message_frame, height=10, wrap="word", font=("Microsoft YaHei UI", 10), bg="#f8fbf8", relief="flat", padx=10, pady=10)
        announcement_scroll = ttk.Scrollbar(message_frame, orient="vertical", command=self.announcement_text.yview)
        self.announcement_text.configure(yscrollcommand=announcement_scroll.set)
        self.announcement_text.grid(row=0, column=0, sticky="nsew")
        announcement_scroll.grid(row=0, column=1, sticky="ns")
        self._set_announcement_text(tr("settings.no_announcements"))

    def _option_combobox(self, parent: tk.Widget, var: tk.StringVar, kind: str, values: list[str], *, row: int, width: int = 28, pady=0) -> ttk.Combobox:
        label_var = tk.StringVar()
        box = ttk.Combobox(parent, textvariable=label_var, state="readonly", width=width)
        box.grid(row=row, column=1, sticky="w", pady=pady)
        self._option_vars[kind] = var
        self._option_boxes.append((box, label_var, kind, values))

        def _selected(_event=None, b=box, lv=label_var, code_var=var, k=kind) -> None:
            reverse = getattr(b, "_label_to_code", {})
            code_var.set(reverse.get(lv.get(), code_var.get()))
            if k == "worker":
                self._update_concurrency_hint()

        box.bind("<<ComboboxSelected>>", _selected)
        return box

    def _option_label(self, kind: str, code: str) -> str:
        if kind == "language":
            return language_label(code)
        if kind == "theme":
            lang = normalize_language(self.language_var.get() if hasattr(self, "language_var") else None)
            labels = THEME_LABEL_KEYS.get(code)
            if labels:
                return labels.get(lang, labels.get("zh_CN", code))
            return code
        return tr(f"option.{kind}.{code}")

    def _refresh_option_labels(self) -> None:
        for box, label_var, kind, values in self._option_boxes:
            labels = [self._option_label(kind, value) for value in values]
            label_to_code = dict(zip(labels, values))
            code_to_label = dict(zip(values, labels))
            box.configure(values=labels)
            box._label_to_code = label_to_code  # type: ignore[attr-defined]
            code_var = self._option_vars[kind]
            label_var.set(code_to_label.get(code_var.get(), labels[0] if labels else ""))

    def _select_initial_tab(self) -> None:
        if not self._initial_tab:
            return
        for tab, _key, tab_id in self._settings_tabs:
            if tab_id == self._initial_tab:
                try:
                    self.notebook.select(tab)
                except tk.TclError:
                    pass
                return

    def _normalize_rule_values(self, key: str, values: list[str]) -> list[str]:
        if key == "prefix":
            return normalize_scan_ignore_prefixes(values)
        if key == "suffix":
            return normalize_scan_ignore_suffixes(values)
        return normalize_scan_ignore_contains(values)

    def _current_rules(self, key: str) -> list[str]:
        listbox, _value_var, _button = self._scan_rule_widgets[key]
        values = [listbox.get(index).split(". ", 1)[-1] for index in range(listbox.size())]
        return self._normalize_rule_values(key, values)

    def _refresh_rule_list(self, key: str, values: list[str], *, select_value: str | None = None) -> None:
        listbox, _value_var, _button = self._scan_rule_widgets[key]
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
        _listbox, value_var, _button = self._scan_rule_widgets[key]
        raw_value = value_var.get().strip()
        if not raw_value:
            return
        self._refresh_rule_list(key, self._current_rules(key) + [raw_value], select_value=raw_value)
        value_var.set("")

    def _remove_selected_rules(self, key: str) -> None:
        listbox, _value_var, _button = self._scan_rule_widgets[key]
        selection = set(listbox.curselection())
        if not selection:
            return
        values = [listbox.get(index).split(". ", 1)[-1] for index in range(listbox.size()) if index not in selection]
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

    def _update_concurrency_hint(self) -> None:
        if not hasattr(self, "concurrency_var"):
            return
        limit = max_analysis_workers()
        mode = normalize_analysis_concurrency_mode(self.concurrency_var.get())
        custom_value = self.custom_workers_var.get() if hasattr(self, "custom_workers_var") else 0
        plan = resolve_analysis_worker_plan(9999, mode, custom_value)
        self.concurrency_default_var.set(tr("settings.default_workers").format(count=plan.requested_workers))
        is_custom = mode == ANALYSIS_CONCURRENCY_CUSTOM
        self.worker_range_var.set(
            tr("settings.worker_range").format(max=limit)
            if is_custom
            else tr("settings.worker_locked")
        )
        if hasattr(self, "custom_workers_spin"):
            self.custom_workers_spin.configure(to=limit, state="normal" if is_custom else "disabled")
        for button_name in ("worker_minus_button", "worker_plus_button"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.configure(state="normal" if is_custom else "disabled")
        if hasattr(self, "worker_range_label"):
            self.worker_range_label.configure(foreground="#666666" if not is_custom else "#1f3527")
        if not is_custom:
            self.custom_workers_var.set("")
            return
        current = normalize_analysis_custom_workers(custom_value)
        if current <= 0:
            self.custom_workers_var.set(str(min(limit, max(1, plan.requested_workers))))
        elif current > limit:
            self.custom_workers_var.set(str(limit))

    def _step_custom_workers(self, delta: int) -> None:
        if normalize_analysis_concurrency_mode(self.concurrency_var.get()) != ANALYSIS_CONCURRENCY_CUSTOM:
            return
        limit = max_analysis_workers()
        current = normalize_analysis_custom_workers(self.custom_workers_var.get()) or 1
        self.custom_workers_var.set(str(max(1, min(limit, current + delta))))
        self._update_concurrency_hint()

    def _start_gpu_status_refresh(self, *, force_refresh: bool = False) -> None:
        self.gpu_hardware_var.set(tr("settings.gpu_detecting"))
        self.gpu_backend_var.set(tr("settings.gpu_detecting"))
        self.gpu_reason_var.set(tr("settings.gpu_reason_detecting"))

        def _worker() -> None:
            status = detect_gpu_backend(force_refresh=force_refresh)

            def _finish() -> None:
                if not self.winfo_exists():
                    return
                self._last_gpu_status = status
                hardware = status.hardware_name if status.hardware_detected else status.hardware_name
                if status.driver_version:
                    hardware = f"{hardware} ({status.driver_version})"
                self.gpu_hardware_var.set(hardware)
                self.gpu_backend_var.set(status.backend_name if status.available else tr("settings.gpu_cpu"))
                if status.available:
                    self.gpu_reason_var.set(tr("settings.gpu_available"))
                    self.gpu_next_step_var.set(tr("settings.gpu_available"))
                elif status.hardware_detected:
                    self.gpu_reason_var.set(tr("settings.gpu_hw_no_backend"))
                    self.gpu_next_step_var.set(tr("settings.gpu_hw_no_backend"))
                else:
                    self.gpu_reason_var.set(tr("settings.gpu_cpu"))
                    self.gpu_next_step_var.set(tr("settings.gpu_cpu"))

            self.after(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()

    def _copy_gpu_diagnostics(self) -> None:
        status = self._last_gpu_status or detect_gpu_backend()
        text = (
            f"ShapeYourPhoto GPU diagnostics\n"
            f"hardware_detected={status.hardware_detected}\n"
            f"hardware_name={status.hardware_name}\n"
            f"driver_version={status.driver_version}\n"
            f"backend_name={status.backend_name}\n"
            f"available={status.available}\n"
            f"active={status.active}\n"
            f"reason={status.reason}\n"
            f"backend_reasons={' | '.join(status.backend_reasons)}"
        )
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._set_status(tr("settings.copied"), kind="temporary")
        except Exception as exc:
            messagebox.showwarning(tr("settings.gpu_copy"), str(exc), parent=self)

    def _open_gpu_prepare_help(self) -> None:
        self._open_gpu_help()
        self._set_status(tr("settings.gpu_prepare_opened"), kind="temporary")

    def _open_gpu_help(self) -> None:
        url = "https://helloalp.top/tools/shapeyourphoto/articles/faq.html#gpu"
        try:
            if not webbrowser.open(url):
                raise RuntimeError("open failed")
        except Exception:
            try:
                self.clipboard_clear()
                self.clipboard_append(url)
                self._set_status(tr("settings.copied"), kind="temporary")
            except Exception:
                messagebox.showinfo(tr("settings.gpu_help"), url, parent=self)

    def _clear_temporary_status(self) -> None:
        if self._status_kind == "temporary":
            self._save_status_var.set("")
            self._status_kind = ""
        self._status_after_id = None

    def _set_status(self, message: str, *, kind: str = "persistent", timeout_ms: int = 3500) -> None:
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except tk.TclError:
                pass
            self._status_after_id = None
        self._status_kind = kind
        self._save_status_var.set(message)
        if kind == "temporary":
            self._status_after_id = self.after(timeout_ms, self._clear_temporary_status)

    def _refresh_language_texts(self) -> None:
        self.title(app_window_title(tr("settings.app")))
        self.header_label.configure(text=tr("settings.app"))
        for notebook, tab, key in self._notebook_tab_labels:
            try:
                notebook.tab(tab, text=tr(key))
            except tk.TclError:
                pass
        for widget, key in self._text_widgets:
            try:
                widget.configure(text=tr(key))
            except tk.TclError:
                pass
        for key, (_listbox, _value_var, add_button) in self._scan_rule_widgets.items():
            add_button.configure(text=f"{tr('settings.rule.add')} {tr(f'settings.rule.{key}')}")
        self.cancel_button.configure(text=tr("settings.cancel"))
        self.save_button.configure(text=tr("settings.save"))
        self.version_var.set(f"{APP_NAME} v{APP_VERSION}\n{tr('settings.version_id').format(id=APP_VERSION_ID)}")
        if self.announcement_status_var.get() in {"暂无公告。", "No announcements.", "お知らせはありません。"}:
            self.announcement_status_var.set(tr("settings.no_announcements"))
            self._set_announcement_text(tr("settings.no_announcements"))
        if self._save_status_var.get() and self._status_kind != "temporary":
            self._save_status_var.set(tr("settings.saved_keep_open"))
        self._refresh_option_labels()
        self._update_concurrency_hint()

    def _confirm(self) -> None:
        prefixes = self._current_prefixes()
        if not prefixes:
            messagebox.showwarning(tr("settings.app"), tr("settings.need_prefix"), parent=self)
            return
        language = normalize_language(self.language_var.get())
        mode = normalize_analysis_concurrency_mode(self.concurrency_var.get())
        custom_workers = normalize_analysis_custom_workers(self.custom_workers_var.get()) if mode == ANALYSIS_CONCURRENCY_CUSTOM else 0
        limit = max_analysis_workers()
        if custom_workers > limit:
            custom_workers = limit
            self.custom_workers_var.set(str(limit))
        self.result = AppSettings(
            scan_ignore_prefixes=prefixes,
            scan_ignore_suffixes=self._current_suffixes(),
            scan_ignore_contains=self._current_contains(),
            default_scan_mode=normalize_default_scan_mode(self.scan_mode_var.get()),
            repair_summary_default_filter=normalize_repair_summary_filter(self.summary_filter_var.get()),
            analysis_concurrency_mode=mode,
            analysis_custom_workers=custom_workers,
            gpu_acceleration_mode=normalize_gpu_acceleration_mode(self.gpu_mode_var.get()),
            console_time_mode=normalize_console_time_mode(self.console_time_var.get()),
            theme_id=normalize_theme_id(self.theme_var.get()),
            ui_density=normalize_ui_density(self.density_var.get()),
            language=language,
            auto_check_updates=True,
        )
        if self._apply_callback is not None:
            try:
                applied = bool(self._apply_callback(self.result))
            except Exception as exc:
                messagebox.showerror(
                    tr("settings.save_failed_title"),
                    tr("settings.save_failed_body").format(error=exc),
                    parent=self,
                )
                self._set_status(tr("settings.save_failed"), kind="persistent")
                return
            if not applied:
                self._set_status(tr("settings.save_failed"), kind="persistent")
                return
            language_changed = language != self._initial_language
            self._initial_language = language
            self._set_status(tr("settings.saved_keep_open"), kind="persistent")
            if language_changed:
                set_current_language(language)
                self._refresh_language_texts()
            return
        if language != self._initial_language:
            set_current_language(language)
            self._refresh_language_texts()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _check_updates_now(self) -> None:
        if self._update_check_callback is None:
            messagebox.showinfo(tr("settings.check_updates"), tr("settings.check_unavailable"), parent=self)
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
        self.announcement_status_var.set(tr("settings.refreshing_announcements"))
        self._set_announcement_text(tr("settings.fetching_announcements"))
        self._log("cloud message manual refresh requested from settings")

        def _worker() -> None:
            result = fetch_cloud_messages("")

            def _finish() -> None:
                if not self.winfo_exists():
                    return
                if not result.ok or result.payload is None:
                    self.announcement_status_var.set(tr("settings.announcement_failed"))
                    self._set_announcement_text(tr("settings.announcement_retry"))
                    self._log(f"cloud message manual refresh failed: {result.error}")
                    return
                messages = result.payload.get("messages", [])
                if isinstance(messages, dict):
                    messages = [messages]
                if not isinstance(messages, list):
                    messages = []
                enabled_messages = [item for item in messages if isinstance(item, dict) and item.get("enabled", True)]
                if not enabled_messages:
                    self.announcement_status_var.set(tr("settings.no_announcements"))
                    self._set_announcement_text(tr("settings.no_announcements"))
                    self._log("cloud message manual refresh completed: empty")
                    return
                lines: list[str] = []
                for item in enabled_messages[:5]:
                    title = str(item.get("title") or tr("settings.section.announcements"))
                    body = str(item.get("body") or "").strip()
                    lines.append(title)
                    if body:
                        lines.append(body)
                    lines.append("")
                self.announcement_status_var.set(tr("settings.announcement_count").format(count=len(enabled_messages)))
                self._set_announcement_text("\n".join(lines).strip())
                self._log(f"cloud message manual refresh completed: count={len(enabled_messages)}")

            self.after(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()


def show_app_settings_dialog(
    parent: tk.Widget,
    settings: AppSettings,
    update_check_callback=None,
    log_callback=None,
    apply_callback=None,
    initial_tab: str | None = None,
) -> AppSettings | None:
    dialog = AppSettingsDialog(
        parent,
        settings,
        update_check_callback=update_check_callback,
        log_callback=log_callback,
        apply_callback=apply_callback,
        initial_tab=initial_tab,
    )
    dialog.wait_window()
    return dialog.result
