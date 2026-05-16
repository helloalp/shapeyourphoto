from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk

from app_settings import REPAIR_SUMMARY_FILTER_ALL, REPAIR_SUMMARY_FILTER_OPTIONS, normalize_repair_summary_filter
from ui.display_names import display_name
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window


@dataclass
class RepairCompletionEntry:
    file_name: str
    status: str
    primary_reason: str
    ops_or_skip: str
    forced: bool
    filter_tags: set[str] = field(default_factory=set)
    detail_lines: list[str] = field(default_factory=list)


class RepairCompletionDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        *,
        title: str,
        summary_lines: list[str],
        entries: list[RepairCompletionEntry],
        default_filter: str = REPAIR_SUMMARY_FILTER_ALL,
    ) -> None:
        super().__init__(parent)
        self.title(app_window_title(title))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(1040, 720)
        self._entries = entries
        self._label_to_filter = {label: value for value, label in REPAIR_SUMMARY_FILTER_OPTIONS}
        self._filter_to_label = dict(REPAIR_SUMMARY_FILTER_OPTIONS)
        normalized_filter = normalize_repair_summary_filter(default_filter)
        self.filter_var = tk.StringVar(value=self._filter_to_label[normalized_filter])
        self._size_notice_var = tk.StringVar(value="")

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        summary_frame = ttk.Frame(outer, padding=(0, 0, 0, 2))
        summary_frame.grid(row=0, column=0, sticky="ew")
        summary_frame.columnconfigure(0, weight=1)
        for index, line in enumerate(summary_lines[:8]):
            chip = ttk.Label(summary_frame, text=line, anchor="center", relief="solid", padding=(8, 4))
            chip.grid(row=index // 4, column=index % 4, sticky="ew", padx=(0 if index % 4 == 0 else 6, 0), pady=(0, 6))
            summary_frame.columnconfigure(index % 4, weight=1)
        if len(summary_lines) > 8:
            ttk.Label(summary_frame, text="更多批次信息在下方详情中查看。").grid(row=2, column=0, columnspan=4, sticky="w")

        filter_row = ttk.Frame(outer)
        filter_row.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        ttk.Label(filter_row, text="筛选：").pack(side="left")
        filter_box = ttk.Combobox(
            filter_row,
            textvariable=self.filter_var,
            state="readonly",
            values=[label for _value, label in REPAIR_SUMMARY_FILTER_OPTIONS],
            width=22,
        )
        filter_box.pack(side="left")
        filter_box.bind("<<ComboboxSelected>>", lambda _event: self._populate_tree())
        ttk.Button(filter_row, text="复制当前筛选结果", command=self._copy_current_filter).pack(side="left", padx=(10, 0))
        ttk.Label(filter_row, text="顶部统计固定显示全量结果，不会随筛选变化。").pack(side="right")

        body = ttk.PanedWindow(outer, orient="vertical")
        body.grid(row=2, column=0, sticky="nsew")

        list_frame = ttk.Frame(body, padding=0)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        body.add(list_frame, weight=4)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("status", "reason", "ops", "forced"),
            show=("tree", "headings"),
            selectmode="browse",
        )
        self.tree.heading("#0", text="文件名")
        self.tree.column("#0", width=230, anchor="w")
        self.tree.heading("status", text="状态")
        self.tree.column("status", width=190, anchor="center")
        self.tree.heading("reason", text="主要原因")
        self.tree.column("reason", width=330, anchor="w")
        self.tree.heading("ops", text="操作 / 跳过原因")
        self.tree.column("ops", width=320, anchor="w")
        self.tree.heading("forced", text="强制")
        self.tree.column("forced", width=80, anchor="center")

        scroll_y = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_detail)

        detail_frame = ttk.LabelFrame(body, text="选中项详情", padding=10)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)
        body.add(detail_frame, weight=2)

        self.detail_text = tk.Text(
            detail_frame,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
            bg="#fbfcfa",
            relief="flat",
            padx=10,
            pady=10,
        )
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        detail_scroll.grid(row=0, column=1, sticky="ns")
        self.detail_text.insert("1.0", "请选择上方任一记录，查看更完整的原因、策略说明和警告。")
        self.detail_text.config(state="disabled")

        button_row = ttk.Frame(outer)
        button_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(button_row, textvariable=self._size_notice_var).pack(side="left")
        ttk.Button(button_row, text="关闭", command=self.destroy).pack(side="right")

        self._item_to_entry: dict[str, RepairCompletionEntry] = {}
        self._populate_tree()
        bind_minimum_size_notice(self, self._size_notice_var, 1040, 720)
        center_window(self, 1320, 900)

    def _current_filter(self) -> str:
        return normalize_repair_summary_filter(self._label_to_filter.get(self.filter_var.get()))

    def _visible_entries(self) -> list[RepairCompletionEntry]:
        current_filter = self._current_filter()
        if current_filter == REPAIR_SUMMARY_FILTER_ALL:
            return list(self._entries)
        return [entry for entry in self._entries if current_filter in entry.filter_tags]

    def _populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._item_to_entry.clear()
        visible = self._visible_entries()
        for entry in visible:
            item_id = self.tree.insert(
                "",
                "end",
                text=entry.file_name,
                values=(entry.status, entry.primary_reason, entry.ops_or_skip, "是" if entry.forced else ""),
            )
            self._item_to_entry[item_id] = entry
        if visible:
            first_id = self.tree.get_children()[0]
            self.tree.selection_set(first_id)
            self._show_selected_detail()
        else:
            self._set_detail_text(f"当前筛选“{self.filter_var.get()}”下没有记录。")

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.config(state="disabled")

    def _show_selected_detail(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            self._set_detail_text("请选择上方任一记录查看详情。")
            return
        entry = self._item_to_entry.get(selection[0])
        if entry is None:
            self._set_detail_text("未找到所选记录。")
            return
        lines = [
            f"文件名：{entry.file_name}",
            f"状态：{entry.status}",
            f"主要原因：{entry.primary_reason}",
            f"操作 / 跳过原因：{entry.ops_or_skip}",
            f"强制尝试：{'是' if entry.forced else '否'}",
            "",
        ]
        lines.extend(entry.detail_lines or ["没有额外详情。"])
        self._set_detail_text("\n".join(lines))

    def _copy_current_filter(self) -> None:
        visible = self._visible_entries()
        lines = [f"当前筛选：{self.filter_var.get()}", ""]
        if not visible:
            lines.append("没有可复制的记录。")
        else:
            for entry in visible:
                lines.append(
                    f"{entry.file_name} | {entry.status} | {entry.primary_reason} | {entry.ops_or_skip} | 强制尝试：{'是' if entry.forced else '否'}"
                )
                for detail in entry.detail_lines:
                    lines.append(f"  {detail}")
        try:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
        except Exception:
            pass


def show_repair_completion_dialog(
    parent: tk.Widget,
    *,
    title: str,
    summary_lines: list[str],
    entries: list[RepairCompletionEntry],
    default_filter: str = REPAIR_SUMMARY_FILTER_ALL,
) -> None:
    dialog = RepairCompletionDialog(
        parent,
        title=title,
        summary_lines=summary_lines,
        entries=entries,
        default_filter=default_filter,
    )
    dialog.wait_window()
