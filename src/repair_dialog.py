from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from models import RepairMethod, RepairSelection
from repair_planner import get_method_labels
from ui.window_titles import app_window_title
from window_layout import bind_minimum_size_notice, center_window, prepare_dialog_window


class RepairDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        methods: list[RepairMethod],
        recommended_method_ids: list[str],
        allow_adaptive: bool,
        target_count: int = 1,
        analyzed_count: int = 0,
        recommendation_note: str = "",
    ) -> None:
        super().__init__(parent)
        prepare_dialog_window(self, parent, title=app_window_title(title), min_width=760, min_height=640)
        self.result: RepairSelection | None = None

        self.mode_var = tk.StringVar(value="adaptive" if allow_adaptive else "manual")
        self.output_folder_var = tk.StringVar(value="_repaired")
        self.filename_suffix_var = tk.StringVar(value="_fixed")
        self.use_suffix_var = tk.BooleanVar(value=True)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.force_repair_cleanup_var = tk.BooleanVar(value=False)
        self._size_notice_var = tk.StringVar(value="")
        self.method_vars = {
            method.method_id: tk.BooleanVar(value=method.method_id in recommended_method_ids)
            for method in methods
        }
        self.recommended_method_ids = recommended_method_ids

        self.protocol("WM_DELETE_WINDOW", self._cancel)

        container = ttk.Frame(self, padding=14)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        form_shell = ttk.Frame(container)
        form_shell.grid(row=0, column=0, sticky="nsew")
        form_shell.columnconfigure(0, weight=1)
        form_shell.rowconfigure(0, weight=1)

        canvas = tk.Canvas(form_shell, bg="#fbfcfa", highlightthickness=0)
        scroll = ttk.Scrollbar(form_shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas, padding=(2, 2, 10, 2))
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_scroll(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _fit_content(_event=None) -> None:
            canvas.itemconfigure(window_id, width=max(360, canvas.winfo_width()))

        content.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", _fit_content)

        ttk.Label(content, text="修复策略", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            content,
            text=(
                "自动模式会按每张图片的检测结果生成独立修复方案；"
                "手动模式会沿用你勾选的方法，但仍会按单图风险自动限幅，避免副作用。"
            ),
            wraplength=660,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        if allow_adaptive:
            ttk.Radiobutton(content, text="按检测结果自动推荐", value="adaptive", variable=self.mode_var).pack(anchor="w")
        ttk.Radiobutton(content, text="统一使用勾选的方法", value="manual", variable=self.mode_var).pack(anchor="w", pady=(0, 10))

        recommended_labels = "、".join(get_method_labels(recommended_method_ids)) or "当前没有明确推荐项"
        if target_count > 1:
            note = recommendation_note or f"已选择 {target_count} 张：多张图片将按各自分析结果使用不同修复方案和力度。"
            ttk.Label(content, text=note, wraplength=660, justify="left").pack(anchor="w", pady=(0, 4))
            ttk.Label(
                content,
                text=f"方法汇总（{analyzed_count}/{target_count} 张已有分析）：{recommended_labels}",
                wraplength=660,
                justify="left",
            ).pack(anchor="w", pady=(0, 10))
        else:
            ttk.Label(content, text=f"当前推荐：{recommended_labels}", wraplength=660, justify="left").pack(anchor="w", pady=(0, 10))

        guard_frame = ttk.LabelFrame(content, text="高风险图片处理", padding=10)
        guard_frame.pack(fill="x", pady=(0, 12))
        ttk.Checkbutton(
            guard_frame,
            text="强制修复不值得保留的图片",
            variable=self.force_repair_cleanup_var,
        ).pack(anchor="w")
        ttk.Label(
            guard_frame,
            text=(
                "仅表示允许尝试修复不适合保留的图片，"
                "不代表无条件保存。修复后仍会执行单图评分、安全检查和回退判断，"
                "不合适时会继续跳过输出。"
            ),
            wraplength=650,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        folder_row = ttk.Frame(content)
        folder_row.pack(fill="x", pady=(0, 8))
        ttk.Label(folder_row, text="输出文件夹名：").pack(side="left")
        ttk.Entry(folder_row, textvariable=self.output_folder_var, width=22).pack(side="left")
        ttk.Label(folder_row, text="例如：_repaired").pack(side="left", padx=(8, 0))

        suffix_row = ttk.Frame(content)
        suffix_row.pack(fill="x", pady=(0, 10))
        ttk.Label(suffix_row, text="输出文件后缀：").pack(side="left")
        ttk.Entry(suffix_row, textvariable=self.filename_suffix_var, width=22).pack(side="left")
        ttk.Label(suffix_row, text="例如：_fixed").pack(side="left", padx=(8, 0))

        options_row = ttk.Frame(content)
        options_row.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(options_row, text="使用后缀", variable=self.use_suffix_var).pack(side="left")
        ttk.Checkbutton(options_row, text="覆盖原文件（默认关闭）", variable=self.overwrite_var).pack(side="left", padx=(12, 0))

        ttk.Label(content, text="手动修复方法", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 8))

        methods_frame = ttk.Frame(content)
        methods_frame.pack(fill="x")
        for method in methods:
            row = ttk.Frame(methods_frame)
            row.pack(fill="x", pady=2)
            ttk.Checkbutton(row, text=method.label, variable=self.method_vars[method.method_id]).pack(side="left")
            ttk.Label(row, text=method.description, wraplength=520, justify="left").pack(side="left", padx=(8, 0))

        helper_row = ttk.Frame(content)
        helper_row.pack(fill="x", pady=(10, 0))
        ttk.Button(helper_row, text="只选推荐项", command=self._set_recommended).pack(side="left")
        ttk.Button(helper_row, text="清空手动勾选", command=self._clear_methods).pack(side="left", padx=6)

        action_row = ttk.Frame(container)
        action_row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(action_row, textvariable=self._size_notice_var).pack(side="left")
        ttk.Button(action_row, text="取消", command=self._cancel).pack(side="right")
        ttk.Button(action_row, text="开始修复", command=self._confirm).pack(side="right", padx=(0, 8))

        bind_minimum_size_notice(self, self._size_notice_var, 760, 640)
        center_window(self, 820, 820)

    def _set_recommended(self) -> None:
        for method_id, variable in self.method_vars.items():
            variable.set(method_id in self.recommended_method_ids)

    def _clear_methods(self) -> None:
        for variable in self.method_vars.values():
            variable.set(False)

    def _confirm(self) -> None:
        selected_method_ids = [method_id for method_id, variable in self.method_vars.items() if variable.get()]
        mode = self.mode_var.get()

        if mode == "manual" and not selected_method_ids:
            messagebox.showwarning("提示", "手动修复模式至少需要勾选一种修复方法。", parent=self)
            return

        output_folder_name = self.output_folder_var.get().strip() or "_repaired"
        use_suffix = self.use_suffix_var.get()
        filename_suffix = self.filename_suffix_var.get().strip() if use_suffix else ""
        if use_suffix and not filename_suffix:
            filename_suffix = "_fixed"

        self.result = RepairSelection(
            mode=mode,
            selected_method_ids=selected_method_ids,
            output_folder_name=output_folder_name,
            filename_suffix=filename_suffix,
            use_suffix=use_suffix,
            overwrite_original=self.overwrite_var.get(),
            force_repair_cleanup_candidates=self.force_repair_cleanup_var.get(),
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def show_repair_dialog(
    parent: tk.Widget,
    title: str,
    methods: list[RepairMethod],
    recommended_method_ids: list[str],
    allow_adaptive: bool,
    target_count: int = 1,
    analyzed_count: int = 0,
    recommendation_note: str = "",
) -> RepairSelection | None:
    dialog = RepairDialog(
        parent,
        title,
        methods,
        recommended_method_ids,
        allow_adaptive,
        target_count=target_count,
        analyzed_count=analyzed_count,
        recommendation_note=recommendation_note,
    )
    dialog.wait_window()
    return dialog.result
