from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

from task_state import TaskManager
from ui.display_names import display_name
from ui.language import tr
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window, prepare_dialog_window


@dataclass(frozen=True)
class CleanupReviewEntry:
    image_path: Path
    display_name: str
    reason_code: str
    reason_text: str
    severity: str
    confidence: float


@dataclass(frozen=True)
class CleanupReviewResult:
    action: str
    chosen_paths: list[Path]


class CleanupReviewDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, entries: list[CleanupReviewEntry]) -> None:
        super().__init__(parent)
        prepare_dialog_window(
            self,
            parent,
            title=app_window_title(tr("cleanup.title")),
            min_width=980,
            min_height=640,
        )
        self.protocol("WM_DELETE_WINDOW", self._skip)
        self.result: CleanupReviewResult | None = None
        self._entries = entries
        self._vars = [tk.BooleanVar(value=False) for _ in entries]
        self._status_vars = [tk.StringVar(value=tr("cleanup.pending")) for _ in entries]
        self._thumbs: list[ImageTk.PhotoImage] = []
        self._preview_queue: queue.SimpleQueue[tuple[int, ttk.Label, Image.Image | None]] = queue.SimpleQueue()
        self._task_manager = TaskManager(ui_dispatch=lambda callback: self.after(0, callback), max_workers=1)
        self._preview_stop = threading.Event()
        self._preview_generation = 0
        self._preview_tasks: list[tuple[int, ttk.Label, Path, tuple[int, int]]] = []
        self._size_notice_var = tk.StringVar(value="")
        self._hint_var = tk.StringVar(value=tr("cleanup.none_selected"))
        self._page = 0
        self._page_size = 8
        self._card_widgets: dict[int, tk.Frame] = {}

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text=tr("cleanup.intro"), wraplength=900, justify="left").grid(row=0, column=0, sticky="ew", pady=(0, 10))

        shell = ttk.Frame(outer)
        shell.grid(row=1, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(shell, highlightthickness=0, background="#fbfcfa")
        self.scrollbar = ttk.Scrollbar(shell, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.grid_shell = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.grid_shell, anchor="nw")
        self.grid_shell.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.grid_shell)

        footer = ttk.Frame(outer)
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(4, weight=1)
        ttk.Button(footer, text=tr("action.select_all"), command=self._select_all).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(footer, text=tr("action.clear_all"), command=self._unselect_all).grid(row=0, column=1, padx=(0, 10))
        self.prev_button = ttk.Button(footer, text=tr("similar.prev"), command=self._prev_page)
        self.prev_button.grid(row=0, column=2, padx=(0, 6))
        self.next_button = ttk.Button(footer, text=tr("similar.next"), command=self._next_page)
        self.next_button.grid(row=0, column=3, padx=(0, 10))
        ttk.Label(footer, textvariable=self._hint_var).grid(row=0, column=4, sticky="w")
        ttk.Label(footer, textvariable=self._size_notice_var).grid(row=0, column=5, sticky="e", padx=(10, 10))
        self.delete_button = ttk.Button(footer, text=tr("cleanup.delete_selected"), command=self._confirm_delete, state="disabled")
        self.delete_button.grid(row=0, column=6, padx=(0, 8))
        ttk.Button(footer, text=tr("action.cancel"), command=self._skip).grid(row=0, column=7)

        for variable in self._vars:
            variable.trace_add("write", lambda *_args: self._refresh_controls())
        self._render_cards()
        bind_minimum_size_notice(self, self._size_notice_var, 980, 640)
        center_window(self, 1180, 820)
        self.after(30, self._drain_preview_queue)

    def _bind_mousewheel(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event) -> str:
        self.canvas.yview_scroll((-1 if event.delta > 0 else 1) * 3, "units")
        return "break"

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=max(1, event.width))
        self.after_idle(self._render_cards)

    def _columns(self) -> int:
        width = max(720, self.canvas.winfo_width() or self.winfo_width() - 80)
        count = max(1, len(self._entries))
        if width >= 1320 and count >= 4:
            return 4
        if width >= 1040 and count >= 3:
            return 3
        if width >= 720 and count >= 2:
            return 2
        return 1

    def _preview_size(self, columns: int) -> tuple[int, int]:
        width = max(680, self.canvas.winfo_width() or self.winfo_width() - 90)
        card_width = max(300, int(width / max(1, columns)) - 28)
        preview_width = min(440, max(280, card_width - 24))
        return preview_width, max(210, int(preview_width * 0.66))

    def _render_cards(self) -> None:
        columns = self._columns()
        existing_columns = getattr(self, "_rendered_columns", None)
        if existing_columns == columns and self.grid_shell.winfo_children():
            return
        self._rendered_columns = columns
        self._preview_generation += 1
        generation = self._preview_generation
        self._preview_tasks = []
        self._thumbs.clear()
        for child in self.grid_shell.winfo_children():
            child.destroy()
        for column in range(columns):
            self.grid_shell.columnconfigure(column, weight=1)
        preview_size = self._preview_size(columns)
        start = self._page * self._page_size
        page_entries = list(enumerate(self._entries[start : start + self._page_size], start=start))
        self._card_widgets = {}
        for local_index, (index, entry) in enumerate(page_entries):
            row = local_index // columns
            column = local_index % columns
            card = self._build_card(index, entry, preview_size)
            card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        if self._preview_tasks:
            self._task_manager.submit(
                kind="preview_generation",
                name="cleanup_review_preview",
                target=lambda _record, gen=generation, tasks=list(self._preview_tasks): self._preview_worker(gen, tasks),
                exclusive=False,
            )
        self._refresh_controls()

    def _build_card(self, index: int, entry: CleanupReviewEntry, preview_size: tuple[int, int]) -> ttk.Frame:
        card = tk.Frame(self.grid_shell, padx=10, pady=10, relief="solid", bd=1, bg="#fbfcfa", cursor="hand2")
        card.columnconfigure(0, weight=1)
        self._bind_mousewheel(card)
        card.bind("<Button-1>", lambda _event, i=index: self._toggle_card(i))
        self._card_widgets[index] = card
        image_label = ttk.Label(card)
        image_label.grid(row=0, column=0, sticky="n")
        self._bind_mousewheel(image_label)
        self._preview_tasks.append((index, image_label, entry.image_path, preview_size))
        wrap = max(260, preview_size[0] - 8)
        ttk.Checkbutton(card, text=tr("cleanup.heading.pick"), variable=self._vars[index]).grid(row=1, column=0, sticky="w", pady=(8, 0))
        for row, text, font in [
            (2, entry.display_name, ("Microsoft YaHei UI", 10, "bold")),
            (3, f"{tr('cleanup.heading.severity')}: {display_name('severity', entry.severity)}", None),
            (4, f"{tr('cleanup.heading.reason')}: {self._reason_summary(entry)}", None),
        ]:
            label = tk.Label(card, text=text, font=font, bg="#fbfcfa", fg="#183326", wraplength=wrap, justify="left", anchor="w", cursor="hand2")
            label.grid(row=row, column=0, sticky="w", pady=(6 if row == 2 else 4, 0))
            label.bind("<Button-1>", lambda _event, i=index: self._toggle_card(i))
            self._bind_mousewheel(label)
        status = tk.Label(card, textvariable=self._status_vars[index], bg="#fbfcfa", fg="#183326", wraplength=wrap, anchor="w", cursor="hand2")
        status.grid(row=5, column=0, sticky="w", pady=(4, 0))
        status.bind("<Button-1>", lambda _event, i=index: self._toggle_card(i))
        self._bind_mousewheel(status)
        return card

    def _reason_summary(self, entry: CleanupReviewEntry) -> str:
        label = display_name("cleanup_reason", entry.reason_code)
        detail = entry.reason_text.strip()
        if not detail or detail == entry.reason_code or detail == label:
            return label
        if entry.reason_code in detail:
            detail = detail.replace(entry.reason_code, label)
        if detail.startswith("未知类型"):
            return label
        return f"{label}：{detail}"

    def _preview_worker(self, generation: int, tasks: list[tuple[int, ttk.Label, Path, tuple[int, int]]]) -> None:
        for index, label, path, size in tasks:
            if self._preview_stop.is_set() or generation != self._preview_generation:
                return
            self._preview_queue.put((generation, label, self._decode_preview(path, size)))

    def _drain_preview_queue(self) -> None:
        drained = 0
        try:
            while drained < 12:
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
            self.after(10 if drained >= 12 else 40, self._drain_preview_queue)

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

    def _refresh_controls(self) -> None:
        count = len([variable for variable in self._vars if variable.get()])
        self.delete_button.configure(state="normal" if count else "disabled")
        pages = max(1, (len(self._entries) + self._page_size - 1) // self._page_size)
        base = tr("cleanup.selected_hint").format(count=count) if count else tr("cleanup.none_selected")
        self._hint_var.set(f"{base}  {self._page + 1}/{pages}")
        self.prev_button.configure(state="normal" if self._page > 0 else "disabled")
        self.next_button.configure(state="normal" if self._page + 1 < pages else "disabled")
        for index, (status_var, variable) in enumerate(zip(self._status_vars, self._vars)):
            state = tr("cleanup.selected") if variable.get() else tr("cleanup.pending")
            status_var.set(f"{tr('cleanup.detail_status')}: {state}")
            card = self._card_widgets.get(index)
            if card is not None:
                card.configure(bg="#dcebdd" if variable.get() else "#fbfcfa")

    def _toggle_card(self, index: int) -> None:
        self._vars[index].set(not self._vars[index].get())

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._rendered_columns = None
            self._render_cards()

    def _next_page(self) -> None:
        if (self._page + 1) * self._page_size < len(self._entries):
            self._page += 1
            self._rendered_columns = None
            self._render_cards()

    def _select_all(self) -> None:
        for variable in self._vars:
            variable.set(True)

    def _unselect_all(self) -> None:
        for variable in self._vars:
            variable.set(False)

    def _confirm_delete(self) -> None:
        chosen_paths = [entry.image_path for entry, variable in zip(self._entries, self._vars) if variable.get()]
        if not chosen_paths:
            self._skip()
            return
        self.result = CleanupReviewResult(action="delete", chosen_paths=chosen_paths)
        self._preview_stop.set()
        self.destroy()

    def _skip(self) -> None:
        self.result = CleanupReviewResult(action="skip", chosen_paths=[])
        self._preview_stop.set()
        self.destroy()


def show_cleanup_review_dialog(parent: tk.Widget, entries: list[CleanupReviewEntry]) -> CleanupReviewResult | None:
    dialog = CleanupReviewDialog(parent, entries)
    dialog.wait_window()
    return dialog.result
