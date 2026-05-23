from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import ExifTags, Image

from app_settings import load_app_settings
from file_safety import get_file_safety_service
from ui.language import tr
from ui.window_titles import app_window_title
from dialog_factory import DialogSpec, create_dialog_window, finalize_dialog_window
from task_state import TaskManager
from window_layout import center_window, prepare_dialog_window


SHAPEYOURPHOTO_MARKER = "shapeyourphoto"
EXIF_NAME_MAP = {key: value for key, value in ExifTags.TAGS.items()}

SAFE_TEXT_TAGS = {
    "title": (270, "标题 / 描述", "str"),
    "artist": (315, "作者", "str"),
    "copyright": (33432, "版权", "str"),
    "keywords": (40094, "关键词 / 备注", "xp"),
    "user_comment": (37510, "用户备注", "str"),
}

ADVANCED_TAGS = {
    "make": (271, "相机品牌", "str"),
    "model": (272, "相机型号", "str"),
    "lens_make": (42035, "镜头品牌", "str"),
    "lens_model": (42036, "镜头型号", "str"),
    "date_time": (306, "文件时间", "str"),
    "date_original": (36867, "拍摄时间", "str"),
    "exposure_time": (33434, "曝光时间", "str"),
    "f_number": (33437, "光圈值", "str"),
    "iso": (34855, "ISO", "str"),
    "focal_length": (37386, "焦距", "str"),
    "gps": (34853, "GPS 摘要", "readonly"),
}

EXIFTOOL_ADVANCED_FIELDS = {
    "xmp_title": ("XMP-dc:Title", "XMP 标题"),
    "xmp_description": ("XMP-dc:Description", "XMP 描述"),
    "xmp_creator": ("XMP-dc:Creator", "XMP 作者"),
    "xmp_rights": ("XMP-dc:Rights", "XMP 版权"),
    "iptc_keywords": ("IPTC:Keywords", "IPTC 关键词"),
    "iptc_caption": ("IPTC:Caption-Abstract", "IPTC 说明"),
}

ALWAYS_PROTECTED_TAGS = {
    274: "meta.readonly_orientation",
    305: "meta.protected",
    34675: "meta.readonly_binary",
    37500: "meta.readonly_makernote",
}


@dataclass
class MetadataEditResult:
    saved: bool = False
    message: str = ""


@dataclass
class FieldState:
    field_id: str
    tag: int
    label: str
    value: str
    encoding: str
    editable: bool
    reason: str = ""


def _clean_text(value: object, *, encoding: str = "str") -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        if encoding == "xp":
            return value.rstrip(b"\x00").decode("utf-16le", errors="replace").strip()
        return value.rstrip(b"\x00").decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _contains_marker(value: object) -> bool:
    cleaned = _clean_text(value).casefold()
    compact = re.sub(r"[\s_\-./\\:|]+", "", cleaned)
    return SHAPEYOURPHOTO_MARKER in compact or "shapeyourphoto" in cleaned or "shape your photo" in cleaned


def _is_protected_field(label: str, value: object) -> bool:
    return _contains_marker(label) or _contains_marker(value)


def _field_label(field_id: str, fallback: str) -> str:
    key = f"meta.field.{field_id}"
    value = tr(key)
    return value if value != key else fallback


def _tr_or(key: str, fallback: str) -> str:
    value = tr(key)
    return fallback if value == key else value


def _gps_summary(exif: Image.Exif) -> str:
    try:
        gps = exif.get_ifd(34853)
    except Exception:
        gps = {}
    if not gps:
        return ""
    parts = []
    for key, value in list(gps.items())[:8]:
        name = ExifTags.GPSTAGS.get(key, f"GPS {key}")
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def _exiftool_path() -> str | None:
    return shutil.which("exiftool")


