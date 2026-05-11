from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from cleanup_review_dialog import CleanupReviewEntry, show_cleanup_review_dialog
from file_actions import safe_cleanup_paths
from models import SimilarImageGroup
from similar_review_dialog import show_similar_group_decision_dialog, show_similar_group_list_dialog


class UiReviewActionsMixin:
    def _maybe_prompt_cleanup_candidates(self, paths: list[Path]) -> None:
        if not paths:
            return
        primary_candidates = self._primary_cleanup_candidates()
        matched_paths = [path for path in paths if path in primary_candidates]
        if not matched_paths:
            return

        first_path = matched_paths[0]
        self._select_path(first_path)
        self._select_cleanup_path(first_path)
        entries = [
            CleanupReviewEntry(
                image_path=path,
                display_name=path.name,
                reason_code=primary_candidates[path].reason_code,
                reason_text=primary_candidates[path].reason_text,
                severity=primary_candidates[path].severity,
                confidence=primary_candidates[path].confidence,
            )
            for path in matched_paths
        ]
        dialog_result = show_cleanup_review_dialog(self.root, entries)
        if dialog_result is None:
            return

        for path in matched_paths:
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
            self.cleanup_flags[path].set(False)
        for path in dialog_result.chosen_paths:
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
            self.cleanup_flags[path].set(True)
        self.refresh_tree()
        if dialog_result.chosen_paths:
            self._select_path(dialog_result.chosen_paths[0])
            self._select_cleanup_path(dialog_result.chosen_paths[0])
        if dialog_result.action == "delete" and dialog_result.chosen_paths:
            self.cleanup_selected_candidates()

    def _maybe_prompt_similar_groups(self, groups: list[SimilarImageGroup]) -> None:
        groups = [group for group in groups if len([path for path in group.paths if path.exists()]) >= 2]
        if not groups:
            return
        self._log_console(f"similar detection summary: groups={len(groups)}")
        self.open_similar_group_window(groups)

    def open_similar_group_window(self, groups: list[SimilarImageGroup] | None = None) -> None:
        self._prune_missing_paths()
        active_groups = groups if groups is not None else self.similar_groups
        active_groups = [group for group in active_groups if len([path for path in group.paths if path.exists()]) >= 2]
        if not active_groups:
            messagebox.showinfo("提示", "当前没有可复核的相似图片组。")
            return
        cleanup_paths = set(self._primary_cleanup_candidates())
        show_similar_group_list_dialog(
            self.root,
            active_groups,
            self.results,
            cleanup_paths,
            self._open_similar_decision_window,
        )
        self._prune_similar_groups()
        self.refresh_tree()

    def _open_similar_decision_window(self, groups: list[SimilarImageGroup]) -> None:
        cleanup_paths = set(self._primary_cleanup_candidates())
        show_similar_group_decision_dialog(
            self.root,
            groups,
            self.results,
            cleanup_paths,
            self._delete_similar_image,
        )
        self._prune_similar_groups()
        self.refresh_tree()

    def open_cleanup_review_window(self) -> None:
        self._prune_missing_paths()
        primary_candidates = self._primary_cleanup_candidates()
        if not primary_candidates:
            messagebox.showinfo("提示", "当前没有可重新查看的不适合保留候选。")
            return
        ordered_paths = [path for path in self._sorted_paths() if path in primary_candidates]
        entries = [
            CleanupReviewEntry(
                image_path=path,
                display_name=path.name,
                reason_code=primary_candidates[path].reason_code,
                reason_text=primary_candidates[path].reason_text,
                severity=primary_candidates[path].severity,
                confidence=primary_candidates[path].confidence,
            )
            for path in ordered_paths
        ]
        dialog_result = show_cleanup_review_dialog(self.root, entries)
        if dialog_result is None:
            return
        for path in primary_candidates:
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
            self.cleanup_flags[path].set(False)
        for path in dialog_result.chosen_paths:
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
            self.cleanup_flags[path].set(True)
        self.refresh_tree()
        if dialog_result.action == "delete" and dialog_result.chosen_paths:
            self.cleanup_selected_candidates()

    def _delete_similar_image(self, path: Path, group: SimilarImageGroup) -> bool:
        if not path.exists():
            group.paths[:] = [item for item in group.paths if item != path]
            self._remove_path_from_list(path, refresh=False)
            self.refresh_tree()
            return True
        result = self.results.get(path)
        cleanup_marker = "；该图同时是不适合保留候选" if result and result.cleanup_candidates else ""
        confirm = messagebox.askyesno(
            "确认删除相似图片",
            "将优先尝试移入系统回收站；若系统不支持，则移入项目内安全隔离目录 `_cleanup_candidates`。\n\n"
            f"相似组 {group.group_id}：{path.name}{cleanup_marker}\n\n是否继续？",
        )
        if not confirm:
            return False
        try:
            operation = safe_cleanup_paths([path], self._resolve_base_folder())
        except Exception as exc:
            self._log_console(f"similar delete failed: {path.name} | {exc}")
            messagebox.showerror("无法删除", f"未能安全删除 {path.name}：\n{exc}")
            return False
        if operation.moved < 1 and path.exists():
            messagebox.showerror("无法删除", f"未能安全删除 {path.name}：\n{operation.destination_label}")
            return False

        self._remove_path_from_list(path, refresh=False)
        self.image_paths = [item for item in self.image_paths if item.exists()]
        group.paths[:] = [item for item in group.paths if item != path and item.exists()]
        self._prune_similar_groups()
        self.refresh_tree()
        current = self._current_path()
        if current is None and self.image_paths:
            self._select_path(self.image_paths[0])
        detail = f"已安全清理相似图片：{path.name} -> {operation.destination_label}"
        self._log_console(f"similar image handled: group={group.group_id} mode={operation.mode} moved={operation.moved} destination={operation.destination_label}")
        self.status_var.set(detail)
        return True

    def cleanup_selected_candidates(self) -> None:
        primary_candidates = self._primary_cleanup_candidates()
        chosen = [path for path, flag in self.cleanup_flags.items() if flag.get() and path in primary_candidates and path.exists()]
        if not chosen:
            self._update_cleanup_controls()
            return

        preview_lines = []
        for path in chosen[:5]:
            candidate = primary_candidates[path]
            preview_lines.append(f"- {path.name} | {candidate.reason_code} | {candidate.severity}")
        if len(chosen) > 5:
            preview_lines.append(f"... 另外 {len(chosen) - 5} 张")
        confirm = messagebox.askyesno(
            "确认安全清理",
            "将优先尝试移入系统回收站；若系统不支持，则移入项目内安全隔离目录 `_cleanup_candidates`。\n\n"
            f"本次共 {len(chosen)} 张：\n" + "\n".join(preview_lines) + "\n\n是否继续？",
        )
        if not confirm:
            return

        try:
            operation = safe_cleanup_paths(chosen, self._resolve_base_folder())
        except Exception as exc:
            self._log_console(f"cleanup candidates failed: {exc}")
            messagebox.showerror("无法删除", f"安全清理失败：\n{exc}")
            return
        for path in chosen:
            self._remove_path_from_list(path, refresh=False)

        self.image_paths = [path for path in self.image_paths if path.exists()]
        self.refresh_tree()

        self._log_console(f"cleanup candidates handled: mode={operation.mode} moved={operation.moved} destination={operation.destination_label}")
        if operation.mode == "recycle_bin":
            detail = f"已将 {operation.moved} 张图片移入系统回收站。"
        elif operation.mode == "mixed":
            detail = f"已处理 {operation.moved} 张图片：{operation.destination_label}"
        else:
            detail = f"系统回收站不可用，已将 {operation.moved} 张图片移入安全隔离目录：{operation.destination_label}"
        self.status_var.set(detail)
        messagebox.showinfo("完成", detail)

    def cleanup_selected(self) -> None:
        if self._primary_cleanup_candidates():
            if not any(flag.get() for flag in self.cleanup_flags.values()):
                messagebox.showinfo("提示", "请先在“不适合保留候选”框体中勾选需要清理的图片。")
                self._update_cleanup_controls()
                return
            self.cleanup_selected_candidates()
            return

        chosen = [path for path, flag in self.selected_flags.items() if flag.get() and path.exists()]
        if not chosen:
            messagebox.showinfo("提示", "当前没有勾选需要清理的图片。")
            return

        confirm = messagebox.askyesno(
            "确认安全清理",
            "将优先尝试移入系统回收站；若系统不支持，则移入项目内安全隔离目录 `_cleanup_candidates`。\n\n"
            f"本次共 {len(chosen)} 张，是否继续？",
        )
        if not confirm:
            return

        try:
            operation = safe_cleanup_paths(chosen, self._resolve_base_folder())
        except Exception as exc:
            self._log_console(f"cleanup failed: {exc}")
            messagebox.showerror("无法删除", f"安全清理失败：\n{exc}")
            return
        for path in chosen:
            self._remove_path_from_list(path, refresh=False)

        self.image_paths = [path for path in self.image_paths if path.exists()]
        self.refresh_tree()
        self._log_console(f"cleanup moved: mode={operation.mode} moved={operation.moved} -> {operation.destination_label}")
        self.status_var.set(f"已安全清理 {operation.moved} 张图片：{operation.destination_label}")
        messagebox.showinfo("完成", f"已安全清理 {operation.moved} 张图片：\n{operation.destination_label}")
