from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

from ui.display_names import display_name
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


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
        self.title(app_window_title("不适合保留的图片"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(980, 640)
        self.protocol("WM_DELETE_WINDOW", self._skip)

        self.result: CleanupReviewResult | None = None
        self._entries = entries
        self._vars = [tk.BooleanVar(value=False) for _ in entries]
        self._item_lookup: dict[str, int] = {}
        self._thumbs: list[ImageTk.PhotoImage | None] = []
        self._size_notice_var = tk.StringVar(value="")
        self._detail_var = tk.StringVar(value="选择一张图片后，可在这里查看完整原因。")

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(
            outer,
            text="以下图片可能不适合继续保留。请核对后再选择是否删除。",
            wraplength=900,
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        list_shell = ttk.Frame(outer)
        list_shell.grid(row=1, column=0, sticky="nsew")
        list_shell.columnconfigure(0, weight=1)
        list_shell.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            list_shell,
            columns=("pick", "severity", "confidence", "reason"),
            show=("tree", "headings"),
            selectmode="extended",
            height=10,
        )
        self.tree.heading("#0", text="缩略图 / 文件名")
        self.tree.column("#0", width=250, anchor="w")
        self.tree.heading("pick", text="选择")
        self.tree.column("pick", width=70, anchor="center")
        self.tree.heading("severity", text="严重程度")
        self.tree.column("severity", width=72, anchor="center")
        self.tree.heading("confidence", text="置信度")
        self.tree.column("confidence", width=72, anchor="center")
        self.tree.heading("reason", text="主要原因")
        self.tree.column("reason", width=420, anchor="w")
        scroll = ttk.Scrollbar(list_shell, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(list_shell, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._refresh_detail())

        for index, entry in enumerate(entries):
            checked = "待定"
            thumb = self._build_thumbnail(entry.image_path)
            reason = self._reason_summary(entry)
            self._thumbs.append(thumb)
            item_id = self.tree.insert(
                "",
                "end",
                text=entry.display_name,
                image=thumb,
                values=(
                    checked,
                    display_name("severity", entry.severity),
                    f"{entry.confidence:.2f}",
                    reason,
                ),
            )
            self._item_lookup[item_id] = index

        detail = ttk.Label(
            outer,
            textvariable=self._detail_var,
            wraplength=900,
            justify="left",
        )
        detail.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        action_row = ttk.Frame(outer)
        action_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(action_row, text="勾选当前", command=self._select_current).pack(side="left")
        ttk.Button(action_row, text="切换所选", command=self._toggle_selected).pack(side="left", padx=6)
        ttk.Button(action_row, text="全选", command=self._select_all).pack(side="left")
        ttk.Button(action_row, text="取消全选", command=self._unselect_all).pack(side="left", padx=6)
        self._hint_var = tk.StringVar(value="当前没有选择图片，可以直接取消。")
        ttk.Label(action_row, textvariable=self._hint_var).pack(side="right")

        button_row = ttk.Frame(outer)
        button_row.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.delete_button = ttk.Button(
            button_row,
            text="删除选择的图片",
            command=self._confirm_delete,
            state="disabled",
        )
        self.delete_button.pack(side="left")
        ttk.Label(button_row, textvariable=self._size_notice_var).pack(side="left", padx=(12, 0))
        ttk.Button(button_row, text="取消", command=self._skip).pack(side="right")

        bind_minimum_size_notice(self, self._size_notice_var, 860, 520)
        center_window(self, 1120, 780)

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

    def _refresh_detail(self) -> None:
        index = self._current_index()
        if index is None:
            self._detail_var.set("选择一张图片后，可在这里查看完整原因。")
            return
        entry = self._entries[index]
        self._detail_var.set(
            f"{entry.display_name}\n"
            f"状态：{'已选' if self._vars[index].get() else '待定'} | "
            f"严重程度：{display_name('severity', entry.severity)} | "
            f"置信度：{entry.confidence:.2f}\n"
            f"主要原因：{self._reason_summary(entry)}"
        )

    def _build_thumbnail(self, path: Path, size: tuple[int, int] = (90, 68)) -> ImageTk.PhotoImage | None:
        try:
            with Image.open(path) as img:
                image = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return None

        image.thumbnail(size)
        thumb = Image.new("RGB", size, (237, 242, 238))
        offset_x = (size[0] - image.width) // 2
        offset_y = (size[1] - image.height) // 2
        thumb.paste(image, (offset_x, offset_y))
        return ImageTk.PhotoImage(thumb)

    def _current_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self._item_lookup.get(selection[0])

    def _selected_indices(self) -> list[int]:
        return [self._item_lookup[item_id] for item_id in self.tree.selection() if item_id in self._item_lookup]

    def _refresh_checks(self) -> None:
        for item_id, index in self._item_lookup.items():
            values = list(self.tree.item(item_id, "values"))
            if values:
                values[0] = "已选" if self._vars[index].get() else "待定"
                self.tree.item(item_id, values=tuple(values))
        selected_count = len([variable for variable in self._vars if variable.get()])
        if selected_count > 0:
            self.delete_button.configure(state="normal")
            self._hint_var.set(f"已选择 {selected_count} 张图片。")
        else:
            self.delete_button.configure(state="disabled")
            self._hint_var.set("当前没有选择图片，可以直接取消。")
        self._refresh_detail()

    def _on_tree_click(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id:
            return
        self.tree.selection_set(item_id)
        index = self._item_lookup.get(item_id)
        if index is None:
            return
        if column == "#1":
            self._vars[index].set(not self._vars[index].get())
            self._refresh_checks()

    def _select_current(self) -> None:
        index = self._current_index()
        if index is None:
            return
        self._vars[index].set(True)
        self._refresh_checks()

    def _toggle_selected(self) -> None:
        indices = self._selected_indices()
        if not indices:
            return
        target_state = not self._vars[indices[0]].get()
        for index in indices:
            self._vars[index].set(target_state)
        self._refresh_checks()

    def _select_all(self) -> None:
        for variable in self._vars:
            variable.set(True)
        self._refresh_checks()

    def _unselect_all(self) -> None:
        for variable in self._vars:
            variable.set(False)
        self._refresh_checks()

    def _confirm_delete(self) -> None:
        chosen_paths = [entry.image_path for entry, variable in zip(self._entries, self._vars) if variable.get()]
        if not chosen_paths:
            self._skip()
            return
        self.result = CleanupReviewResult(action="delete", chosen_paths=chosen_paths)
        self.destroy()

    def _skip(self) -> None:
        self.result = CleanupReviewResult(action="skip", chosen_paths=[])
        self.destroy()


def show_cleanup_review_dialog(parent: tk.Widget, entries: list[CleanupReviewEntry]) -> CleanupReviewResult | None:
    dialog = CleanupReviewDialog(parent, entries)
    dialog.wait_window()
    return dialog.result
