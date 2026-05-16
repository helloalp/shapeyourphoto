from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageOps, ImageTk

from developer_mode import developer_session
from file_actions import export_cleanup_list
from metadata_utils import summarize_image_metadata
from models import AnalysisResult, CleanupCandidate, SimilarImageGroup
from repair_planner import get_method_labels, suggest_methods_for_result
from result_sorting import sort_paths
from ui.display_names import display_name, issue_display
from ui.metadata_editor import show_metadata_edit_dialog, supports_metadata_edit


class UiFileListMixin:
    def _toggle_sort(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.refresh_tree()

    def _selected_tree_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item_id in self.tree.selection():
            path = self.item_lookup.get(item_id)
            if path is not None:
                paths.append(path)
        return paths

    def _visible_tree_item_ids(self) -> list[str]:
        return list(self.tree.get_children(""))

    def _prune_missing_paths(self) -> None:
        missing = [path for path in self.image_paths if not path.exists()]
        if not missing:
            return
        for path in missing:
            self.results.pop(path, None)
            self.errors.pop(path, None)
            self.selected_flags.pop(path, None)
            self.cleanup_flags.pop(path, None)
            self.thumb_cache.evict(path)
        self.image_paths = [path for path in self.image_paths if path.exists()]
        self._prune_similar_groups()

    def _prune_similar_groups(self) -> None:
        kept: list[SimilarImageGroup] = []
        next_id = 1
        for group in self.similar_groups:
            group.paths[:] = [path for path in group.paths if path.exists() and path in self.image_paths]
            if len(group.paths) < 2:
                continue
            group.group_id = next_id
            kept.append(group)
            next_id += 1
        self.similar_groups = kept

    def _sorted_paths(self) -> list[Path]:
        visible: list[Path] = []
        for path in self.image_paths:
            result = self.results.get(path)
            error = self.errors.get(path)
            if self._matches_filter(result, error):
                visible.append(path)
        return sort_paths(visible, self.results, self.errors, self.sort_column, self.sort_reverse)

    def _cleanup_severity_rank(self, severity: str) -> int:
        order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return order.get(severity.lower(), 0)

    def _cleanup_reason_summary(self, candidate: CleanupCandidate) -> str:
        label = display_name("cleanup_reason", candidate.reason_code)
        detail = candidate.reason_text.strip()
        if not detail or detail == candidate.reason_code or detail == label:
            return label
        if candidate.reason_code in detail:
            detail = detail.replace(candidate.reason_code, label)
        if detail.startswith("未知类型"):
            return label
        return f"{label}：{detail}"

    def _primary_cleanup_candidates(self) -> dict[Path, CleanupCandidate]:
        primary: dict[Path, CleanupCandidate] = {}
        for path, result in self.results.items():
            if not result.cleanup_candidates:
                continue
            best = sorted(
                result.cleanup_candidates,
                key=lambda candidate: (
                    self._cleanup_severity_rank(candidate.severity),
                    candidate.confidence,
                ),
                reverse=True,
            )[0]
            primary[path] = best
        return primary

    def _current_cleanup_path(self) -> Path | None:
        selection = self.cleanup_tree.selection()
        if not selection:
            return None
        return self.cleanup_item_lookup.get(selection[0])

    def _refresh_cleanup_tree(self) -> None:
        current_path = self._current_cleanup_path()
        primary_candidates = self._primary_cleanup_candidates()
        for item in self.cleanup_tree.get_children():
            self.cleanup_tree.delete(item)
        self.cleanup_item_lookup.clear()

        for path in list(self.cleanup_flags):
            if path not in primary_candidates:
                self.cleanup_flags.pop(path, None)
        for path in primary_candidates:
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))

        ordered_paths = sort_paths(
            [path for path in self.image_paths if path in primary_candidates],
            self.results,
            self.errors,
            self.sort_column,
            self.sort_reverse,
        )
        for path in ordered_paths:
            candidate = primary_candidates[path]
            checked = "已选" if self.cleanup_flags.get(path, tk.BooleanVar(value=False)).get() else "待定"
            confidence = f"{candidate.confidence:.2f}"
            thumb = self.thumb_cache.get_tree_thumbnail(path)
            item_id = self.cleanup_tree.insert(
                "",
                "end",
                text=path.name,
                image=thumb,
                values=(checked, display_name("severity", candidate.severity), confidence, self._cleanup_reason_summary(candidate)),
            )
            self.cleanup_item_lookup[item_id] = path
            if path == current_path:
                self.cleanup_tree.selection_set(item_id)

        self._update_cleanup_controls()

    def _update_cleanup_controls(self) -> None:
        selected_count = len([path for path, flag in self.cleanup_flags.items() if flag.get()])
        if selected_count > 0:
            self.cleanup_delete_button.configure(state="normal")
            self.cleanup_hint_var.set(f"已选择 {selected_count} 张图片。")
        else:
            self.cleanup_delete_button.configure(state="disabled")
            self.cleanup_hint_var.set("当前没有选择图片。")

    def _similar_marker_for_path(self, path: Path) -> str:
        group_ids = [str(group.group_id) for group in self.similar_groups if path in group.paths and len(group.paths) >= 2]
        if not group_ids:
            return ""
        return f"相似组#{'/'.join(group_ids[:2])}"

    def _tree_row_values(self, path: Path) -> tuple[str, str, str, str]:
        result = self.results.get(path)
        error = self.errors.get(path)
        checked = "已选" if self.selected_flags.get(path, tk.BooleanVar(value=False)).get() else "待定"
        status = "失败" if error else "已分析" if result else "未分析"
        risk = "-" if error or not result else f"{result.overall_score:.2f}"
        if error:
            tags = "分析失败"
        elif result and result.issues:
            tags = "、".join(issue_display(issue) for issue in result.issues)
        elif result:
            tags = "正常"
        else:
            tags = ""
        similar_marker = self._similar_marker_for_path(path)
        if similar_marker:
            tags = f"{tags} | {similar_marker}" if tags else similar_marker
        return checked, status, risk, tags

    def _update_list_stats(self) -> None:
        if not hasattr(self, "list_stats_var"):
            return
        total = len(self.image_paths)
        analyzed = len([path for path in self.image_paths if path in self.results])
        failed = len([path for path in self.image_paths if path in self.errors])
        issue_count = len([path for path in self.image_paths if path in self.results and self.results[path].issues])
        cleanup_count = len(self._primary_cleanup_candidates())
        similar_count = len([group for group in self.similar_groups if len(group.paths) >= 2])
        self.list_stats_var.set(
            f"共 {total} 张 | 已分析 {analyzed} | 问题 {issue_count} | 失败 {failed} | 待清理 {cleanup_count} | 相似组 {similar_count}"
        )

    def _refresh_tree_item(self, path: Path) -> bool:
        item_id = self.path_item_lookup.get(path)
        if not item_id or not self.tree.exists(item_id):
            return False
        if not self._matches_filter(self.results.get(path), self.errors.get(path)):
            self.tree.delete(item_id)
            self.item_lookup.pop(item_id, None)
            self.path_item_lookup.pop(path, None)
            return True
        self.tree.item(item_id, text=path.name, values=self._tree_row_values(path))
        return True

    def refresh_tree(self) -> None:
        self._prune_missing_paths()
        current_path = self._current_path()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_lookup.clear()
        self.path_item_lookup.clear()

        for path in self._sorted_paths():
            thumb = self.thumb_cache.get_tree_thumbnail(path)
            item_id = self.tree.insert("", "end", text=path.name, image=thumb, values=self._tree_row_values(path))
            self.item_lookup[item_id] = path
            self.path_item_lookup[path] = item_id
            if path == current_path:
                self.tree.selection_set(item_id)
        self._refresh_cleanup_tree()
        self._update_list_stats()

    def _matches_filter(self, result: AnalysisResult | None, error: str | None) -> bool:
        chosen = self.filter_var.get()
        if chosen == "全部":
            return True
        if error:
            return False
        if chosen == "仅问题图":
            return bool(result and result.issues)
        if not result:
            return False
        return any(issue.label == chosen or issue_display(issue) == chosen for issue in result.issues)

    def _current_path(self) -> Path | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.item_lookup.get(selection[0])

    def _select_path(self, path: Path) -> None:
        for item_id, item_path in self.item_lookup.items():
            if item_path == path:
                self.tree.selection_set(item_id)
                self.tree.see(item_id)
                self.show_preview(path)
                break

    def _select_cleanup_path(self, path: Path) -> None:
        for item_id, item_path in self.cleanup_item_lookup.items():
            if item_path == path:
                self.cleanup_tree.selection_set(item_id)
                self.cleanup_tree.see(item_id)
                break

    def _show_selection_summary(self, paths: list[Path]) -> None:
        selected = [path for path in paths if path in self.image_paths]
        if not selected:
            self._clear_hud_and_summary()
            return
        issue_count = 0
        analyzed_count = 0
        scene_types: dict[str, int] = {}
        exposure_types: dict[str, int] = {}
        color_types: dict[str, int] = {}
        cleanup_count = 0
        for path in selected:
            result = self.results.get(path)
            if result is None:
                continue
            analyzed_count += 1
            issue_count += int(bool(result.issues))
            scene_types[result.scene_type] = scene_types.get(result.scene_type, 0) + 1
            exposure_types[result.exposure_type] = exposure_types.get(result.exposure_type, 0) + 1
            color_types[result.color_type] = color_types.get(result.color_type, 0) + 1
            cleanup_count += int(bool(result.cleanup_candidates))

        self.chart.update_result(None)
        self.hud_name_var.set(f"已多选 {len(selected)} 张图片")
        self.hud_risk_var.set(f"已分析 {analyzed_count}/{len(selected)}")
        scene_label = "、".join(
            f"{display_name('scene_type', name)}:{count}" for name, count in list(scene_types.items())[:3]
        ) or "待分析"
        self.hud_tags_var.set(f"识别结果：问题图 {issue_count} 张 | 待清理 {cleanup_count} 张 | 场景 {scene_label}")
        self.hud_methods_var.set("推荐修复：多选状态下请使用“分析选中”或“批量修复勾选”")
        self._set_meta_summary("多选状态下不显示单张 EXIF 摘要。请切回单选查看详细属性。")
        lines = [
            f"当前多选 {len(selected)} 张图片。",
            f"已分析 {analyzed_count} 张，其中问题图 {issue_count} 张，待清理 {cleanup_count} 张。",
            "",
            "scene_type 汇总：",
        ]
        for name, count in scene_types.items():
            lines.append(f"- {display_name('scene_type', name)}（{name}）: {count}")
        lines.append("")
        lines.append("exposure_type 汇总：")
        for name, count in exposure_types.items():
            lines.append(f"- {display_name('exposure_type', name)}（{name}）: {count}")
        lines.append("")
        lines.append("color_type 汇总：")
        for name, count in color_types.items():
            lines.append(f"- {display_name('color_type', name)}（{name}）: {count}")
        lines.append("")
        lines.append("提示：")
        lines.append("- 可继续用 Ctrl/Shift 扩展多选。")
        lines.append("- “分析选中”会按当前选择批量分析。")
        lines.append("- “批量修复勾选”会优先处理当前多选；如无多选则回退到勾选状态。")
        self._set_summary("\n".join(lines))

    def on_tree_select(self, _event=None) -> None:
        paths = self._selected_tree_paths()
        if len(paths) > 1:
            self._show_selection_summary(paths)
            return
        path = paths[0] if paths else self._current_path()
        if path is not None:
            self.show_preview(path)

    def on_tree_click(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id:
            return
        if column == "#1":
            self.tree.selection_set(item_id)
            path = self.item_lookup.get(item_id)
            if path is None:
                return
            self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
            self.selected_flags[path].set(not self.selected_flags[path].get())
            self.refresh_tree()
            self._select_path(path)

    def on_cleanup_tree_select(self, _event=None) -> None:
        path = self._current_cleanup_path()
        if path is not None:
            self._select_path(path)

    def on_cleanup_tree_click(self, event) -> None:
        item_id = self.cleanup_tree.identify_row(event.y)
        column = self.cleanup_tree.identify_column(event.x)
        if not item_id:
            return
        self.cleanup_tree.selection_set(item_id)
        path = self.cleanup_item_lookup.get(item_id)
        if path is None:
            return
        if column == "#1":
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
            self.cleanup_flags[path].set(not self.cleanup_flags[path].get())
            self._refresh_cleanup_tree()
            self._select_cleanup_path(path)
            self._select_path(path)

    def select_cleanup_current(self) -> None:
        path = self._current_cleanup_path() or self._current_path()
        if path is None or path not in self._primary_cleanup_candidates():
            return
        self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
        self.cleanup_flags[path].set(True)
        self._refresh_cleanup_tree()
        self._select_path(path)

    def toggle_selected_cleanup_candidates(self) -> None:
        selection = self.cleanup_tree.selection()
        if not selection:
            return
        paths = [self.cleanup_item_lookup[item_id] for item_id in selection if item_id in self.cleanup_item_lookup]
        if not paths:
            return
        first_path = paths[0]
        self.cleanup_flags.setdefault(first_path, tk.BooleanVar(value=False))
        target_state = not self.cleanup_flags[first_path].get()
        for path in paths:
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
            self.cleanup_flags[path].set(target_state)
        self._refresh_cleanup_tree()
        self._select_cleanup_path(first_path)
        self._select_path(first_path)

    def select_all_cleanup_candidates(self) -> None:
        for path in self._primary_cleanup_candidates():
            self.cleanup_flags.setdefault(path, tk.BooleanVar(value=False))
            self.cleanup_flags[path].set(True)
        self._refresh_cleanup_tree()

    def unselect_all_cleanup_candidates(self) -> None:
        for flag in self.cleanup_flags.values():
            flag.set(False)
        self._refresh_cleanup_tree()

    def open_context_menu(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        if not item_id or self.list_menu is None:
            return
        if item_id not in self.tree.selection():
            self.tree.selection_set(item_id)
        self.list_menu.tk_popup(event.x_root, event.y_root)

    def remove_current_from_list(self) -> None:
        self.remove_selected_from_list()

    def remove_selected_from_list(self, _event=None) -> str:
        selection = self.tree.selection()
        if not selection:
            return "break"
        paths = [self.item_lookup[item_id] for item_id in selection if item_id in self.item_lookup]
        if not paths:
            return "break"
        removed_count = len(paths)
        for path in paths:
            self._remove_path_from_list(path, refresh=False)
        self.refresh_tree()
        if self.image_paths:
            self._select_path(self.image_paths[0])
        else:
            self._clear_hud_and_summary()
        self._log_console(f"list batch removed: {removed_count} image(s)")
        return "break"

    def select_all_list_items(self, _event=None) -> str:
        item_ids = self._visible_tree_item_ids()
        if item_ids:
            self.tree.selection_set(*item_ids)
            self.tree.focus(item_ids[0])
            self.tree.see(item_ids[0])
            self._show_selection_summary(self._selected_tree_paths())
        self._log_console(f"list selected all visible: {len(item_ids)} image(s)")
        return "break"

    def clear_list_selection(self, _event=None) -> str:
        self.tree.selection_remove(self.tree.selection())
        self._clear_hud_and_summary()
        self._log_console("list selection cleared")
        return "break"

    def invert_list_selection(self, _event=None) -> str:
        visible = self._visible_tree_item_ids()
        selected = set(self.tree.selection())
        new_selection = [item_id for item_id in visible if item_id not in selected]
        if new_selection:
            self.tree.selection_set(*new_selection)
            self.tree.focus(new_selection[0])
            self.tree.see(new_selection[0])
            self._show_selection_summary(self._selected_tree_paths())
        else:
            self.tree.selection_remove(self.tree.selection())
            self._clear_hud_and_summary()
        self._log_console(f"list selection inverted: {len(new_selection)} image(s)")
        return "break"

    def _merge_paths(self, paths: list[Path]) -> None:
        existing = set(self.image_paths)
        added = 0
        for path in paths:
            if path not in existing:
                self.image_paths.append(path)
                existing.add(path)
                self.selected_flags[path] = tk.BooleanVar(value=True)
                added += 1
            else:
                self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
        if paths:
            self._log_console(f"list merge: added={added} duplicate={len(paths) - added} total={len(self.image_paths)}")

    def _remove_path_from_list(self, path: Path, refresh: bool = True) -> None:
        if path in self.image_paths:
            self.image_paths = [item for item in self.image_paths if item != path]
        self.results.pop(path, None)
        self.errors.pop(path, None)
        self.selected_flags.pop(path, None)
        self.cleanup_flags.pop(path, None)
        self.thumb_cache.evict(path)
        self._prune_similar_groups()
        self._log_console(f"removed from list: {path}")
        if refresh:
            self.refresh_tree()
            if self.image_paths:
                self._select_path(self.image_paths[0])
            else:
                self._clear_hud_and_summary()

    def _clear_hud_and_summary(self) -> None:
        self.chart.update_result(None)
        self._current_preview_path = None
        self._large_preview_image = None
        if hasattr(self, "large_preview_label"):
            self.large_preview_label.configure(image="", text="选择图片后，这里会显示更大的预览图。")
        self.hud_name_var.set("未选择图片")
        self.hud_risk_var.set("风险值 --")
        self.hud_tags_var.set("识别结果：等待分析")
        self.hud_methods_var.set("推荐修复：等待分析")
        if hasattr(self, "meta_edit_button"):
            self.meta_edit_button.configure(state="disabled")
        self._set_meta_summary("当前列表为空，暂无可查看的属性信息。")
        self._set_summary("当前列表为空。可继续添加文件夹、拖入图片或手动选择单张图片。")

    def toggle_cleanup_flag(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        paths = [self.item_lookup[item_id] for item_id in selection if item_id in self.item_lookup]
        if not paths:
            return
        
        # Determine the target state based on the first item
        first_path = paths[0]
        self.selected_flags.setdefault(first_path, tk.BooleanVar(value=False))
        target_state = not self.selected_flags[first_path].get()

        for path in paths:
            self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
            self.selected_flags[path].set(target_state)
        self.refresh_tree()
        self._select_path(first_path)

    def select_problem_items(self) -> None:
        for path, result in self.results.items():
            self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
            self.selected_flags[path].set(bool(result.issues))
        self.refresh_tree()

    def select_current(self) -> None:
        path = self._current_path()
        if path is None:
            return
        self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
        self.selected_flags[path].set(True)
        self.refresh_tree()
        self._select_path(path)

    def unselect_current(self) -> None:
        path = self._current_path()
        if path is None:
            return
        self.selected_flags.setdefault(path, tk.BooleanVar(value=False))
        self.selected_flags[path].set(False)
        self.refresh_tree()
        self._select_path(path)

    def unselect_all(self) -> None:
        for flag in self.selected_flags.values():
            flag.set(False)
        self.refresh_tree()

    def show_preview(self, path: Path) -> None:
        result = self.results.get(path)
        error = self.errors.get(path)
        self._current_preview_path = path

        try:
            with Image.open(path) as img:
                image = ImageOps.exif_transpose(img).convert("RGB")
        except Exception as exc:
            self.chart.update_result(None)
            self._set_summary(f"无法加载预览：{exc}")
            self._set_meta_summary(f"文件：{path.name}\n\n读取失败：{exc}")
            self._update_hud(path, None, None, str(exc))
            self._large_preview_image = None
            if hasattr(self, "large_preview_label"):
                self.large_preview_label.configure(image="", text="无法加载预览图。")
            return
        self.chart.update_result(result)
        self._update_large_preview_image(image)
        self._update_hud(path, image, result, error)
        meta_summary = summarize_image_metadata(path)
        if hasattr(self, "meta_edit_button"):
            editable, reason = supports_metadata_edit(path, developer_unlocked=developer_session.unlocked)
            self.meta_edit_button.configure(state="normal" if editable else "disabled")
            if editable and developer_session.unlocked:
                edit_note = "可编辑字段：安全文本字段 + 开发者高级 EXIF 字段；ShapeYourPhoto 溯源字段仍会锁定。"
            else:
                edit_note = "可编辑字段：标题 / 描述、作者、版权、关键词 / 备注。" if editable else f"编辑状态：只读。{reason}"
            meta_summary = f"{meta_summary}\n\n{edit_note}"
        self._set_meta_summary(meta_summary)

        lines = [
            f"文件：{path.name}",
            f"路径：{path}",
            f"尺寸：{image.width} x {image.height}",
        ]
        if error:
            lines.append("")
            lines.append(f"分析失败：{error}")
        elif result:
            lines.append(f"总体风险值：{result.overall_score:.2f}")
            lines.append("")
            lines.append(
                f"人像判断：{'是' if result.portrait_likely else '否'} | "
                f"raw/有效/拒绝：{result.raw_face_count}/{result.validated_face_count}/{result.rejected_face_count}"
            )
            lines.append(f"人像类型：{display_name('portrait_type', result.portrait_type)}（{result.portrait_type}）")
            lines.append(f"场景类型：{display_name('scene_type', result.scene_type)}（{result.scene_type}）")
            lines.append(f"曝光类型：{display_name('exposure_type', result.exposure_type)}（{result.exposure_type}）")
            lines.append(f"色彩类型：{display_name('color_type', result.color_type)}（{result.color_type}）")
            lines.append(
                f"noise：{result.noise_level} ({result.noise_score:.4f}) | "
                f"denoise_profile={result.denoise_profile} | recommended={'是' if result.denoise_recommended else '否'}"
            )
            if result.portrait_scene_type:
                lines.append(f"人像场景：{display_name('portrait_scene_type', result.portrait_scene_type)}（{result.portrait_scene_type}）")
            if result.portrait_repair_policy:
                lines.append(f"修复策略：{display_name('repair_policy', result.portrait_repair_policy)}（{result.portrait_repair_policy}）")
            if result.portrait_rejection_reason:
                lines.append(f"未启用 portrait-aware：{result.portrait_rejection_reason}")
            rejected_face_notes = [
                f"{candidate.box} | {candidate.confidence:.2f} | {' / '.join(candidate.rejection_reasons)}"
                for candidate in result.face_candidates
                if not candidate.accepted and candidate.rejection_reasons
            ]
            if rejected_face_notes:
                lines.append("低置信度候选拒绝：")
                for note in rejected_face_notes[:4]:
                    lines.append(f"- {note}")
            if result.cleanup_candidates:
                primary_cleanup = sorted(
                    result.cleanup_candidates,
                    key=lambda candidate: (self._cleanup_severity_rank(candidate.severity), candidate.confidence),
                    reverse=True,
                )[0]
                lines.append("")
                lines.append("不适合保留的图片：")
                lines.append(
                    f"- {display_name('cleanup_reason', primary_cleanup.reason_code)} | "
                    f"{display_name('severity', primary_cleanup.severity)} | {primary_cleanup.confidence:.2f}"
                )
                lines.append(f"  原因：{self._cleanup_reason_summary(primary_cleanup)}")
            similar_marker = self._similar_marker_for_path(path)
            if similar_marker:
                lines.append("")
                lines.append(f"相似图片标记：{similar_marker}。可在“查看 -> 打开相似图片组”中复核。")
            if result.perf_notes:
                lines.append("性能提示：")
                for note in result.perf_notes:
                    lines.append(f"- {note}")
                lines.append("")
            lines.append("关键指标：")
            for metric in result.metrics:
                lines.append(f"- {metric.label}：{metric.value}")
            lines.append("")
            if result.issues:
                lines.append("识别问题：")
                for issue in result.issues:
                    lines.append(f"- {issue_display(issue)} | {issue.level} | {issue.score:.2f}")
                    lines.append(f"  判断：{issue.detail}")
                    lines.append(f"  建议：{issue.suggestion}")
                recommended = suggest_methods_for_result(result)
                lines.append("")
                lines.append(f"推荐修复：{'、'.join(get_method_labels(recommended)) or '暂无明确推荐'}")
            else:
                lines.append("识别结果：当前未发现明显质量问题。")
                lines.append("建议：可直接保留原图。")
        else:
            lines.append("")
            lines.append("识别结果：尚未分析。")
        self._set_summary("\n".join(lines))

    def _set_meta_summary(self, text: str) -> None:
        self.meta_text.config(state="normal")
        self.meta_text.delete("1.0", "end")
        self.meta_text.insert("1.0", text)
        self.meta_text.config(state="disabled")

    def _update_hud(self, path: Path, image: Image.Image | None, result: AnalysisResult | None, error: str | None) -> None:
        if image is None:
            self.hud_name_var.set(path.name)
        else:
            try:
                self.hud_name_var.set(f"{path.name}  |  {image.width} x {image.height}")
            except Exception:
                self.hud_name_var.set(path.name)
        if error:
            self.hud_risk_var.set("风险值 --")
            self.hud_tags_var.set(f"识别结果：分析失败 - {error}")
            self.hud_methods_var.set("推荐修复：请先确认图片能正常读取")
            return
        if result is None:
            self.hud_risk_var.set("风险值 --")
            self.hud_tags_var.set("识别结果：尚未分析")
            self.hud_methods_var.set("推荐修复：等待分析完成")
            return
        self.hud_risk_var.set(f"风险值 {result.overall_score:.2f}")
        similar_hint = " | 相似组" if self._similar_marker_for_path(path) else ""
        if result.issues:
            tags = "、".join(issue_display(issue) for issue in result.issues[:4])
            methods = "、".join(get_method_labels(suggest_methods_for_result(result))) or "暂无明确推荐"
            face_info = f" | raw/valid/reject {result.raw_face_count}/{result.validated_face_count}/{result.rejected_face_count}" if (result.raw_face_count or result.validated_face_count or result.rejected_face_count) else ""
            cleanup_hint = " | 可能不适合保留" if result.cleanup_candidates else ""
            self.hud_tags_var.set(f"识别结果：{tags}{face_info}{cleanup_hint}{similar_hint}")
            if result.denoise_recommended:
                methods = f"{methods} | 降噪:{result.denoise_profile}"
            if result.cleanup_candidates:
                primary_cleanup = sorted(
                    result.cleanup_candidates,
                    key=lambda candidate: (self._cleanup_severity_rank(candidate.severity), candidate.confidence),
                    reverse=True,
                )[0]
                self.hud_methods_var.set(
                    f"推荐修复：{methods} | 待核对：{display_name('cleanup_reason', primary_cleanup.reason_code)}"
                )
            else:
                self.hud_methods_var.set(f"推荐修复：{methods}")
        else:
            portrait_hint = (
                f" | {display_name('portrait_scene_type', result.portrait_scene_type)}"
                if result.portrait_likely and result.portrait_scene_type
                else ""
            )
            cleanup_hint = " | 可能不适合保留" if result.cleanup_candidates else ""
            self.hud_tags_var.set(f"识别结果：未发现明显问题{portrait_hint}{cleanup_hint}{similar_hint}")
            if result.portrait_rejection_reason:
                self.hud_methods_var.set(f"推荐修复：未启用人像策略，{result.portrait_rejection_reason}")
            else:
                self.hud_methods_var.set("推荐修复：可保留原图，无需额外修正")

    def _set_summary(self, text: str) -> None:
        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", text)
        self.summary_text.config(state="disabled")

    def _refresh_large_preview(self) -> None:
        path = getattr(self, "_current_preview_path", None)
        if path is None or not Path(path).exists() or not hasattr(self, "large_preview_label"):
            return
        try:
            with Image.open(path) as img:
                image = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return
        self._update_large_preview_image(image)

    def _update_large_preview_image(self, image: Image.Image) -> None:
        if not hasattr(self, "large_preview_label"):
            return
        width = max(320, self.large_preview_label.winfo_width() - 24)
        height = max(240, self.large_preview_label.winfo_height() - 24)
        preview = image.copy()
        preview.thumbnail((width, height), Image.Resampling.LANCZOS)
        self._large_preview_image = ImageTk.PhotoImage(preview)
        self.large_preview_label.configure(image=self._large_preview_image, text="")

    def edit_current_metadata(self) -> None:
        path = self._current_path()
        if path is None:
            messagebox.showinfo("提示", "请先选中一张图片。")
            return
        editable, reason = supports_metadata_edit(path, developer_unlocked=developer_session.unlocked)
        if not editable:
            messagebox.showinfo("只读", reason)
            return
        result = show_metadata_edit_dialog(self.root, path, developer_unlocked=developer_session.unlocked)
        if result.saved:
            self._log_console(f"metadata edited: {path.name}")
            self._set_meta_summary(summarize_image_metadata(path))
            messagebox.showinfo("保存完成", result.message)

    def export_selected(self) -> None:
        cleanup_primary = self._primary_cleanup_candidates()
        chosen = [path for path, flag in self.cleanup_flags.items() if flag.get() and path in cleanup_primary]
        if not chosen:
            chosen = [path for path, flag in self.selected_flags.items() if flag.get()]
        if not chosen:
            messagebox.showinfo("提示", "当前没有勾选需要处理的图片。")
            return
        output = export_cleanup_list(chosen, self._resolve_base_folder())
        self._log_console(f"exported cleanup list: {output}")
        self.status_var.set(f"已导出清理清单：{output}")
        messagebox.showinfo("完成", f"已导出清理清单：\n{output}")
