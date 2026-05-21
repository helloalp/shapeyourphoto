from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import quote

from app_settings import AppSettings, load_app_settings, save_app_settings
from app_console import AppConsole
from app_metadata import APP_NAME, APP_VERSION
from diagnostics_chart import DiagnosticsChart
from dnd_support import install_drop_target
from file_actions import ScanResult
from gpu_accel import detect_gpu_backend, shutdown_native_gpu_server
from history_dialog import show_history_dialog
from models import AnalysisResult, SimilarImageGroup
from preview_cache import ThumbnailCache
from progress_dialog import TaskProgressController
from settings_dialog import show_app_settings_dialog
from stats_dialog import show_stats_dialog
from stats_store import load_stats
from format_conversion import show_format_conversion_dialog
from log_manager import cleanup_old_logs, export_logs_bundle
from ui.language import get_current_language, set_current_language, tr
from ui.display_names import display_name
from ui.themes import get_theme
from ui.hidpi import configure_fonts
from ui.cloud_actions import UiCloudActionsMixin
from ui.splash import SplashScreen
from ui_analysis_actions import UiAnalysisActionsMixin
from ui_file_list import UiFileListMixin
from ui_repair_actions import UiRepairActionsMixin
from ui_review_actions import UiReviewActionsMixin
from ui_scan_actions import UiScanActionsMixin
from ui_task_console import UiTaskConsoleMixin


FILTER_ISSUE_CODES = [
    "overexposed",
    "underexposed",
    "low_contrast",
    "muted_colors",
    "over_saturated",
    "out_of_focus",
    "high_noise",
    "color_cast",
    "portrait_out_of_focus",
]


