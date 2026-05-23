from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from models import AnalysisResult
from ui.language import tr
from ui.themes import ThemeTokens, get_theme


class DiagnosticsChart(ttk.Frame):
    def __init__(self, master) -> None:
        super().__init__(master, style="Panel.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._theme = get_theme("classic_green")
        self._resize_after_id: str | None = None
        self.canvas = tk.Canvas(self, bg=self._theme.panel, highlightthickness=0, height=420)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>", self._on_resize)
        self._result: AnalysisResult | None = None

    def update_result(self, result: AnalysisResult | None) -> None:
        self._result = result
        self._draw()

    def apply_theme(self, theme: ThemeTokens) -> None:
        self._theme = theme
        self.canvas.configure(bg=theme.panel)
        self._draw()

    def _on_resize(self, _event=None) -> None:
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass
        self._resize_after_id = self.after(100, self._draw_after_resize)

    def _draw_after_resize(self) -> None:
        self._resize_after_id = None
        self._draw()

    def _draw(self) -> None:
        theme = self._theme
        self.canvas.delete("all")
        width = max(360, self.canvas.winfo_width() or 420)
        height = max(280, self.canvas.winfo_height() or 280)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        title_font, body_font, value_font, label_w, value_pad, bar_h, row_gap = self._layout_metrics(width)

        if self._result is None:
            self.canvas.create_text(
                18,
                18,
                anchor="nw",
                text=tr("diagnostics.empty"),
                fill=theme.muted_text,
                font=("Microsoft YaHei UI", body_font),
            )
            return

        x0 = 20
        y = 16
        bar_x = x0 + label_w
        value_x = width - 18
        percent_x = max(bar_x + 46, value_x - value_pad)
        bar_w = max(90, percent_x - bar_x - 14)

        self.canvas.create_text(x0, y, anchor="nw", text=tr("diagnostics.issue_strength"), fill=theme.text, font=("Microsoft YaHei UI", title_font, "bold"))
        y += row_gap + 2

        issue_rows = self._result.issues[:6]
        if not issue_rows:
            self.canvas.create_text(x0, y, anchor="nw", text=tr("diagnostics.no_issues"), fill=theme.muted_text, font=("Microsoft YaHei UI", body_font))
            y += row_gap
        else:
            for issue in issue_rows:
                y = self._draw_bar(
                    y,
                    issue.label,
                    issue.score,
                    f"{issue.score:.2f}",
                    theme.danger,
                    bar_x,
                    bar_w,
                    percent_x,
                    value_x,
                    body_font,
                    value_font,
                    bar_h,
                    row_gap,
                )

        y += max(8, row_gap // 2)
        self.canvas.create_text(x0, y, anchor="nw", text=tr("diagnostics.key_metrics"), fill=theme.text, font=("Microsoft YaHei UI", title_font, "bold"))
        y += row_gap + 2

        for metric in self._result.metrics:
            y = self._draw_bar(
                y,
                metric.label,
                metric.ratio,
                metric.value,
                metric.color,
                bar_x,
                bar_w,
                percent_x,
                value_x,
                body_font,
                value_font,
                bar_h,
                row_gap,
            )

        self.canvas.configure(scrollregion=(0, 0, width, y + 12))

    def _layout_metrics(self, width: int) -> tuple[int, int, int, int, int, int, int]:
        if width < 520:
            return 10, 8, 8, 86, 96, 16, 24
        if width < 680:
            return 10, 9, 9, 104, 108, 17, 26
        return 11, 10, 10, 126, 120, 18, 28

    def _draw_bar(
        self,
        y: int,
        label: str,
        ratio: float,
        value: str,
        color: str,
        bar_x: int,
        bar_w: int,
        percent_x: int,
        value_x: int,
        body_font: int,
        value_font: int,
        bar_h: int,
        row_gap: int,
    ) -> int:
        x0 = 20
        label_text = self._ellipsize(label, 14 if bar_x < 118 else 18)
        self.canvas.create_text(x0, y + 6, anchor="nw", text=label_text, fill=self._theme.text, font=("Microsoft YaHei UI", body_font))
        self.canvas.create_rectangle(bar_x, y + 3, bar_x + bar_w, y + 3 + bar_h, fill=self._theme.button, outline="")
        fill_w = max(0, min(bar_w, int(bar_w * ratio)))
        self.canvas.create_rectangle(bar_x, y + 3, bar_x + fill_w, y + 3 + bar_h, fill=color, outline="")
        percent_text = f"{ratio * 100:.0f}%"
        self.canvas.create_text(percent_x, y + 6, anchor="e", text=percent_text, fill=self._theme.muted_text, font=("Microsoft YaHei UI", body_font))
        self.canvas.create_text(value_x, y + 6, anchor="e", text=self._ellipsize(str(value), 10), fill=self._theme.text, font=("Consolas", value_font))
        return y + row_gap

    def _ellipsize(self, text: str, limit: int) -> str:
        value = str(text)
        if len(value) <= limit:
            return value
        return value[: max(1, limit - 1)] + "…"
