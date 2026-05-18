from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from models import SessionStats
from stats_store import export_stats_report
from ui.display_names import display_name
from ui.language import tr
from ui.window_titles import app_window_title
from window_layout import center_window, prepare_dialog_window


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def _bar(canvas: tk.Canvas, x: int, y: int, width: int, label: str, value: float, max_value: float, color: str) -> None:
    max_value = max(1.0, max_value)
    fill_width = int(width * max(0.0, min(1.0, value / max_value)))
    canvas.create_text(x, y, anchor="nw", text=label, fill="#1f3527", font=("Microsoft YaHei UI", 9))
    canvas.create_rectangle(x + 190, y + 3, x + 190 + width, y + 17, outline="#d8e5dc", fill="#ffffff")
    canvas.create_rectangle(x + 190, y + 3, x + 190 + fill_width, y + 17, outline="", fill=color)
    canvas.create_text(x + 200 + width, y, anchor="nw", text=f"{value:.0f}", fill="#45604d", font=("Consolas", 9))


def _section(canvas: tk.Canvas, y: int, title: str) -> int:
    canvas.create_text(20, y, anchor="nw", text=title, fill="#1c3c2a", font=("Microsoft YaHei UI", 11, "bold"))
    return y + 32


def show_stats_dialog(parent: tk.Widget, stats: SessionStats) -> None:
    dialog = tk.Toplevel(parent)
    prepare_dialog_window(
        dialog,
        parent,
        title=app_window_title(tr("stats.title")),
        min_width=960,
        min_height=760,
        modal=False,
    )

    outer = ttk.Frame(dialog, padding=14)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(2, weight=0)

    ttk.Label(outer, text=tr("stats.title"), font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(outer, text=tr("stats.subtitle"), wraplength=880, justify="left").grid(row=1, column=0, sticky="w", pady=(4, 10))

    summary = ttk.Frame(outer)
    summary.grid(row=2, column=0, sticky="ew", pady=(4, 8))
    for column in range(4):
        summary.columnconfigure(column, weight=1)
    issue_rate = stats.issue_images / max(1, stats.analyzed_images)
    cards = [
        (tr("stats.card.analysis"), f"{stats.analyzed_images}", _format_bytes(stats.analyzed_bytes)),
        (tr("stats.card.repair"), f"{stats.repaired_images}", _format_bytes(stats.repaired_bytes)),
        (tr("stats.card.skip_rollback"), f"{stats.skipped_images} / {stats.rollback_images}", tr("stats.unsaved").format(count=stats.noop_images)),
        (tr("stats.card.scan"), tr("stats.scan_rounds").format(count=stats.scanned_folders), tr("stats.skipped_folders").format(count=stats.skipped_folders)),
        (tr("stats.card.unsuitable"), f"{stats.cleanup_candidate_images}", tr("stats.candidate_images")),
        (tr("stats.card.similar"), f"{stats.similar_group_count}", tr("stats.groups")),
        (tr("stats.card.failed_cancel"), f"{stats.failed_images} / {stats.canceled_tasks}", tr("stats.needs_attention")),
        (tr("stats.card.issue_rate"), f"{issue_rate:.1%}", tr("stats.issue_images").format(count=stats.issue_images)),
    ]
    for index, (title, value, sub) in enumerate(cards):
        card = ttk.Frame(summary, padding=10, style="TopCard.TFrame")
        card.grid(row=index // 4, column=index % 4, sticky="nsew", padx=4, pady=4)
        ttk.Label(card, text=title, style="HudValue.TLabel").pack(anchor="w")
        ttk.Label(card, text=value, style="HudTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text=sub, style="HudValue.TLabel").pack(anchor="w")

    chart_frame = ttk.Frame(outer)
    chart_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
    outer.rowconfigure(3, weight=1)
    chart_frame.columnconfigure(0, weight=1)
    chart_frame.rowconfigure(0, weight=1)
    canvas = tk.Canvas(chart_frame, bg="#f8fbf8", highlightthickness=0)
    scroll_y = ttk.Scrollbar(chart_frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll_y.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")

    width = 900
    y = 20
    y = _section(canvas, y, tr("stats.issue_rate_chart"))
    canvas.create_rectangle(56, y + 10, width - 44, y + 190, outline="#d8e5dc")
    points = stats.issue_points[-60:]
    if len(points) >= 2:
        graph_w = width - 120
        graph_h = 150
        coords = []
        for idx, (_, rate) in enumerate(points):
            x = 66 + graph_w * idx / max(1, len(points) - 1)
            yy = y + 22 + graph_h * (1.0 - max(0.0, min(1.0, rate)))
            coords.extend((x, yy))
        canvas.create_line(*coords, fill="#2f8f63", width=3, smooth=True)
    else:
        canvas.create_text(66, y + 60, anchor="nw", text=tr("stats.not_enough"), fill="#4c6a57", font=("Microsoft YaHei UI", 10))
    y += 220

    y = _section(canvas, y, tr("stats.volume_chart"))
    volume_values = [
        (tr("stats.analyzed"), stats.analyzed_images, "#5b9bd5"),
        (tr("stats.repaired"), stats.repaired_images, "#70ad47"),
        (tr("stats.skipped"), stats.skipped_images, "#ffc000"),
        (tr("stats.scanned_files"), stats.scanned_files, "#8064a2"),
    ]
    max_volume = max([value for _label, value, _color in volume_values] + [1])
    for label, value, color in volume_values:
        _bar(canvas, 32, y, 430, label, float(value), float(max_volume), color)
        y += 28
    y += 24

    y = _section(canvas, y, tr("stats.outcome_chart"))
    outcome_items = sorted(stats.repair_outcome_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    if not outcome_items:
        outcome_items = [("normal_saved", stats.repaired_images), ("skipped", stats.skipped_images), ("failed", stats.failed_images)]
    max_outcome = max([value for _key, value in outcome_items] + [1])
    for key, value in outcome_items:
        _bar(canvas, 32, y, 430, display_name("outcome", key), float(value), float(max_outcome), "#76a9d8")
        y += 28
    y += 24

    y = _section(canvas, y, tr("stats.common_issues"))
    issue_items = sorted(stats.issue_code_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    if not issue_items:
        issue_items = [("overexposed", 0), ("underexposed", 0), ("out_of_focus", 0)]
    max_issue = max([value for _key, value in issue_items] + [1])
    for key, value in issue_items:
        _bar(canvas, 32, y, 430, display_name("issue", key), float(value), float(max_issue), "#d8896b")
        y += 28
    y += 24

    y = _section(canvas, y, tr("stats.daily_chart"))
    daily_items = sorted(stats.daily_counts.items())[-10:]
    if daily_items:
        max_daily = max(sum(values.values()) for _day, values in daily_items) or 1
        for day, values in daily_items:
            total = sum(values.values())
            label = (
                f"{day}  {tr('stats.daily_analyzed')} {values.get('analyzed', 0)}  "
                f"{tr('stats.daily_repaired')} {values.get('repaired', 0)}  "
                f"{tr('stats.daily_scanned')} {values.get('scan_runs', 0)}"
            )
            _bar(canvas, 32, y, 430, label, float(total), float(max_daily), "#8fbf8f")
            y += 28
    else:
        canvas.create_text(32, y, anchor="nw", text=tr("stats.not_enough"), fill="#4c6a57", font=("Microsoft YaHei UI", 10))
        y += 32

    y += 30
    canvas.configure(scrollregion=(0, 0, width, max(y, 640)))

    actions = ttk.Frame(outer)
    actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    actions.columnconfigure(0, weight=1)

    def export_report() -> None:
        target = filedialog.asksaveasfilename(
            parent=dialog,
            title=tr("stats.export_title"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not target:
            return
        output = export_stats_report(stats, target)
        messagebox.showinfo(tr("stats.export_title"), tr("stats.export_done").format(path=output), parent=dialog)

    ttk.Button(actions, text=tr("stats.export"), command=export_report).pack(side="left")
    ttk.Button(actions, text=tr("stats.close"), command=dialog.destroy).pack(side="right")
    center_window(dialog, 1000, 820)