def _read_exiftool_values(path: Path) -> dict[str, str]:
    exe = _exiftool_path()
    if not exe:
        return {}
    tags = [tag for tag, _label in EXIFTOOL_ADVANCED_FIELDS.values()]
    try:
        completed = subprocess.run(
            [exe, "-json", *[f"-{tag}" for tag in tags], str(path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        payload = json.loads(completed.stdout or "[]")
        if not payload:
            return {}
        first = payload[0]
        return {tag: _clean_text(first.get(tag.split(":")[-1], first.get(tag, ""))) for tag in tags}
    except Exception:
        return {}


def supports_metadata_edit(path: Path, *, developer_unlocked: bool | None = None) -> tuple[bool, str]:
    suffix = path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".tif", ".tiff"}:
        return False, "当前只支持 JPEG / TIFF 的 EXIF 文本字段写入。"
    try:
        with Image.open(path) as img:
            img.getexif()
    except Exception as exc:
        return False, f"读取元数据失败：{exc}"
    return True, ""


def _confirm_save_metadata(parent: tk.Widget) -> bool:
    dialog = create_dialog_window(
        parent,
        DialogSpec(
            title=app_window_title(tr("meta.confirm_title")),
            min_width=380,
            min_height=150,
            fallback_width=380,
            fallback_height=150,
            resizable=(False, False),
            modal=True,
        ),
    )
    result = tk.BooleanVar(value=False)

    outer = ttk.Frame(dialog, padding=18)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text=tr("meta.confirm_body"), wraplength=320).pack(anchor="w")

    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(16, 0))
    actions.columnconfigure(0, weight=1)

    def _finish(value: bool) -> None:
        result.set(value)
        dialog.destroy()

    ttk.Button(actions, text=tr("meta.cancel"), command=lambda: _finish(False)).grid(row=0, column=1, padx=(8, 0))
    ttk.Button(actions, text=tr("meta.save"), command=lambda: _finish(True)).grid(row=0, column=2)
    dialog.protocol("WM_DELETE_WINDOW", lambda: _finish(False))
    finalize_dialog_window(
        dialog,
        parent,
        DialogSpec(
            title=app_window_title(tr("meta.confirm_title")),
            min_width=380,
            min_height=150,
            fallback_width=380,
            fallback_height=150,
            resizable=(False, False),
        ),
    )
    dialog.wait_window()
    return bool(result.get())


class MetadataEditDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        path: Path,
        *,
        developer_unlocked: bool = False,
        task_manager: TaskManager | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = path
        self.developer_unlocked = False
        self.result = MetadataEditResult()
        self.task_manager = task_manager or TaskManager(ui_dispatch=lambda callback: self.after(0, callback), max_workers=2)
        prepare_dialog_window(
            self,
            parent,
            title=app_window_title(tr("meta.dialog_title")),
            min_width=700,
            min_height=520,
        )
        self.vars: dict[str, tk.StringVar] = {}
        self.fields: dict[str, FieldState] = {}
        self._saving = False

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        ttk.Label(outer, text=tr("meta.dialog_title"), style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        mode_text = tr("meta.editable_whitelist")
        ttk.Label(
            outer,
            text=mode_text,
            wraplength=660,
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        form = ttk.Frame(canvas)
        form.columnconfigure(1, weight=1)
        form_id = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=2, column=0, sticky="nsew")
        scroll.grid(row=2, column=1, sticky="ns")
        form.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(form_id, width=event.width))

        self._form = form
        self._loading_label = ttk.Label(form, text=_tr_or("meta.loading", "正在读取 EXIF 信息..."), padding=12)
        self._loading_label.grid(row=0, column=0, columnspan=3, sticky="w")

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        actions.columnconfigure(0, weight=1)
        self._cancel_button = ttk.Button(actions, text=tr("meta.cancel"), command=self._cancel)
        self._cancel_button.grid(row=0, column=1, padx=(8, 0))
        self._save_button = ttk.Button(actions, text=tr("meta.save"), command=self._save, state="disabled")
        self._save_button.grid(row=0, column=2)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        finalize_dialog_window(
            self,
            parent,
            DialogSpec(
                title=app_window_title(tr("meta.dialog_title")),
                min_width=700,
                min_height=520,
                fallback_width=780,
                fallback_height=620,
            ),
        )
        self.after(20, self._start_field_load)

    def _place_empty_entry_cursor(self, event, entry: ttk.Entry, value_var: tk.StringVar) -> str | None:
        if value_var.get().strip():
            return None
        entry.focus_set()
        entry.icursor(0)
        try:
            entry.selection_clear()
        except tk.TclError:
            pass
        return "break"

    def _read_fields(self) -> list[FieldState]:
        fields: list[FieldState] = []
        with Image.open(self.path) as img:
            exif = img.getexif()
            exiftool_values = _read_exiftool_values(self.path)
            exiftool_available = bool(_exiftool_path())
            fields.append(
                FieldState(
                    "filename",
                    -1,
                    _field_label("filename", "文件名"),
                    self.path.name,
                    "readonly",
                    False,
                    tr("meta.filename_readonly"),
                )
            )
            specs = dict(SAFE_TEXT_TAGS)
            specs.update(ADVANCED_TAGS)
            for field_id, (tag, label, encoding) in specs.items():
                label = _field_label(field_id, label)
                raw = _gps_summary(exif) if tag == 34853 else exif.get(tag, "")
                value = _clean_text(raw, encoding=encoding)
                reason = ""
                editable = field_id in SAFE_TEXT_TAGS
                if not editable:
                    reason = tr("meta.readonly_camera")
                if tag in ALWAYS_PROTECTED_TAGS:
                    editable = False
                    reason_key = ALWAYS_PROTECTED_TAGS[tag]
                    reason = tr(reason_key) if reason_key != "meta.protected" else tr("meta.protected")
                if _is_protected_field(label, raw):
                    editable = False
                    reason = tr("meta.protected")
                fields.append(FieldState(field_id, tag, label, value, encoding, editable, reason))
            for field_id, (tool_tag, label) in EXIFTOOL_ADVANCED_FIELDS.items():
                label = _field_label(field_id, label)
                value = exiftool_values.get(tool_tag, "")
                editable = exiftool_available
                reason = "" if editable else tr("meta.exiftool_required")
                if _is_protected_field(label, value):
                    editable = False
                    reason = tr("meta.protected")
                fields.append(FieldState(field_id, 0, label, value, f"exiftool:{tool_tag}", editable, reason))
        return fields

    def _start_field_load(self) -> None:
        def worker() -> tuple[list[FieldState], Exception | None]:
            try:
                fields = self._read_fields()
                error = None
            except Exception as exc:
                fields = []
                error = exc
            return fields, error

        self.task_manager.submit_worker(
            task_id=None,
            target=worker,
            on_done=lambda outcome: self._finish_field_load(*outcome),
        )

    def _finish_field_load(self, fields: list[FieldState], error: Exception | None) -> None:
        if not self.winfo_exists():
            return
        if self._loading_label.winfo_exists():
            self._loading_label.destroy()
        if error is not None:
            ttk.Label(
                self._form,
                text=_tr_or("meta.load_failed", "无法读取这张图片的属性信息，请查看 Console。"),
                foreground="#8a1f11",
                padding=12,
            ).grid(
                row=0,
                column=0,
                columnspan=3,
                sticky="w",
            )
            return
        for row, field in enumerate(fields, start=0):
            self.fields[field.field_id] = field
            ttk.Label(self._form, text=f"{field.label}:").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 8))
            var = tk.StringVar(value=field.value)
            self.vars[field.field_id] = var
            entry = ttk.Entry(self._form, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", pady=5)
            entry.bind("<Button-1>", lambda event, widget=entry, value_var=var: self._place_empty_entry_cursor(event, widget, value_var))
            entry.bind("<ButtonRelease-1>", lambda event, widget=entry, value_var=var: self._place_empty_entry_cursor(event, widget, value_var))
            if not field.editable:
                entry.configure(state="readonly")
                ttk.Label(self._form, text=field.reason, foreground="#666666", wraplength=220).grid(row=row, column=2, sticky="w", padx=(8, 0))
        self._save_button.configure(state="normal")

    def _encode_value(self, field: FieldState, value: str) -> object:
        clean = value.strip()
        if not clean:
            return ""
        if field.encoding == "xp":
            return clean.encode("utf-16le") + b"\x00\x00"
        return clean

    def _save(self) -> None:
        if self._saving:
            return
        if not _confirm_save_metadata(self):
            return
        settings = load_app_settings()
        keep_backup = bool(getattr(settings, "metadata_keep_visible_backup", False))
        values = {field_id: value_var.get().strip() for field_id, value_var in self.vars.items()}
        self._saving = True
        self._save_button.configure(state="disabled")
        self._cancel_button.configure(state="disabled")

        def _writer(target: Path) -> None:
            with Image.open(self.path) as img:
                exif = img.getexif()
                exiftool_updates: list[tuple[str, str]] = []
                for field_id, field in self.fields.items():
                    if not field.editable or field.tag < 0:
                        continue
                    if field.encoding.startswith("exiftool:"):
                        tool_tag = field.encoding.split(":", 1)[1]
                        new_value = values.get(field_id, "")
                        if _is_protected_field(field.label, new_value):
                            raise RuntimeError(tr("meta.protected"))
                        exiftool_updates.append((tool_tag, new_value))
                        continue
                    old_value = exif.get(field.tag, "")
                    new_value = values.get(field_id, "")
                    if _is_protected_field(field.label, old_value) or _is_protected_field(field.label, new_value):
                        raise RuntimeError(tr("meta.protected"))
                    encoded = self._encode_value(field, new_value)
                    if encoded:
                        exif[field.tag] = encoded
                    elif field.tag in exif:
                        del exif[field.tag]
                save_kwargs = {"exif": exif}
                if img.info.get("icc_profile"):
                    save_kwargs["icc_profile"] = img.info.get("icc_profile")
                if img.info.get("dpi"):
                    save_kwargs["dpi"] = img.info.get("dpi")
                img.save(target, **save_kwargs)
            if exiftool_updates:
                exe = _exiftool_path()
                if not exe:
                    raise RuntimeError("exiftool 后端不可用，无法写入高级 GPS/XMP/IPTC 字段。")
                args = [exe, "-overwrite_original"]
                args.extend(f"-{tag}={value}" for tag, value in exiftool_updates)
                args.append(str(target))
                subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")

        def worker():
            return get_file_safety_service().transactional_overwrite(
                self.path,
                _writer,
                keep_user_backup=keep_backup,
                visible_backup_dir=self.path.parent / ".metadata-bak",
            )

        self.task_manager.submit_worker(task_id=None, target=worker, on_done=self._finish_save)

    def _finish_save(self, result) -> None:
        if not self.winfo_exists():
            return
        self._saving = False
        self._save_button.configure(state="normal")
        self._cancel_button.configure(state="normal")
        if not result.ok:
            messagebox.showerror(tr("meta.save_failed_title"), tr("meta.save_failed_body").format(error=result.message), parent=self)
            return
        backup_text = str(result.backup) if result.backup else tr("meta.no_visible_backup")
        self.result = MetadataEditResult(True, tr("meta.saved").format(backup=backup_text))
        self.destroy()

    def _cancel(self) -> None:
        if self._saving:
            return
        self.result = MetadataEditResult(False, "")
        self.destroy()


def show_metadata_edit_dialog(
    parent: tk.Widget,
    path: Path,
    *,
    developer_unlocked: bool = False,
    task_manager: TaskManager | None = None,
) -> MetadataEditResult:
    dialog = MetadataEditDialog(parent, path, developer_unlocked=developer_unlocked, task_manager=task_manager)
    dialog.wait_window()
    return dialog.result
