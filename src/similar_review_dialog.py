from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

from models import AnalysisResult, SimilarImageGroup
from repair_planner import get_method_labels, suggest_methods_for_result
from task_state import TaskManager
from ui.display_names import display_name, issue_display
from ui.language import tr
from ui.window_titles import app_window_title
from dialog_factory import DialogSpec, finalize_dialog_window
from window_layout import MIN_SIZE_NOTICE


FILTER_ALL = "all"
FILTER_HIGH = "high"
FILTER_MEDIUM = "medium"
FILTER_LOW = "low"
FILTER_LARGE = "large"
FILTER_BURST = "burst"


class SimilarGroupListDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        groups: list[SimilarImageGroup],
        results: dict[Path, AnalysisResult],
        cleanup_paths: set[Path],
        decision_callback: Callable[[list[SimilarImageGroup]], None],
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title(app_window_title("相似图片自动检测结果"))
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.minsize(900, 560)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._groups = groups
        self._results = results
        self._cleanup_paths = cleanup_paths
        self._decision_callback = decision_callback
        self._filter_var = tk.StringVar(value=FILTER_ALL)
        self._filter_label_var = tk.StringVar(value=tr("similar.filter.all"))
        self._selected_vars: dict[int, tk.BooleanVar] = {}
        self._thumbs: list[ImageTk.PhotoImage] = []
        self._thumbnail_queue: queue.SimpleQueue[tuple[int, ttk.Label, Image.Image | None]] = queue.SimpleQueue()
        self._task_manager = TaskManager(ui_dispatch=lambda callback: self.after(0, callback), max_workers=2)
        self._thumbnail_stop = threading.Event()
        self._thumbnail_generation = 0
        self._thumbnail_tasks: list[tuple[ttk.Label, Path, tuple[int, int]]] = []
        self._hint_var = tk.StringVar()
        self._size_notice_var = tk.StringVar(value="")

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(outer)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(4, weight=1)
        ttk.Label(toolbar, text=tr("filter.label")).grid(row=0, column=0, sticky="w")
        self._filter_labels = self._filter_label_map()
        filter_box = ttk.Combobox(
            toolbar,
            textvariable=self._filter_label_var,
            values=list(self._filter_labels.values()),
            state="readonly",
            width=18,
        )
        filter_box.grid(row=0, column=1, sticky="w", padx=(4, 12))
        filter_box.bind("<<ComboboxSelected>>", self._on_filter_selected)
        self.select_toggle_button = ttk.Button(toolbar, text=tr("action.select_all"), command=self._toggle_visible_selection)
        self.select_toggle_button.grid(row=0, column=2, padx=(0, 12))
        ttk.Label(toolbar, textvariable=self._hint_var).grid(row=0, column=4, sticky="e")

        list_shell = ttk.Frame(outer)
        list_shell.grid(row=1, column=0, sticky="nsew")
        list_shell.columnconfigure(0, weight=1)
        list_shell.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(list_shell, highlightthickness=0, background="#fbfcfa")
        self.scrollbar = ttk.Scrollbar(list_shell, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.inner)

        footer = ttk.Frame(outer)
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(1, weight=1)
        self.start_button = ttk.Button(footer, text=tr("similar.start_selection"), command=self._start_decision, state="disabled")
        self.start_button.grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self._size_notice_var).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Button(footer, text=tr("similar.skip_all"), command=self._close).grid(row=0, column=2, sticky="e")

        self._render_groups()
        finalize_dialog_window(
            self,
            parent,
            DialogSpec(
                title=self.title(),
                min_width=900,
                min_height=560,
                fallback_width=1080,
                fallback_height=720,
                modal=False,
            ),
            size_notice_var=self._size_notice_var,
        )
        self.after(30, self._drain_thumbnail_queue)

    def _filter_label_map(self) -> dict[str, str]:
        return {
            FILTER_ALL: tr("similar.filter.all"),
            FILTER_HIGH: tr("similar.filter.high"),
            FILTER_MEDIUM: tr("similar.filter.medium"),
            FILTER_LOW: tr("similar.filter.low"),
            FILTER_LARGE: tr("similar.filter.large"),
            FILTER_BURST: tr("similar.filter.burst"),
        }

    def _on_filter_selected(self, _event=None) -> None:
        reverse = {label: code for code, label in self._filter_labels.items()}
        self._filter_var.set(reverse.get(self._filter_label_var.get(), FILTER_ALL))
        self._render_groups()

    def _fit_to_screen(self, preferred_width: int, preferred_height: int) -> None:
        self.update_idletasks()
        screen_width = max(900, self.winfo_screenwidth())
        screen_height = max(620, self.winfo_screenheight())
        width = min(preferred_width, max(780, screen_width - 120))
        height = min(preferred_height, max(460, screen_height - 140))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _bind_mousewheel(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_inner_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=max(1, event.width))

    def _on_mousewheel(self, event) -> str:
        if self.canvas.winfo_exists() and self.canvas.winfo_ismapped():
            delta = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(delta * 3, "units")
        return "break"

    def _visible_groups(self) -> list[SimilarImageGroup]:
        chosen = self._filter_var.get()
        groups = [group for group in self._groups if len([path for path in group.paths if path.exists()]) >= 2]
        if chosen == FILTER_HIGH:
            return [group for group in groups if group.level == "high"]
        if chosen == FILTER_MEDIUM:
            return [group for group in groups if group.level == "medium"]
        if chosen == FILTER_LOW:
            return [group for group in groups if group.level == "low"]
        if chosen == FILTER_LARGE:
            return [group for group in groups if len(group.paths) >= 4]
        if chosen == FILTER_BURST:
            return [group for group in groups if group.possible_burst]
        return groups

    def _render_groups(self) -> None:
        self._thumbnail_generation += 1
        generation = self._thumbnail_generation
        self._thumbnail_tasks = []
        for child in self.inner.winfo_children():
            child.destroy()
        self._thumbs.clear()

        visible = self._visible_groups()
        if not visible:
            empty = ttk.Label(self.inner, text=tr("similar.empty_filter"), padding=16)
            empty.pack(anchor="w")
            self._bind_mousewheel(empty)
        for group in visible:
            if group.group_id not in self._selected_vars:
                variable = tk.BooleanVar(value=False)
                variable.trace_add("write", lambda *_args: self._update_controls())
                self._selected_vars[group.group_id] = variable
            self._build_group_card(group, generation)
        self.canvas.yview_moveto(0)
        self._update_controls()
        self.after_idle(lambda: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        if self._thumbnail_tasks:
            self._task_manager.submit(
                kind="preview_generation",
                name="similar_group_thumbs",
                target=lambda _record, gen=generation, tasks=list(self._thumbnail_tasks): self._thumbnail_worker(gen, tasks),
                exclusive=False,
            )

    def _build_group_card(self, group: SimilarImageGroup, generation: int) -> None:
        existing_paths = [path for path in group.paths if path.exists()]
        card = ttk.Frame(self.inner, padding=10, relief="solid")
        card.pack(fill="x", expand=False, pady=(0, 10), padx=(0, 8))
        card.columnconfigure(1, weight=1)
        self._bind_mousewheel(card)
        self._bind_group_toggle(card, group.group_id)

        check = ttk.Checkbutton(card, variable=self._selected_vars[group.group_id])
        check.grid(row=0, column=0, rowspan=4, sticky="n", padx=(0, 8))
        self._bind_mousewheel(check)

        level_label = {"high": tr("similar.level.high"), "medium": tr("similar.level.medium"), "low": tr("similar.level.low")}.get(group.level, group.level)
        title = ttk.Label(card, text=tr("similar.group_title").format(id=group.group_id, count=len(existing_paths), level=level_label), font=("Microsoft YaHei UI", 10, "bold"))
        title.grid(row=0, column=1, sticky="w")
        self._bind_mousewheel(title)
        self._bind_group_toggle(title, group.group_id)

        thumbs_frame = ttk.Frame(card)
        thumbs_frame.grid(row=1, column=1, sticky="w", pady=(8, 0))
        self._bind_mousewheel(thumbs_frame)
        self._bind_group_toggle(thumbs_frame, group.group_id)
        preview_paths = existing_paths[:6]
        for path in preview_paths:
            label = ttk.Label(thumbs_frame)
            label.pack(side="left", padx=(0, 6))
            self._bind_mousewheel(label)
            self._bind_group_toggle(label, group.group_id)
            self._thumbnail_tasks.append((label, path, (112, 78)))
        if len(existing_paths) > len(preview_paths):
            more = ttk.Label(thumbs_frame, text=tr("similar.more_count").format(count=len(existing_paths) - len(preview_paths)))
            more.pack(side="left", padx=(4, 0))
            self._bind_mousewheel(more)
            self._bind_group_toggle(more, group.group_id)

        marker_count = len([path for path in existing_paths if path in self._cleanup_paths])
        marker = f" | {tr('similar.contains_cleanup').format(count=marker_count)}" if marker_count else ""
        reason = ttk.Label(card, text=tr("similar.reason_line").format(score=f"{group.similarity:.2f}", reason=group.reason, marker=marker), wraplength=900)
        reason.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        self._bind_mousewheel(reason)
        self._bind_group_toggle(reason, group.group_id)

        filenames = "、".join(path.name + (f" [{tr('similar.cleanup_marker')}]" if path in self._cleanup_paths else "") for path in existing_paths)
        names = ttk.Label(card, text=filenames, wraplength=900)
        names.grid(row=3, column=1, sticky="ew", pady=(6, 0))
        self._bind_mousewheel(names)
        self._bind_group_toggle(names, group.group_id)

    def _bind_group_toggle(self, widget: tk.Widget, group_id: int) -> None:
        widget.bind("<Button-1>", lambda event, gid=group_id: self._toggle_group_selection_from_click(event, gid), add="+")

    def _toggle_group_selection_from_click(self, _event, group_id: int) -> str:
        variable = self._selected_vars.get(group_id)
        if variable is not None:
            variable.set(not variable.get())
            self._update_controls()
        return "break"

    def _visible_all_selected(self) -> bool:
        visible = self._visible_groups()
        return bool(visible) and all(
            self._selected_vars.get(group.group_id) and self._selected_vars[group.group_id].get()
            for group in visible
        )

    def _toggle_visible_selection(self) -> None:
        target = not self._visible_all_selected()
        for group in self._visible_groups():
            if group.group_id in self._selected_vars:
                self._selected_vars[group.group_id].set(target)
        self._update_controls()

    def _selected_groups(self) -> list[SimilarImageGroup]:
        selected_ids = {group_id for group_id, variable in self._selected_vars.items() if variable.get()}
        return [group for group in self._groups if group.group_id in selected_ids and len([path for path in group.paths if path.exists()]) >= 2]

    def _update_controls(self) -> None:
        selected_count = len(self._selected_groups())
        visible_count = len(self._visible_groups())
        self.start_button.configure(state="normal" if selected_count else "disabled")
        self._hint_var.set(tr("similar.hint").format(visible=visible_count, selected=selected_count))
        if hasattr(self, "select_toggle_button"):
            self.select_toggle_button.configure(
                text=tr("action.unselect_all_short") if self._visible_all_selected() else tr("action.select_all")
            )

    def _start_decision(self) -> None:
        selected = self._selected_groups()
        if not selected:
            self._update_controls()
            return
        self._thumbnail_stop.set()
        self.destroy()
        self._decision_callback(selected)

    def _thumbnail_worker(self, generation: int, tasks: list[tuple[ttk.Label, Path, tuple[int, int]]]) -> None:
        for label, path, size in tasks:
            if self._thumbnail_stop.is_set() or generation != self._thumbnail_generation:
                return
            self._thumbnail_queue.put((generation, label, self._decode_thumbnail(path, size)))

    def _drain_thumbnail_queue(self) -> None:
        drained = 0
        try:
            while drained < 30:
                generation, label, image = self._thumbnail_queue.get_nowait()
                if generation == self._thumbnail_generation and image is not None and label.winfo_exists():
                    thumb = ImageTk.PhotoImage(image)
                    self._thumbs.append(thumb)
                    label.configure(image=thumb)
                drained += 1
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            alive = self.winfo_exists()
        except tk.TclError:
            return
        if not self._thumbnail_stop.is_set() and alive:
            self.after(10 if drained >= 30 else 40, self._drain_thumbnail_queue)

    def _decode_thumbnail(self, path: Path, size: tuple[int, int]) -> Image.Image | None:
        try:
            with Image.open(path) as img:
                try:
                    img.draft("RGB", (max(1, size[0] * 2), max(1, size[1] * 2)))
                except Exception:
                    pass
                image = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return None
        image.thumbnail(size)
        thumb = Image.new("RGB", size, (237, 242, 238))
        thumb.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
        return thumb

    def _close(self) -> None:
        self._thumbnail_stop.set()
        self.destroy()


class SimilarGroupDecisionDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        groups: list[SimilarImageGroup],
        results: dict[Path, AnalysisResult],
        cleanup_paths: set[Path],
        delete_callback: Callable[[Path, SimilarImageGroup], bool],
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title(app_window_title(tr("similar.decision_title")))
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.minsize(1120, 780)
        self.protocol("WM_DELETE_WINDOW", self._skip_all)

        self._groups = groups
        self._results = results
        self._cleanup_paths = cleanup_paths
        self._delete_callback = delete_callback
        self._group_index = 0
        self._page_start = 0
        self._thumbs: list[ImageTk.PhotoImage] = []
        self._preview_queue: queue.SimpleQueue[tuple[int, ttk.Label, Image.Image | None]] = queue.SimpleQueue()
        self._task_manager = TaskManager(ui_dispatch=lambda callback: self.after(0, callback), max_workers=2)
        self._preview_stop = threading.Event()
        self._preview_generation = 0
        self._preview_tasks: list[tuple[ttk.Label, Path, tuple[int, int]]] = []
        self._selected_paths: set[Path] = set()
        self._size_hint_var = tk.StringVar()
        self._title_var = tk.StringVar()
        self._reason_var = tk.StringVar()

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=0)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, textvariable=self._title_var, style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, textvariable=self._reason_var, wraplength=920).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Label(outer, textvariable=self._size_hint_var, foreground="#8a4a00").grid(row=2, column=0, sticky="w", pady=(0, 6))

        self.grid_canvas = tk.Canvas(outer, highlightthickness=0, background="#fbfcfa")
        self.grid_scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.grid_canvas.yview)
        self.grid_canvas.configure(yscrollcommand=self.grid_scrollbar.set)
        self.grid_canvas.grid(row=3, column=0, sticky="nsew")
        self.grid_scrollbar.grid(row=3, column=1, sticky="ns")

        self.grid_shell = ttk.Frame(self.grid_canvas)
        self.grid_window_id = self.grid_canvas.create_window((0, 0), window=self.grid_shell, anchor="nw")
        self.grid_shell.bind("<Configure>", self._on_grid_inner_configure)
        self.grid_canvas.bind("<Configure>", self._on_grid_canvas_configure)
        self._bind_grid_mousewheel(self.grid_canvas)
        self._bind_grid_mousewheel(self.grid_shell)

        nav_row = ttk.Frame(outer)
        nav_row.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.prev_button = ttk.Button(nav_row, text=tr("similar.prev"), command=self._prev_page)
        self.next_button = ttk.Button(nav_row, text=tr("similar.next"), command=self._next_page)
        self.prev_button.pack(side="left")
        self.next_button.pack(side="left", padx=6)
        self.skip_button = ttk.Button(nav_row, text=tr("similar.skip_group"), command=self._skip_group)
        self.skip_button.pack(side="right")
        ttk.Button(nav_row, text=tr("similar.skip_remaining"), command=self._skip_all).pack(side="right", padx=6)
        ttk.Button(nav_row, text=tr("similar.finish"), command=self._skip_all).pack(side="right", padx=(0, 6))

        self.bind("<Configure>", lambda _event: self._update_size_hint())
        self._render_group()
        finalize_dialog_window(
            self,
            parent,
            DialogSpec(
                title=app_window_title(tr("similar.decision_title")),
                min_width=1120,
                min_height=780,
                fallback_width=1180,
                fallback_height=900,
                modal=False,
            ),
            size_notice_var=self._size_hint_var,
        )
        self.after(30, self._drain_preview_queue)

    def _fit_to_screen(self, preferred_width: int, preferred_height: int) -> None:
        self.update_idletasks()
        screen_width = max(900, self.winfo_screenwidth())
        screen_height = max(680, self.winfo_screenheight())
        width = min(preferred_width, max(900, screen_width - 80))
        height = min(preferred_height, max(640, screen_height - 80))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _bind_grid_mousewheel(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_grid_mousewheel, add="+")

    def _on_grid_inner_configure(self, _event=None) -> None:
        self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))

    def _on_grid_canvas_configure(self, event) -> None:
        self.grid_canvas.itemconfigure(self.grid_window_id, width=max(1, event.width))

    def _on_grid_mousewheel(self, event) -> str:
        if self.grid_canvas.winfo_exists() and self.grid_canvas.winfo_ismapped():
            delta = -1 if event.delta > 0 else 1
            self.grid_canvas.yview_scroll(delta * 3, "units")
        return "break"

    def _active_group(self) -> SimilarImageGroup | None:
        while self._group_index < len(self._groups):
            group = self._groups[self._group_index]
            group.paths[:] = [path for path in group.paths if path.exists()]
            if len(group.paths) >= 2:
                return group
            self._group_index += 1
            self._page_start = 0
        return None

    def _render_group(self) -> None:
        self._preview_generation += 1
        generation = self._preview_generation
        self._preview_tasks = []
        for child in self.grid_shell.winfo_children():
            child.destroy()
        self._thumbs.clear()
        group = self._active_group()
        if group is None:
            self.destroy()
            return

        self._title_var.set(tr("similar.decision_group_title").format(id=group.group_id, index=self._group_index + 1, total=len(self._groups), count=len(group.paths)))
        self._reason_var.set(group.reason)
        columns = self._preview_columns(len(group.paths))
        rows = 1 if len(group.paths) <= columns else 2
        max_visible = max(1, columns * rows)
        page_paths = group.paths[self._page_start : self._page_start + max_visible]
        columns = min(columns, max(1, len(page_paths)))
        for row in range(rows):
            self.grid_shell.rowconfigure(row, weight=1)
        for column in range(columns):
            self.grid_shell.columnconfigure(column, weight=1)

        for index, path in enumerate(page_paths):
            row = index // columns
            column = index % columns
            self._build_image_card(self.grid_shell, group, path, columns=columns).grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        if self._preview_tasks:
            self._task_manager.submit(
                kind="preview_generation",
                name="similar_decision_preview",
                target=lambda _record, gen=generation, tasks=list(self._preview_tasks): self._preview_worker(gen, tasks),
                exclusive=False,
            )

        has_pages = len(group.paths) > max_visible
        self.prev_button.configure(state="normal" if has_pages and self._page_start > 0 else "disabled")
        self.next_button.configure(state="normal" if has_pages and self._page_start + max_visible < len(group.paths) else "disabled")
        self.skip_button.configure(text=tr("similar.finish_all") if self._group_index >= len(self._groups) - 1 else tr("similar.skip_group"))
        self.grid_canvas.yview_moveto(0)
        self.after_idle(lambda: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        self._update_size_hint()

    def _preview_columns(self, count: int) -> int:
        width = max(900, self.grid_canvas.winfo_width() or self.winfo_width() - 80)
        if count <= 1:
            return 1
        if width >= 1320 and count >= 4:
            return 4
        if width >= 1040 and count >= 3:
            return 3
        if width >= 720:
            return 2
        return 1

    def _preview_size(self, columns: int) -> tuple[int, int]:
        width = max(680, self.grid_canvas.winfo_width() or self.winfo_width() - 90)
        card_width = max(260, int(width / max(1, columns)) - 36)
        preview_width = min(430, max(260, card_width - 24))
        return preview_width, max(190, int(preview_width * 0.62))

    def _build_image_card(self, parent: tk.Widget, group: SimilarImageGroup, path: Path, *, columns: int) -> ttk.Frame:
        card = ttk.Frame(parent, padding=10, relief="solid")
        card.columnconfigure(0, weight=1)
        self._bind_grid_mousewheel(card)
        self._bind_image_toggle(card, path)
        image_label = ttk.Label(card)
        image_label.grid(row=0, column=0, sticky="n")
        self._bind_grid_mousewheel(image_label)
        self._bind_image_toggle(image_label, path)
        preview_size = self._preview_size(columns)
        self._preview_tasks.append((image_label, path, preview_size))
        wrap = max(240, preview_size[0] - 10)
        name_label = ttk.Label(card, text=path.name, font=("Microsoft YaHei UI", 10, "bold"), wraplength=wrap)
        name_label.grid(row=1, column=0, sticky="w", pady=(8, 2))
        self._bind_grid_mousewheel(name_label)
        self._bind_image_toggle(name_label, path)
        summary_label = ttk.Label(card, text=self._analysis_summary(path), wraplength=wrap)
        summary_label.grid(row=2, column=0, sticky="w")
        self._bind_grid_mousewheel(summary_label)
        self._bind_image_toggle(summary_label, path)
        selection_label = ttk.Label(card, text=tr("tree.selected") if path in self._selected_paths else tr("tree.pending"))
        selection_label.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self._bind_grid_mousewheel(selection_label)
        self._bind_image_toggle(selection_label, path)
        delete_button = ttk.Button(card, text=tr("similar.delete_this"), command=lambda p=path, g=group: self._delete_path(p, g))
        delete_button.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        return card

    def _bind_image_toggle(self, widget: tk.Widget, path: Path) -> None:
        widget.bind("<Button-1>", lambda event, p=path: self._toggle_image_selection(event, p), add="+")

    def _toggle_image_selection(self, _event, path: Path) -> str:
        if path in self._selected_paths:
            self._selected_paths.remove(path)
        else:
            self._selected_paths.add(path)
        self._render_group()
        return "break"

    def _analysis_summary(self, path: Path) -> str:
        result = self._results.get(path)
        cleanup_marker = " | 可能不适合保留" if path in self._cleanup_paths else ""
        if result is None:
            return f"尚无分析结果{cleanup_marker}"
        issues = "、".join(issue_display(issue) for issue in result.issues[:3]) if result.issues else "无明显问题"
        methods = "、".join(get_method_labels(suggest_methods_for_result(result))) or "暂无明确推荐"
        portrait = "人像" if result.portrait_likely else "非人像"
        return (
            f"风险 {result.overall_score:.2f} | {portrait} | 场景={display_name('scene_type', result.scene_type)}{cleanup_marker}\n"
            f"问题：{issues}\n"
            f"建议：{methods}"
        )

    def _delete_path(self, path: Path, group: SimilarImageGroup) -> None:
        if self._delete_callback(path, group):
            self._selected_paths.discard(path)
            group.paths[:] = [item for item in group.paths if item != path and item.exists()]
            if self._page_start >= len(group.paths):
                self._page_start = max(0, len(group.paths) - 4)
            self._render_group()

    def _prev_page(self) -> None:
        group = self._active_group()
        step = max(1, self._preview_columns(len(group.paths)) if group is not None else 2)
        self._page_start = max(0, self._page_start - step)
        self._render_group()

    def _next_page(self) -> None:
        group = self._active_group()
        if group is None:
            return
        step = max(1, self._preview_columns(len(group.paths)))
        self._page_start = min(max(0, len(group.paths) - 1), self._page_start + step)
        self._render_group()

    def _skip_group(self) -> None:
        self._group_index += 1
        self._page_start = 0
        self._render_group()

    def _skip_all(self) -> None:
        self._preview_stop.set()
        self.destroy()

    def _update_size_hint(self) -> None:
        if self.winfo_width() < 1120 or self.winfo_height() < 820:
            if self.winfo_width() <= 1128 and self.winfo_height() <= 788:
                self._size_hint_var.set(MIN_SIZE_NOTICE)
            else:
                self._size_hint_var.set("当前窗口空间偏小，图片区域可滚动；删除按钮和底部操作栏会保留在可达位置。")
        else:
            self._size_hint_var.set("")

    def _preview_worker(self, generation: int, tasks: list[tuple[ttk.Label, Path, tuple[int, int]]]) -> None:
        for label, path, size in tasks:
            if self._preview_stop.is_set() or generation != self._preview_generation:
                return
            self._preview_queue.put((generation, label, self._decode_preview(path, size)))

    def _drain_preview_queue(self) -> None:
        drained = 0
        try:
            while drained < 10:
                generation, label, image = self._preview_queue.get_nowait()
                if generation == self._preview_generation and image is not None and label.winfo_exists():
                    thumb = ImageTk.PhotoImage(image)
                    self._thumbs.append(thumb)
                    label.configure(image=thumb)
                drained += 1
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            alive = self.winfo_exists()
        except tk.TclError:
            return
        if not self._preview_stop.is_set() and alive:
            self.after(10 if drained >= 10 else 40, self._drain_preview_queue)

    def _decode_preview(self, path: Path, size: tuple[int, int]) -> Image.Image | None:
        try:
            with Image.open(path) as img:
                try:
                    img.draft("RGB", (max(1, size[0] * 2), max(1, size[1] * 2)))
                except Exception:
                    pass
                image = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return None
        image.thumbnail(size)
        canvas = Image.new("RGB", size, (237, 242, 238))
        canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
        return canvas


def show_similar_group_list_dialog(
    parent: tk.Widget,
    groups: list[SimilarImageGroup],
    results: dict[Path, AnalysisResult],
    cleanup_paths: set[Path],
    decision_callback: Callable[[list[SimilarImageGroup]], None],
) -> None:
    dialog = SimilarGroupListDialog(parent, groups, results, cleanup_paths, decision_callback)
    dialog.wait_window()


def show_similar_group_decision_dialog(
    parent: tk.Widget,
    groups: list[SimilarImageGroup],
    results: dict[Path, AnalysisResult],
    cleanup_paths: set[Path],
    delete_callback: Callable[[Path, SimilarImageGroup], bool],
) -> None:
    dialog = SimilarGroupDecisionDialog(parent, groups, results, cleanup_paths, delete_callback)
    dialog.wait_window()