class PhotoAnalyzerApp(
    UiTaskConsoleMixin,
    UiCloudActionsMixin,
    UiScanActionsMixin,
    UiAnalysisActionsMixin,
    UiRepairActionsMixin,
    UiReviewActionsMixin,
    UiFileListMixin,
):
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        screen_w = max(1280, self.root.winfo_screenwidth())
        screen_h = max(760, self.root.winfo_screenheight())
        initial_w = min(max(1600, int(screen_w * 0.96)), screen_w - 16)
        initial_h = min(max(980, int(screen_h * 0.94)), screen_h - 48)
        min_w = min(1460, max(1220, screen_w - 60))
        min_h = min(900, max(740, screen_h - 96))
        self.root.geometry(f"{initial_w}x{initial_h}")
        self.root.minsize(min_w, min_h)

        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar(value="请选择图片文件夹开始分析。")
        self.filter_var = tk.StringVar(value="全部")
        self.only_problem_var = tk.BooleanVar(value=True)
        self.debug_open_after_repair_var = tk.BooleanVar(value=False)
        self.progress_text_var = tk.StringVar(value=tr("task.waiting"))
        self.progress_detail_var = tk.StringVar(value=tr("task.not_started"))
        self.progress_value = tk.DoubleVar(value=0.0)
        self.hud_name_var = tk.StringVar(value=tr("hud.no_selection"))
        self.hud_risk_var = tk.StringVar(value=tr("hud.risk_empty"))
        self.hud_tags_var = tk.StringVar(value=tr("hud.tags_waiting"))
        self.hud_methods_var = tk.StringVar(value=tr("hud.methods_waiting"))

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
        set_current_language(self.settings.language)
        if self.status_var.get() == "请选择图片文件夹开始分析。":
            self.status_var.set(tr("status.ready"))
        self.console.set_time_mode(self.settings.console_time_mode)
        self.console.set_log_language_mode(getattr(self.settings, "log_language_mode", "follow_ui"))
        removed_logs = cleanup_old_logs(getattr(self.settings, "log_retention_days", 30))
        self.drop_target = None
        self.sort_column = "name"
        self.sort_reverse = False
        self.analysis_phase_progress: dict[Path, int] = {}
        self._last_scan_update = 0.0
        self._scan_run_id = 0
        self._scan_cancel_event: threading.Event | None = None
        self._scan_started_at = 0.0
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._last_analysis_targets: list[Path] = []
        self._analysis_run_id = 0
        self._analysis_cancel_event: threading.Event | None = None
        self._analysis_cancel_targets: list[Path] = []
        self._analysis_allowed_targets: set[Path] = set()
        self._repair_run_id = 0
        self._repair_cancel_event: threading.Event | None = None
        self._repair_cancel_targets: list[Path] = []
        self._repair_pre_state: dict[Path, tuple[bool, AnalysisResult | None, bool, str | None]] = {}
        self._repair_rollback_backups: dict[Path, Path] = {}
        self._repair_rollback_backup_root: Path | None = None
        self._task_started_at = 0.0
        self._last_scan_summary: str = ""
        self._last_scan_results: list[ScanResult] = []
        self._auto_analyze_after_scan = False
        self._console_flush_total_ms = 0.0
        self._console_flush_count = 0
        self._closing = False
        self._always_on_top = False
        self._topmost_button: ttk.Button | None = None
        self._pin_icon_off: tk.PhotoImage | None = None
        self._pin_icon_on: tk.PhotoImage | None = None
        self._large_preview_image: tk.PhotoImage | None = None
        self._current_preview_path: Path | None = None
        self._large_preview_render_key: tuple[str, int, int, int] | None = None
        self._large_preview_pending_key: tuple[str, int, int, int] | None = None
        self._large_preview_after_id: str | None = None
        self._large_preview_run_id = 0
        self._last_repair_summary_payload = None

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
        self.root.bind_all("<Alt-F4>", lambda _event: self._on_close(), add="+")
        self.root.bind("<Map>", lambda _event: self._apply_topmost_state(), add="+")
        self.root.bind("<FocusIn>", lambda _event: self._apply_topmost_state(), add="+")
        self.root.after_idle(self._apply_initial_layout)
        self.root.after(800, self._start_background_gpu_probe)
        self.root.after(1600, self._run_startup_cloud_checks)
        for warning in self._settings_warnings:
            self._log_console(warning)
        if removed_logs:
            self._log_console(f"log cleanup: removed {removed_logs} old log files")
        self._log_console(
            "scan ignore rules: "
            f"prefix={', '.join(self.settings.scan_ignore_prefixes)} | "
            f"suffix={', '.join(self.settings.scan_ignore_suffixes)} | "
            f"contains={', '.join(self.settings.scan_ignore_contains)}"
        )

    def _start_background_gpu_probe(self) -> None:
        def worker() -> None:
            status = detect_gpu_backend()
            hardware = status.hardware_name if status.hardware_detected else "not detected"
            self._log_console(
                "gpu probe: "
                f"hardware={hardware} | driver={status.driver_version or 'unknown'} | "
                f"native_present={status.native_backend_present} | backend={status.backend_name} | "
                f"available={status.available} | active={status.active} | reason={status.reason}"
            )

        threading.Thread(target=worker, daemon=True).start()

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        theme = get_theme(getattr(self.settings, "theme_id", "classic_green"))
        self._theme = theme
        density = getattr(self.settings, "ui_density", "standard")
        density_delta = 1 if density in {"comfortable", "high_detail"} else 0
        spacing_delta = 2 if density == "high_detail" else 1 if density == "comfortable" else 0
        configure_fonts(self.root, delta=theme.font_delta + density_delta)
        base_size = 11 + theme.font_delta + density_delta
        self.root.configure(bg=theme.background)
        style.configure("TFrame", background=theme.background)
        style.configure("Panel.TFrame", background=theme.panel)
        style.configure("TopCard.TFrame", background=theme.panel_alt)
        style.configure("TLabel", background=theme.background, foreground=theme.text, font=("Microsoft YaHei UI", base_size))
        style.configure("Header.TLabel", background=theme.background, foreground=theme.primary, font=("Microsoft YaHei UI", 20 + theme.font_delta, "bold"))
        style.configure("Sub.TLabel", background=theme.background, foreground=theme.muted_text, font=("Microsoft YaHei UI", base_size))
        style.configure("PanelTitle.TLabel", background=theme.panel, foreground=theme.text, font=("Microsoft YaHei UI", base_size, "bold"))
        style.configure("HudTitle.TLabel", background=theme.panel_alt, foreground=theme.primary, font=("Microsoft YaHei UI", base_size, "bold"))
        style.configure("HudValue.TLabel", background=theme.panel_alt, foreground=theme.muted_text, font=("Microsoft YaHei UI", max(9, base_size - 2)))
        style.configure(
            "Treeview",
            font=("Microsoft YaHei UI", max(10, base_size - 1)),
            rowheight=90 + theme.spacing * 4 + spacing_delta * 8,
            background=theme.panel,
            fieldbackground=theme.panel,
            foreground=theme.text,
            bordercolor=theme.border,
            lightcolor=theme.border,
            darkcolor=theme.border,
        )
        style.configure(
            "Treeview.Heading",
            font=("Microsoft YaHei UI", max(10, base_size - 1), "bold"),
            background=theme.button,
            foreground=theme.text,
            bordercolor=theme.border,
        )
        style.map("Treeview", background=[("selected", theme.selection)], foreground=[("selected", theme.text)])
        style.configure("TButton", background=theme.button, foreground=theme.text, bordercolor=theme.border, focusthickness=2, focuscolor=theme.accent)
        style.map(
            "TButton",
            background=[("disabled", theme.disabled_bg), ("active", theme.selection), ("pressed", theme.selection)],
            foreground=[("disabled", theme.disabled_text)],
        )
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", base_size, "bold"), padding=(10 + theme.spacing + spacing_delta, 7 + theme.spacing + spacing_delta))
        style.configure("Soft.TButton", font=("Microsoft YaHei UI", base_size), padding=(10 + theme.spacing + spacing_delta, 7 + theme.spacing + spacing_delta))
        style.configure("Topmost.TButton", font=("Microsoft YaHei UI", max(9, base_size - 2)), padding=(8, 4))
        style.configure("TopmostOn.TButton", font=("Microsoft YaHei UI", max(9, base_size - 2), "bold"), padding=(8, 4))
        style.configure("TEntry", fieldbackground=theme.input_bg, foreground=theme.text, bordercolor=theme.border)
        style.configure("TCombobox", fieldbackground=theme.input_bg, foreground=theme.text, bordercolor=theme.border)
        style.configure("Vertical.TScrollbar", background=theme.button, troughcolor=theme.panel_alt, bordercolor=theme.border, arrowcolor=theme.text)
        style.configure("Horizontal.TScrollbar", background=theme.button, troughcolor=theme.panel_alt, bordercolor=theme.border, arrowcolor=theme.text)
        style.configure("TProgressbar", background=theme.accent, troughcolor=theme.panel_alt, bordercolor=theme.border)
        style.configure("TNotebook", background=theme.background, bordercolor=theme.border)
        style.configure("TNotebook.Tab", background=theme.button, foreground=theme.text, padding=(9, 5))
        style.map("TNotebook.Tab", background=[("selected", theme.selection)], foreground=[("selected", theme.text)])
        style.configure("TLabelframe", background=theme.panel, bordercolor=theme.border)
        style.configure("TLabelframe.Label", background=theme.panel, foreground=theme.text, font=("Microsoft YaHei UI", base_size, "bold"))
        for widget_name in ("summary_text", "meta_text", "console_text", "announcement_text"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                try:
                    font = ("Consolas", 9) if widget_name == "console_text" else ("Microsoft YaHei UI", 10)
                    widget.configure(bg=theme.panel, fg=theme.text, insertbackground=theme.text, font=font)
                except tk.TclError:
                    pass
        self._pin_icon_off = self._make_topmost_icon(False)
        self._pin_icon_on = self._make_topmost_icon(True)
        self._refresh_topmost_button()

    def _make_topmost_icon(self, selected: bool) -> tk.PhotoImage:
        size = 24
        image = tk.PhotoImage(width=size, height=size)
        bg = getattr(self._theme, "panel_alt", "#f8fbf8")
        color = getattr(self._theme, "primary", "#286b4a") if selected else getattr(self._theme, "muted_text", "#6d7b72")
        image.put(bg, to=(0, 0, size, size))
        for x in range(8, 16):
            image.put(color, to=(x, 4, x + 1, 7))
        for y in range(7, 12):
            image.put(color, to=(6, y, 18, y + 1))
        for offset in range(0, 8):
            x = 12 + offset // 2
            y = 12 + offset
            image.put(color, to=(x, y, x + 1, y + 1))
        for x in range(9, 16):
            image.put(color, to=(x, 18, x + 1, 20))
        return image

    def _refresh_topmost_button(self) -> None:
        if self._topmost_button is None:
            return
        self._topmost_button.configure(
            image=self._pin_icon_on if self._always_on_top else self._pin_icon_off,
            text=tr("action.topmost_on") if self._always_on_top else tr("action.topmost_off"),
            style="TopmostOn.TButton" if self._always_on_top else "Topmost.TButton",
        )

    def _apply_topmost_state(self) -> None:
        try:
            self.root.attributes("-topmost", bool(self._always_on_top))
            if self._always_on_top:
                self.root.lift()
        except Exception as exc:
            self._log_console(f"topmost apply failed: {exc}")

    def toggle_topmost(self) -> None:
        self._always_on_top = not self._always_on_top
        self._apply_topmost_state()
        self._refresh_topmost_button()

    def _localized_filter_options(self) -> list[tuple[str, str]]:
        options = [(tr("filter.all"), "all"), (tr("filter.problem"), "problem")]
        options.extend((display_name("issue", code), code) for code in FILTER_ISSUE_CODES)
        return options

    def _selected_filter_token(self) -> str:
        label = self.filter_var.get()
        current_map = getattr(self, "_filter_label_to_token", {})
        if label in current_map:
            return str(current_map[label])
        legacy = {
            "全部": "all",
            "仅问题图": "problem",
            "过曝": "overexposed",
            "欠曝": "underexposed",
            "低对比": "low_contrast",
            "色彩寡淡": "muted_colors",
            "过饱和": "over_saturated",
            "虚焦": "out_of_focus",
            "噪点偏高": "high_noise",
            "色偏": "color_cast",
            "人像主体虚焦": "portrait_out_of_focus",
        }
        return legacy.get(label, "all")

    def _refresh_filter_options(self) -> None:
        token = self._selected_filter_token()
        options = self._localized_filter_options()
        self._filter_label_to_token = {label: value for label, value in options}
        self._filter_token_to_label = {value: label for label, value in options}
        labels = [label for label, _value in options]
        if hasattr(self, "filter_box"):
            self.filter_box.configure(values=labels)
        self.filter_var.set(self._filter_token_to_label.get(token, labels[0]))

    def _refresh_language_texts(self) -> None:
        self._build_menu()
        self._refresh_topmost_button()
        for attr, key in [
            ("subtitle_label", "app.subtitle"),
            ("filter_label", "filter.label"),
            ("list_title_label", "list.title"),
            ("list_action_hint_label", "list.action_hint"),
            ("cleanup_description_label", "cleanup.description"),
            ("right_title_label", "right.title"),
        ]:
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.configure(text=tr(key))
        for attr, key in [
            ("choose_folder_button", "action.choose_folder"),
            ("choose_image_button", "action.choose_image"),
            ("analyze_all_button", "action.analyze_all"),
            ("analyze_selected_button", "action.analyze_selected"),
            ("repair_current_button", "action.repair_selected"),
            ("repair_checked_button", "action.repair_checked"),
            ("format_convert_button", "action.format_convert"),
            ("cleanup_button", "action.cleanup_checked"),
            ("task_cancel_button", "action.cancel_task"),
            ("scan_summary_button", "view.scan_summary"),
            ("select_current_button", "action.select_current"),
            ("unselect_current_button", "action.unselect_current"),
            ("select_problem_button", "action.select_problem_items"),
            ("unselect_all_button", "action.unselect_all"),
            ("refresh_list_button", "action.refresh_list"),
            ("cleanup_delete_button", "action.cleanup_delete"),
            ("cleanup_select_current_button", "action.cleanup_select_current"),
            ("cleanup_toggle_selected_button", "action.cleanup_toggle_selected"),
            ("cleanup_select_all_button", "action.select_all"),
            ("cleanup_unselect_all_button", "action.unselect_all_short"),
            ("meta_edit_button", "meta.edit"),
            ("gps_edit_button", "gps.edit"),
        ]:
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.configure(text=tr(key))
        for attr, key in [("auto_check", "filter.only_problem"), ("debug_open_check", "filter.debug_compare")]:
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.configure(text=tr(key))
        if hasattr(self, "progress_panel"):
            self.progress_panel.configure(text=tr("progress.title"))
        if hasattr(self, "tree"):
            self.tree.heading("#0", text=tr("tree.preview_name"))
            self.tree.heading("pick", text=tr("tree.pick"))
            self.tree.heading("status", text=tr("tree.status"))
            self.tree.heading("risk", text=tr("tree.risk"))
            self.tree.heading("tags", text=tr("tree.tags"))
        if self.list_menu is not None:
            self.list_menu.entryconfigure(0, label=tr("list.menu.toggle_pick"))
            self.list_menu.entryconfigure(1, label=tr("list.menu.select_all"))
            self.list_menu.entryconfigure(2, label=tr("list.menu.invert"))
            self.list_menu.entryconfigure(3, label=tr("list.menu.clear"))
            self.list_menu.entryconfigure(5, label=tr("list.menu.remove"))
        if hasattr(self, "cleanup_frame"):
            self.cleanup_frame.configure(text=tr("cleanup.title"))
        if hasattr(self, "cleanup_tree"):
            self.cleanup_tree.heading("#0", text=tr("cleanup.tree_name"))
            self.cleanup_tree.heading("pick", text=tr("cleanup.state"))
            self.cleanup_tree.heading("severity", text=tr("cleanup.severity"))
            self.cleanup_tree.heading("reason", text=tr("cleanup.reason"))
        if hasattr(self, "right_info_book"):
            for tab, key in getattr(self, "_right_info_tabs", []):
                self.right_info_book.tab(tab, text=tr(key))
        self._refresh_filter_options()
        if not getattr(self, "image_paths", []):
            self._clear_hud_and_summary()
            self._update_list_stats()
        else:
            current_path = self._current_path()
            self.refresh_tree()
            if current_path is not None:
                self._select_path(current_path)
        state = getattr(getattr(self, "progress_controller", None), "state", None)
        if state is not None and state.done <= 0 and state.title in {"等待任务", "Waiting", "待機中", tr("task.waiting")}:
            self.progress_text_var.set(tr("task.waiting"))
            self.progress_detail_var.set(tr("task.not_started"))

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        review_menu = tk.Menu(menu_bar, tearoff=False)
        review_menu.add_command(label=tr("view.cleanup"), command=self.open_cleanup_review_window)
        review_menu.add_command(label=tr("view.similar"), command=self.open_similar_group_window)
        review_menu.add_command(label=tr("action.stats"), command=self.show_stats)
        review_menu.add_command(label=tr("view.scan_summary"), command=self.show_last_scan_summary)
        review_menu.add_command(label=tr("view.repair_summary"), command=self.show_last_repair_summary)
        menu_bar.add_cascade(label=tr("menu.view"), menu=review_menu)
        settings_menu = tk.Menu(menu_bar, tearoff=False)
        settings_menu.add_command(label=tr("settings.app"), command=self.open_settings_panel)
        menu_bar.add_cascade(label=tr("menu.settings"), menu=settings_menu)
        if get_current_language() != "en_US":
            menu_bar.add_command(label=tr("menu.language_quick"), command=lambda: self.open_settings_panel(initial_tab="language"))
        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label=tr("menu.help_website"), command=self.show_help_website_info)
        help_menu.add_command(label=tr("action.website"), command=self.open_author_website)
        help_menu.add_command(label=tr("log.export"), command=self.export_logs_for_support)
        help_menu.add_command(label=tr("menu.contact_author"), command=self.show_contact_author_window)
        menu_bar.add_cascade(label=tr("menu.help"), menu=help_menu)
        self.root.configure(menu=menu_bar)
        self.menu_bar = menu_bar
        self.review_menu = review_menu
        self.settings_menu = settings_menu
        self.help_menu = help_menu

    def _build_ui(self) -> None:
        self._build_menu()

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        top_shell = ttk.Frame(outer, style="TopCard.TFrame", padding=10)
        top_shell.pack(fill="x")
        body_shell = ttk.Frame(outer, style="Panel.TFrame", padding=(0, 6, 0, 0))
        body_shell.pack(fill="both", expand=True)

        header = ttk.Frame(top_shell, style="TopCard.TFrame")
        header.pack(fill="x")
        header.columnconfigure(0, weight=1)
        title_area = ttk.Frame(header, style="TopCard.TFrame")
        title_area.grid(row=0, column=0, sticky="ew")
        ttk.Label(title_area, text=f"{APP_NAME} v{APP_VERSION}", style="Header.TLabel").pack(anchor="w")
        self.subtitle_label = ttk.Label(title_area, text=tr("app.subtitle"), style="Sub.TLabel")
        self.subtitle_label.pack(anchor="w", pady=(2, 6))
        self._topmost_button = ttk.Button(
            header,
            text="置顶",
            image=self._pin_icon_off,
            compound="top",
            command=self.toggle_topmost,
            style="Topmost.TButton",
            width=6,
        )
        self._topmost_button.grid(row=0, column=1, sticky="ne", padx=(12, 0))
        self._refresh_topmost_button()

        controls = ttk.Frame(top_shell, style="Panel.TFrame", padding=8)
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)

        path_entry = ttk.Entry(controls, textvariable=self.folder_var, font=("Consolas", 11))
        path_entry.grid(row=0, column=0, columnspan=6, sticky="ew", padx=(0, 10), pady=(0, 5))

        self.choose_folder_button = ttk.Button(controls, text=tr("action.choose_folder"), command=self.choose_folder)
        self.choose_image_button = ttk.Button(controls, text=tr("action.choose_image"), command=self.choose_image)
        self.analyze_all_button = ttk.Button(controls, text=tr("action.analyze_all"), command=self.analyze_all)
        self.analyze_selected_button = ttk.Button(controls, text=tr("action.analyze_selected"), command=self.analyze_selected)
        self.repair_current_button = ttk.Button(controls, text=tr("action.repair_selected"), command=self.repair_current)
        self.repair_checked_button = ttk.Button(controls, text=tr("action.repair_checked"), command=self.repair_checked)
        self.format_convert_button = ttk.Button(controls, text=tr("action.format_convert"), command=self.open_format_conversion)
        self.cleanup_button = ttk.Button(controls, text=tr("action.cleanup_checked"), command=self.cleanup_selected)

        button_specs: list[ttk.Button] = []
        button_specs.append(self.choose_folder_button)
        button_specs.extend(
            [
                self.choose_image_button,
                self.analyze_all_button,
                self.analyze_selected_button,
                self.repair_current_button,
                self.repair_checked_button,
                self.format_convert_button,
                self.cleanup_button,
            ]
        )
        button_columns = 4
        for offset in range(button_columns):
            controls.columnconfigure(offset + 1, weight=1)
        for index, button in enumerate(button_specs):
            row = 1 + index // button_columns
            column = 1 + (index % button_columns)
            button.grid(row=row, column=column, sticky="ew", padx=4, pady=3)

        self.control_widgets.extend(button_specs)

        toolbar = ttk.Frame(top_shell, padding=(0, 6), style="TopCard.TFrame")
        toolbar.pack(fill="x")
        self.filter_label = ttk.Label(toolbar, text=tr("filter.label"))
        self.filter_label.pack(side="left")
        self.filter_box = ttk.Combobox(toolbar, textvariable=self.filter_var, state="readonly", width=22)
        self._refresh_filter_options()
        self.filter_box.pack(side="left", padx=(0, 12))
        self.filter_box.bind("<<ComboboxSelected>>", lambda _: self.refresh_tree())
        self.auto_check = ttk.Checkbutton(toolbar, text=tr("filter.only_problem"), variable=self.only_problem_var)
        self.auto_check.pack(side="left")
        self.debug_open_check = ttk.Checkbutton(
            toolbar,
            text=tr("filter.debug_compare"),
            variable=self.debug_open_after_repair_var,
        )
        self.debug_open_check.pack(side="left", padx=(12, 0))
        self.control_widgets.extend([self.filter_box, self.auto_check, self.debug_open_check])

        self.progress_panel = ttk.LabelFrame(top_shell, text=tr("progress.title"), padding=8)
        self.progress_panel.pack(fill="x", pady=(2, 6))
        self.progress_panel.columnconfigure(1, weight=1)
        ttk.Label(self.progress_panel, textvariable=self.progress_text_var, style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.progress_panel, textvariable=self.progress_detail_var, style="Sub.TLabel").grid(
            row=0, column=1, sticky="ew", padx=(10, 8)
        )
        self.scan_summary_button = ttk.Button(
            self.progress_panel,
            text=tr("view.scan_summary"),
            command=self.show_last_scan_summary,
            state="disabled",
        )
        self.scan_summary_button.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.task_cancel_button = ttk.Button(
            self.progress_panel,
            text=tr("action.cancel_task"),
            command=self.cancel_current_task,
            state="disabled",
        )
        self.task_cancel_button.grid(row=0, column=3, sticky="e")
        self.progress_bar = ttk.Progressbar(self.progress_panel, mode="determinate", maximum=1, variable=self.progress_value)
        self.progress_bar.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))

        main = ttk.PanedWindow(body_shell, orient="horizontal")
        main.pack(fill="both", expand=True)
        self.main_pane = main

        left = ttk.Frame(main, style="Panel.TFrame", padding=8)
        right = ttk.Frame(main, style="Panel.TFrame", padding=(8, 8, 0, 8))
        main.add(left, weight=3)
        main.add(right, weight=2)
        try:
            main.paneconfigure(left, minsize=560)
            main.paneconfigure(right, minsize=480)
        except tk.TclError:
            pass

        list_header = ttk.Frame(left, style="Panel.TFrame")
        list_header.pack(fill="x", pady=(0, 4))
        self.list_title_label = ttk.Label(list_header, text=tr("list.title"), style="PanelTitle.TLabel")
        self.list_title_label.pack(side="left")
        self.list_stats_var = tk.StringVar(value=tr("list.empty_stats"))
        ttk.Label(list_header, textvariable=self.list_stats_var, style="Sub.TLabel").pack(side="right")
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
        self.tree.heading("#0", text=tr("tree.preview_name"), command=lambda: self._toggle_sort("name"))
        self.tree.column("#0", width=370, anchor="w")
        self.tree.heading("pick", text=tr("tree.pick"))
        self.tree.column("pick", width=92, anchor="center")
        self.tree.heading("status", text=tr("tree.status"), command=lambda: self._toggle_sort("status"))
        self.tree.heading("risk", text=tr("tree.risk"), command=lambda: self._toggle_sort("risk"))
        self.tree.heading("tags", text=tr("tree.tags"), command=lambda: self._toggle_sort("tags"))
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
        self.tree.bind("<Control-a>", self.select_all_list_items)
        self.tree.bind("<Control-A>", self.select_all_list_items)
        self.tree.bind("<Delete>", self.remove_selected_from_list)

        self.list_menu = tk.Menu(self.root, tearoff=False)
        self.list_menu.add_command(label=tr("list.menu.toggle_pick"), command=self.toggle_cleanup_flag)
        self.list_menu.add_command(label=tr("list.menu.select_all"), command=self.select_all_list_items)
        self.list_menu.add_command(label=tr("list.menu.invert"), command=self.invert_list_selection)
        self.list_menu.add_command(label=tr("list.menu.clear"), command=self.clear_list_selection)
        self.list_menu.add_separator()
        self.list_menu.add_command(label=tr("list.menu.remove"), command=self.remove_selected_from_list)

        action_bar = ttk.Frame(left)
        action_bar.pack(fill="x", pady=(6, 0))
        self.select_current_button = ttk.Button(action_bar, text=tr("action.select_current"), command=self.select_current)
        self.select_current_button.pack(side="left")
        self.unselect_current_button = ttk.Button(action_bar, text=tr("action.unselect_current"), command=self.unselect_current)
        self.unselect_current_button.pack(side="left", padx=6)
        self.select_problem_button = ttk.Button(action_bar, text=tr("action.select_problem_items"), command=self.select_problem_items)
        self.select_problem_button.pack(side="left")
        self.unselect_all_button = ttk.Button(action_bar, text=tr("action.unselect_all"), command=self.unselect_all)
        self.unselect_all_button.pack(side="left", padx=6)
        self.refresh_list_button = ttk.Button(action_bar, text=tr("action.refresh_list"), command=self.refresh_tree)
        self.refresh_list_button.pack(side="left")
        self.list_action_hint_label = ttk.Label(action_bar, text=tr("list.action_hint"))
        self.list_action_hint_label.pack(side="right")

        self.cleanup_frame = ttk.LabelFrame(left, text=tr("cleanup.title"), padding=10)
        self.cleanup_frame.pack(fill="both", expand=False, pady=(8, 0))
        self.cleanup_frame.columnconfigure(0, weight=1)
        self.cleanup_frame.rowconfigure(1, weight=1)
        self.cleanup_description_label = ttk.Label(
            self.cleanup_frame,
            text=tr("cleanup.description"),
            style="Sub.TLabel",
        )
        self.cleanup_description_label.grid(row=0, column=0, sticky="w", pady=(0, 8))

        cleanup_tree_frame = ttk.Frame(self.cleanup_frame, style="Panel.TFrame")
        cleanup_tree_frame.grid(row=1, column=0, sticky="nsew")
        cleanup_tree_frame.columnconfigure(0, weight=1)
        cleanup_tree_frame.rowconfigure(0, weight=1)

        self.cleanup_tree = ttk.Treeview(
            cleanup_tree_frame,
            columns=("pick", "severity", "reason"),
            show=("tree", "headings"),
            selectmode="extended",
            height=5,
        )
        self.cleanup_tree.heading("#0", text=tr("cleanup.tree_name"))
        self.cleanup_tree.column("#0", width=260, anchor="w")
        self.cleanup_tree.heading("pick", text=tr("cleanup.state"))
        self.cleanup_tree.column("pick", width=72, anchor="center")
        self.cleanup_tree.heading("severity", text=tr("cleanup.severity"))
        self.cleanup_tree.column("severity", width=72, anchor="center")
        self.cleanup_tree.heading("reason", text=tr("cleanup.reason"))
        self.cleanup_tree.column("reason", width=430, anchor="w")
        cleanup_scroll = ttk.Scrollbar(cleanup_tree_frame, orient="vertical", command=self.cleanup_tree.yview)
        self.cleanup_tree.configure(yscrollcommand=cleanup_scroll.set)
        self.cleanup_tree.grid(row=0, column=0, sticky="nsew")
        cleanup_scroll.grid(row=0, column=1, sticky="ns")
        self.cleanup_tree.bind("<<TreeviewSelect>>", self.on_cleanup_tree_select)
        self.cleanup_tree.bind("<Button-1>", self.on_cleanup_tree_click, add="+")

        cleanup_action_bar = ttk.Frame(self.cleanup_frame)
        cleanup_action_bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.cleanup_delete_button = ttk.Button(
            cleanup_action_bar,
            text=tr("action.cleanup_delete"),
            command=self.cleanup_selected_candidates,
            state="disabled",
        )
        self.cleanup_delete_button.pack(side="left")
        self.cleanup_select_current_button = ttk.Button(
            cleanup_action_bar,
            text=tr("action.cleanup_select_current"),
            command=self.select_cleanup_current,
        )
        self.cleanup_select_current_button.pack(side="left", padx=(6, 0))
        self.cleanup_toggle_selected_button = ttk.Button(
            cleanup_action_bar,
            text=tr("action.cleanup_toggle_selected"),
            command=self.toggle_selected_cleanup_candidates,
        )
        self.cleanup_toggle_selected_button.pack(side="left", padx=6)
        self.cleanup_select_all_button = ttk.Button(cleanup_action_bar, text=tr("action.select_all"), command=self.select_all_cleanup_candidates)
        self.cleanup_select_all_button.pack(side="left")
        self.cleanup_unselect_all_button = ttk.Button(
            cleanup_action_bar,
            text=tr("action.unselect_all_short"),
            command=self.unselect_all_cleanup_candidates,
        )
        self.cleanup_unselect_all_button.pack(side="left", padx=6)
        self.cleanup_hint_var = tk.StringVar(value=tr("cleanup.no_selection"))
        ttk.Label(cleanup_action_bar, textvariable=self.cleanup_hint_var, style="Sub.TLabel").pack(side="right")

        self.right_title_label = ttk.Label(right, text=tr("right.title"), style="PanelTitle.TLabel")
        self.right_title_label.pack(anchor="w", pady=(0, 8))
        right_book = ttk.Notebook(right)
        right_book.pack(fill="both", expand=True)
        self.right_info_book = right_book

        diagnosis_tab = ttk.Frame(right_book, style="Panel.TFrame", padding=(0, 8, 0, 0))
        preview_tab = ttk.Frame(right_book, style="Panel.TFrame", padding=(0, 8, 0, 0))
        meta_tab = ttk.Frame(right_book, style="Panel.TFrame", padding=(0, 8, 0, 0))
        console_tab = ttk.Frame(right_book, style="Panel.TFrame", padding=(0, 8, 0, 0))

        diagnosis_tab.columnconfigure(0, weight=1)
        diagnosis_tab.rowconfigure(0, weight=1)
        chart_frame = ttk.Frame(diagnosis_tab, style="Panel.TFrame")
        chart_frame.grid(row=0, column=0, sticky="nsew")

        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(1, weight=1, minsize=220)

        hud_frame = ttk.Frame(chart_frame, style="TopCard.TFrame", padding=(8, 6))
        hud_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        hud_frame.columnconfigure(0, weight=3)
        hud_frame.columnconfigure(1, minsize=138)
        ttk.Label(hud_frame, textvariable=self.hud_name_var, style="HudTitle.TLabel", wraplength=520).grid(row=0, column=0, sticky="ew")
        ttk.Label(hud_frame, textvariable=self.hud_risk_var, style="HudTitle.TLabel", anchor="e", width=14).grid(row=0, column=1, sticky="e")
        ttk.Label(hud_frame, textvariable=self.hud_tags_var, style="HudValue.TLabel", wraplength=760).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        ttk.Label(hud_frame, textvariable=self.hud_methods_var, style="HudValue.TLabel", wraplength=760).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        self.chart = DiagnosticsChart(chart_frame)
        self.chart.grid(row=1, column=0, sticky="nsew")
        self.chart.canvas.configure(height=360)

        summary_frame = ttk.Frame(diagnosis_tab, style="Panel.TFrame")
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
        self.summary_text.insert("1.0", tr("summary.empty"))
        self.summary_text.config(state="disabled")

        meta_tab.columnconfigure(0, weight=1)
        meta_tab.rowconfigure(1, weight=1)
        meta_toolbar = ttk.Frame(meta_tab)
        meta_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        meta_toolbar.columnconfigure(0, weight=1)
        self.meta_edit_button = ttk.Button(meta_toolbar, text=tr("meta.edit"), command=self.edit_current_metadata, state="disabled")
        self.meta_edit_button.grid(row=0, column=1, sticky="e")
        self.gps_edit_button = ttk.Button(meta_toolbar, text=tr("gps.edit"), command=self.edit_current_gps, state="disabled")
        self.gps_edit_button.grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.meta_text = tk.Text(meta_tab, wrap="word", font=("Microsoft YaHei UI", 10), bg="#f8fbf8", relief="flat", padx=10, pady=10)
        meta_scroll = ttk.Scrollbar(meta_tab, orient="vertical", command=self.meta_text.yview)
        self.meta_text.configure(yscrollcommand=meta_scroll.set)
        self.meta_text.grid(row=1, column=0, sticky="nsew")
        meta_scroll.grid(row=1, column=1, sticky="ns")
        self.meta_text.insert("1.0", tr("meta.empty"))
        self.meta_text.config(state="disabled")

        console_tab.columnconfigure(0, weight=1)
        console_tab.rowconfigure(0, weight=1)
        self.console_text = tk.Text(console_tab, wrap="word", font=("Consolas", 9), bg="#f8fbf8", relief="flat", padx=10, pady=10)
        console_scroll = ttk.Scrollbar(console_tab, orient="vertical", command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=console_scroll.set)
        self.console_text.grid(row=0, column=0, sticky="nsew")
        console_scroll.grid(row=0, column=1, sticky="ns")
        self.console_text.tag_configure("time", font=("Consolas", 9, "bold"), foreground="#203827")
        self.console_text.tag_configure("event", foreground="#33443a")
        self._render_console_text()
        self.console_text.config(state="disabled")

        preview_tab.columnconfigure(0, weight=1)
        preview_tab.rowconfigure(0, weight=1)
        self.large_preview_label = ttk.Label(preview_tab, text=tr("preview.empty"), anchor="center")
        self.large_preview_label.grid(row=0, column=0, sticky="nsew")
        preview_tab.bind("<Configure>", lambda _event: self._refresh_large_preview())
        right_book.bind("<<NotebookTabChanged>>", lambda _event: self._refresh_large_preview(), add="+")

        self._right_info_tabs = [
            (diagnosis_tab, "right.diagnosis"),
            (preview_tab, "right.preview"),
            (meta_tab, "right.properties"),
            (console_tab, "right.console"),
        ]
        for tab, key in self._right_info_tabs:
            right_book.add(tab, text=tr(key))

        status = ttk.Label(body_shell, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", pady=(10, 0))
        self._refresh_language_texts()

    def _apply_initial_layout(self) -> None:
        try:
            width = self.main_pane.winfo_width()
            if width < 1100:
                self.root.after(80, self._apply_initial_layout)
                return
            sash = min(max(620, int(width * 0.56)), max(620, width - 520))
            self.main_pane.sashpos(0, sash)
        except Exception:
            pass

    def _install_drag_drop(self) -> None:
        try:
            self.drop_target = install_drop_target(self.root, self._handle_dropped_paths)
            self._log_console("drag and drop ready")
        except Exception as exc:
            self._log_console(f"drag and drop init failed: {exc}")

    def _on_close(self) -> None:
        self._begin_close_sequence()

    def _begin_close_sequence(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            if self.drop_target is not None:
                self.drop_target.uninstall()
        except Exception as exc:
            self._log_console(f"drag and drop cleanup failed during close: {exc}")
        try:
            shutdown_native_gpu_server()
        except Exception as exc:
            self._log_console(f"native gpu cleanup failed during close: {exc}")
        try:
            splash = SplashScreen(self.root, min_ms=650)
        except Exception:
            self.root.after(80, self.root.destroy)
            return

        def _finish_close() -> None:
            try:
                splash.close_now()
            finally:
                self.root.destroy()

        self.root.after(760, _finish_close)

    def open_author_website(self) -> None:
        url = "https://helloalp.top/tools/shapeyourphoto"
        try:
            if not webbrowser.open(url):
                raise RuntimeError("system browser returned false")
        except Exception as exc:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                copied = f"\n{tr('contact.copied')}"
            except Exception:
                copied = ""
            messagebox.showerror(tr("dialog.help_title"), f"{url}{copied}", parent=self.root)

    def show_help_website_info(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(tr("dialog.help_title"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        outer = ttk.Frame(dialog, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=tr("dialog.help_body"), wraplength=360, justify="left").pack(anchor="w")
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text=tr("action.open_website"), command=lambda: (dialog.destroy(), self.open_author_website())).pack(side="left")
        ttk.Button(buttons, text=tr("help.faq"), command=lambda: (dialog.destroy(), self.open_faq_page())).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text=tr("help.contact"), command=lambda: (dialog.destroy(), self.show_contact_author_window())).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text=tr("action.close"), command=dialog.destroy).pack(side="right")
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + max(40, (self.root.winfo_width() - dialog.winfo_width()) // 2)
        y = self.root.winfo_rooty() + max(40, (self.root.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")

    def open_faq_page(self) -> None:
        url = "https://helloalp.top/tools/shapeyourphoto/articles/faq.html"
        try:
            if not webbrowser.open(url):
                raise RuntimeError("system browser returned false")
        except Exception:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                messagebox.showinfo(tr("help.faq"), tr("contact.copied"), parent=self.root)
            except Exception:
                messagebox.showinfo(tr("help.faq"), url, parent=self.root)

    def show_contact_author_window(self) -> None:
        email = "master@helloalp.top"
        dialog = tk.Toplevel(self.root)
        dialog.title(tr("contact.title"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(640, 520)
        outer = ttk.Frame(dialog, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)
        ttk.Label(outer, text=tr("contact.title"), font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text=tr("contact.intro"), wraplength=580, justify="left").grid(row=1, column=0, sticky="w", pady=(6, 10))
        ttk.Label(outer, text=f"{tr('contact.email')}: {email}").grid(row=2, column=0, sticky="w")
        ttk.Label(outer, text=tr("contact.template"), font=("Microsoft YaHei UI", 10, "bold")).grid(row=3, column=0, sticky="w", pady=(12, 4))
        text_frame = ttk.Frame(outer)
        text_frame.grid(row=4, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        template_text = tk.Text(text_frame, height=10, wrap="word", font=("Microsoft YaHei UI", 10), padx=8, pady=8)
        template_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=template_text.yview)
        template_text.configure(yscrollcommand=template_scroll.set)
        template_text.grid(row=0, column=0, sticky="nsew")
        template_scroll.grid(row=0, column=1, sticky="ns")
        template_text.insert("1.0", tr("contact.template_body"))
        ttk.Label(outer, text=tr("contact.extra"), font=("Microsoft YaHei UI", 10, "bold")).grid(row=5, column=0, sticky="w", pady=(12, 4))
        extra_text = tk.Text(outer, height=5, wrap="word", font=("Microsoft YaHei UI", 10), padx=8, pady=8)
        extra_text.grid(row=6, column=0, sticky="ew")
        placeholder = tr("contact.extra_placeholder")
        placeholder_active = tk.BooleanVar(value=True)

        def _show_placeholder() -> None:
            placeholder_active.set(True)
            extra_text.configure(fg="#7f8a82")
            extra_text.delete("1.0", "end")
            extra_text.insert("1.0", placeholder)

        def _hide_placeholder() -> None:
            if placeholder_active.get():
                placeholder_active.set(False)
                extra_text.configure(fg="#1f3527")
                extra_text.delete("1.0", "end")

        def _on_extra_focus_in(_event=None) -> None:
            _hide_placeholder()

        def _on_extra_focus_out(_event=None) -> None:
            if not extra_text.get("1.0", "end").strip():
                _show_placeholder()

        _show_placeholder()
        extra_text.bind("<FocusIn>", _on_extra_focus_in)
        extra_text.bind("<FocusOut>", _on_extra_focus_out)
        status_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=status_var).grid(row=7, column=0, sticky="w", pady=(8, 0))

        def composed_body() -> str:
            template = template_text.get("1.0", "end").strip()
            extra = "" if placeholder_active.get() else extra_text.get("1.0", "end").strip()
            if extra:
                return f"{template}\n\n{tr('contact.extra')}:\n{extra}"
            return template

        def copy_text(value: str) -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            status_var.set(tr("contact.copied"))

        def send_mail() -> None:
            subject = quote("ShapeYourPhoto feedback")
            body = quote(composed_body())
            url = f"mailto:{email}?subject={subject}&body={body}"
            try:
                if not webbrowser.open(url):
                    raise RuntimeError("open failed")
            except Exception:
                status_var.set(tr("contact.open_failed"))

        actions = ttk.Frame(outer)
        actions.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text=tr("contact.send"), command=send_mail).pack(side="left")
        ttk.Button(actions, text=tr("contact.copy_template"), command=lambda: copy_text(composed_body())).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text=tr("contact.copy_email"), command=lambda: copy_text(email)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text=tr("action.close"), command=dialog.destroy).pack(side="right")
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + max(40, (self.root.winfo_width() - dialog.winfo_width()) // 2)
        y = self.root.winfo_rooty() + max(40, (self.root.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")

    def show_stats(self) -> None:
        show_stats_dialog(self.root, self.stats)

    def open_format_conversion(self) -> None:
        targets = self.resolve_conversion_targets()
        if not targets:
            current = self._current_path()
            if current is not None and current in self.image_paths and current.exists():
                targets = [current]
        if not targets:
            messagebox.showinfo(tr("format.title"), tr("format.no_selection"), parent=self.root)
            self._log_console("format conversion skipped: no current list targets")
            return
        self._log_console(f"format conversion dialog opened: count={len(targets)}")
        show_format_conversion_dialog(self.root, targets, log_callback=self._log_console)

    def export_logs_for_support(self) -> None:
        try:
            path = export_logs_bundle(self.console.dump())
        except Exception as exc:
            messagebox.showerror(tr("log.export"), str(exc), parent=self.root)
            self._log_console(f"log export failed: {exc}")
            return
        self._log_console(f"log bundle exported: {path}")
        messagebox.showinfo(tr("log.export"), tr("log.export_done").format(path=path), parent=self.root)

    def open_settings_panel(self, initial_tab: str | None = None) -> None:
        def _apply_settings(settings: AppSettings) -> bool:
            try:
                save_app_settings(settings, report_warning=lambda message: self._log_console(message))
            except Exception as exc:
                messagebox.showerror("保存失败", f"应用设置保存失败：\n{exc}")
                self._log_console(f"settings save failed: {exc}")
                return False
            self.settings = settings
            set_current_language(self.settings.language)
            self.console.set_time_mode(self.settings.console_time_mode)
            self.console.set_log_language_mode(getattr(self.settings, "log_language_mode", "follow_ui"))
            cleanup_old_logs(getattr(self.settings, "log_retention_days", 30))
            self._configure_style()
            self._refresh_language_texts()
            if self.image_paths:
                current_path = self._current_path()
                self.refresh_tree()
                if current_path is not None:
                    self._select_path(current_path)
            self.status_var.set(tr("settings.saved_keep_open"))
            self._log_console(
                "settings updated: "
                f"prefix={','.join(self.settings.scan_ignore_prefixes)} | "
                f"suffix={','.join(self.settings.scan_ignore_suffixes)} | "
                f"contains={','.join(self.settings.scan_ignore_contains)} | "
                f"default_scan={self.settings.default_scan_mode} | "
                f"repair_summary_filter={self.settings.repair_summary_default_filter} | "
                f"analysis_concurrency={self.settings.analysis_concurrency_mode}:{self.settings.analysis_custom_workers or 'auto'} | "
                f"gpu={self.settings.gpu_acceleration_mode} | "
                f"console_time={self.settings.console_time_mode} | theme={self.settings.theme_id} | "
                f"density={self.settings.ui_density} | language={self.settings.language}"
            )
            return True

        show_app_settings_dialog(
            self.root,
            self.settings,
            update_check_callback=self.check_updates_now,
            apply_callback=_apply_settings,
            initial_tab=initial_tab,
        )
