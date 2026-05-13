from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from models import SessionStats
from stats_store import export_stats_report
from ui.window_titles import app_window_title
from window_layout import center_window


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def show_stats_dialog(parent: tk.Widget, stats: SessionStats) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title(app_window_title("统计"))
    dialog.minsize(760, 560)
    dialog.resizable(True, True)
    dialog.transient(parent.winfo_toplevel())
    center_window(dialog, 920, 700)

    outer = ttk.Frame(dialog, padding=14)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(2, weight=1)

    ttk.Label(outer, text="统计", font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(outer, text="显示累计分析、修复、跳过、回退、不适合保留和相似组等统计。").grid(row=1, column=0, sticky="w", pady=(4, 10))

    summary_frame = ttk.Frame(outer)
    summary_frame.grid(row=2, column=0, sticky="nsew")
    summary_frame.columnconfigure(0, weight=1)
    summary_frame.rowconfigure(0, weight=1)
    summary = tk.Text(summary_frame, height=14, wrap="word", font=("Microsoft YaHei UI", 10), bg="#f8fbf8", relief="flat", padx=10, pady=10)
    summary_scroll = ttk.Scrollbar(summary_frame, orient="vertical", command=summary.yview)
    summary.configure(yscrollcommand=summary_scroll.set)
    summary.grid(row=0, column=0, sticky="nsew")
    summary_scroll.grid(row=0, column=1, sticky="ns")
    issue_rate = stats.issue_images / max(1, stats.analyzed_images)
    lines = [
        f"累计分析图片：{stats.analyzed_images}",
        f"累计分析数据量：{_format_bytes(stats.analyzed_bytes)}",
        f"累计修复图片：{stats.repaired_images}",
        f"累计修复数据量：{_format_bytes(stats.repaired_bytes)}",
        f"累计检出问题图片：{stats.issue_images}",
        f"当前累计检出率：{issue_rate:.2%}",
        f"累计修复尝试：{stats.repair_attempted_images}",
        f"累计跳过或未保存：{stats.skipped_images}",
        f"累计回退：{stats.rollback_images}",
        f"不适合保留累计：{stats.cleanup_candidate_images}",
        f"相似组累计：{stats.similar_group_count}",
        f"平均分析耗时：{stats.average_analysis_wall_ms():.0f} ms/轮",
        f"平均修复耗时：{stats.average_repair_wall_ms():.0f} ms/轮",
        f"最近运行时间：{stats.last_run_at or '暂无'}",
        "",
        "按天聚合：",
        *[f"- {day}: 分析 {values.get('analyzed', 0)}，修复 {values.get('repaired', 0)}，跳过 {values.get('skipped', 0)}"
          for day, values in sorted(stats.daily_counts.items())[-7:]],
        "",
        "按版本聚合：",
        *[f"- {version}: 分析 {values.get('analyzed', 0)}，修复 {values.get('repaired', 0)}，跳过 {values.get('skipped', 0)}"
          for version, values in sorted(stats.version_counts.items())[-7:]],
    ]
    summary.insert("1.0", "\n".join(lines))
    summary.config(state="disabled")

    chart_frame = ttk.Frame(outer)
    chart_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
    chart_frame.columnconfigure(0, weight=1)
    chart_frame.rowconfigure(0, weight=1)

    canvas = tk.Canvas(chart_frame, bg="#f8fbf8", highlightthickness=0)
    scroll_y = ttk.Scrollbar(chart_frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll_y.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")

    width = 760
    height = 260
    canvas.create_text(20, 20, anchor="nw", text="问题检出率变化曲线", fill="#1c3c2a", font=("Microsoft YaHei UI", 10, "bold"))
    canvas.create_rectangle(46, 56, width - 24, height - 24, outline="#d8e5dc")
    points = stats.issue_points[-40:]
    if len(points) >= 2:
        graph_w = width - 90
        graph_h = height - 98
        coords = []
        for idx, (_, rate) in enumerate(points):
            x = 56 + graph_w * idx / max(1, len(points) - 1)
            y = 56 + graph_h * (1.0 - max(0.0, min(1.0, rate)))
            coords.extend((x, y))
        canvas.create_line(*coords, fill="#2f8f63", width=3, smooth=True)
        for idx, (ts, rate) in enumerate(points):
            x = 56 + graph_w * idx / max(1, len(points) - 1)
            y = 56 + graph_h * (1.0 - max(0.0, min(1.0, rate)))
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#2f8f63", outline="")
            if idx in {0, len(points) - 1}:
                canvas.create_text(x, height - 16, text=ts[11:19], fill="#4b6555", font=("Consolas", 8))
                canvas.create_text(x + 6, y - 10, anchor="w", text=f"{rate:.0%}", fill="#244333", font=("Microsoft YaHei UI", 8))
    else:
        canvas.create_text(56, 100, anchor="nw", text="累计样本不足，曲线会在分析更多图片后显示。", fill="#4c6a57", font=("Microsoft YaHei UI", 10))

    canvas.configure(scrollregion=(0, 0, width, height))

    actions = ttk.Frame(outer)
    actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    actions.columnconfigure(0, weight=1)

    def export_report() -> None:
        target = filedialog.asksaveasfilename(
            parent=dialog,
            title="导出统计报表",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not target:
            return
        output = export_stats_report(stats, target)
        messagebox.showinfo("导出完成", f"统计报表已导出到：\n{output}", parent=dialog)

    ttk.Button(actions, text="导出报表", command=export_report).pack(side="left")
    ttk.Button(actions, text="关闭", command=dialog.destroy).pack(side="right")
