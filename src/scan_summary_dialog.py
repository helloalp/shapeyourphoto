from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from file_actions import ScanResult
from ui.window_titles import app_window_title
from window_layout import center_window


def _location_label(location: str) -> str:
    if location == "root_child":
        return "根文件夹下的文件夹"
    if location == "nested":
        return "子文件夹"
    return location or "未知"


class ScanSummaryDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, scan_results: list[ScanResult]) -> None:
        super().__init__(parent)
        self.title(app_window_title("最近扫描摘要"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)
        self.minsize(920, 620)
        self._scan_results = scan_results
        self._skipped_entries = [entry for result in scan_results for entry in result.summary.skipped_details]

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        summary_frame = ttk.LabelFrame(outer, text="摘要", padding=10)
        summary_frame.grid(row=0, column=0, sticky="ew")
        for line in self._summary_lines():
            ttk.Label(summary_frame, text=line, anchor="w").pack(fill="x")

        detail_frame = ttk.LabelFrame(outer, text="跳过的文件夹", padding=10)
        detail_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            detail_frame,
            columns=("root", "prefix", "location", "reason"),
            show=("tree", "headings"),
        )
        self.tree.heading("#0", text="文件夹路径")
        self.tree.column("#0", width=420, anchor="w")
        self.tree.heading("root", text="扫描根文件夹")
        self.tree.column("root", width=200, anchor="w")
        self.tree.heading("prefix", text="命中前缀")
        self.tree.column("prefix", width=110, anchor="center")
        self.tree.heading("location", text="位置")
        self.tree.column("location", width=120, anchor="center")
        self.tree.heading("reason", text="跳过原因")
        self.tree.column("reason", width=300, anchor="w")

        scroll_y = ttk.Scrollbar(detail_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(detail_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self._populate_tree()

        button_row = ttk.Frame(outer)
        button_row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(button_row, text="复制明细", command=self._copy).pack(side="left")
        ttk.Button(button_row, text="关闭", command=self.destroy).pack(side="right")

        center_window(self, 1080, 720)

    def _summary_lines(self) -> list[str]:
        imported_total = sum(result.summary.imported_count for result in self._scan_results)
        skipped_total = sum(result.summary.skipped_directory_count for result in self._scan_results)
        prefix_counts: dict[str, int] = {}
        for result in self._scan_results:
            for prefix, count in result.summary.skipped_prefix_counts.items():
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + count

        lines = [
            f"本次扫描文件夹数：{len(self._scan_results)}",
            f"导入图片总数：{imported_total}",
            f"跳过文件夹总数：{skipped_total}",
        ]
        if prefix_counts:
            prefix_text = "；".join(f"{prefix}：{count} 个文件夹" for prefix, count in prefix_counts.items())
            lines.append(f"命中忽略前缀统计：{prefix_text}")
        else:
            lines.append("命中忽略前缀统计：本次没有跳过文件夹。")

        for result in self._scan_results:
            prefix_text = "；".join(
                f"{prefix}：{count}" for prefix, count in result.summary.skipped_prefix_counts.items()
            ) or "无"
            lines.append(
                f"[{result.summary.root.name}] 模式：{result.summary.mode_label} | 导入 {result.summary.imported_count} 张 | "
                f"跳过 {result.summary.skipped_directory_count} 个 | 前缀命中：{prefix_text}"
            )
        return lines

    def _populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self._skipped_entries:
            self.tree.insert("", "end", text="本次扫描没有命中忽略前缀的文件夹。", values=("", "", "", ""))
            return

        for entry in self._skipped_entries:
            display_path = str(entry.path)
            try:
                display_path = str(entry.path.relative_to(entry.root))
            except Exception:
                pass
            self.tree.insert(
                "",
                "end",
                text=display_path,
                values=(str(entry.root), entry.matched_prefix, _location_label(entry.location), entry.reason),
            )

    def _copy(self) -> None:
        lines = [*self._summary_lines(), ""]
        if not self._skipped_entries:
            lines.append("本次扫描没有跳过文件夹。")
        else:
            for entry in self._skipped_entries:
                lines.append(
                    f"{entry.path} | 命中前缀：{entry.matched_prefix} | 位置：{_location_label(entry.location)} | 原因：{entry.reason}"
                )
        try:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
        except Exception:
            pass


def show_scan_summary_dialog(parent: tk.Widget, scan_results: list[ScanResult]) -> None:
    dialog = ScanSummaryDialog(parent, scan_results)
    dialog.wait_window()
