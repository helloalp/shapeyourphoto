from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image

from ui.window_titles import app_window_title
from window_layout import center_window


SAFE_TEXT_TAGS = {
    "title": (270, "标题 / 描述"),
    "artist": (315, "作者"),
    "copyright": (33432, "版权"),
    "keywords": (40094, "关键词 / 备注"),
}

FORBIDDEN_TAG_LABELS = [
    "相机型号",
    "镜头型号",
    "拍摄时间",
    "EXIF Orientation",
    "ICC Profile",
    "软件内部标记",
]


@dataclass
class MetadataEditResult:
    saved: bool = False
    message: str = ""


def supports_metadata_edit(path: Path) -> tuple[bool, str]:
    suffix = path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".tif", ".tiff"}:
        return False, "当前只支持 JPEG / TIFF 的安全文本 EXIF 字段写入。"
    try:
        with Image.open(path) as img:
            img.getexif()
    except Exception as exc:
        return False, f"读取元数据失败：{exc}"
    return True, ""


class MetadataEditDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, path: Path) -> None:
        super().__init__(parent)
        self.path = path
        self.result = MetadataEditResult()
        self.title(app_window_title("编辑属性 / EXIF"))
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, False)
        self.minsize(620, 420)
        self.vars: dict[str, tk.StringVar] = {}

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(outer, text=path.name, style="PanelTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            outer,
            text="仅允许写入安全文本字段。不会修改相机/镜头、拍摄时间、Orientation、ICC 或软件内部标记。",
            wraplength=560,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))

        values = self._read_values()
        for row, (field_id, (_tag, label)) in enumerate(SAFE_TEXT_TAGS.items(), start=2):
            ttk.Label(outer, text=f"{label}：").grid(row=row, column=0, sticky="w", pady=5)
            var = tk.StringVar(value=values.get(field_id, ""))
            self.vars[field_id] = var
            ttk.Entry(outer, textvariable=var).grid(row=row, column=1, sticky="ew", pady=5)

        ttk.Label(
            outer,
            text="禁止字段：" + "、".join(FORBIDDEN_TAG_LABELS),
            wraplength=560,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 0))

        actions = ttk.Frame(outer)
        actions.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="取消", command=self._cancel).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(actions, text="保存", command=self._save).grid(row=0, column=2)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        center_window(self, 680, 460)

    def _read_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        try:
            with Image.open(self.path) as img:
                exif = img.getexif()
                for field_id, (tag, _label) in SAFE_TEXT_TAGS.items():
                    raw = exif.get(tag, "")
                    if isinstance(raw, bytes):
                        encoding = "utf-16le" if tag >= 40091 else "utf-8"
                        raw = raw.rstrip(b"\x00").decode(encoding, errors="replace")
                    values[field_id] = str(raw) if raw is not None else ""
        except Exception:
            pass
        return values

    def _save(self) -> None:
        if not messagebox.askyesno(
            "确认保存",
            "保存前会创建同目录 .metadata-bak 备份。确认写入这些安全文本字段吗？",
            parent=self,
        ):
            return
        backup = self.path.with_name(f"{self.path.stem}.metadata-bak{self.path.suffix}")
        try:
            index = 1
            while backup.exists():
                backup = self.path.with_name(f"{self.path.stem}.metadata-bak-{index}{self.path.suffix}")
                index += 1
            shutil.copy2(self.path, backup)
            with Image.open(self.path) as img:
                exif = img.getexif()
                for field_id, (tag, _label) in SAFE_TEXT_TAGS.items():
                    value = self.vars[field_id].get().strip()
                    if value:
                        exif[tag] = value.encode("utf-16le") + b"\x00\x00" if tag >= 40091 else value
                    elif tag in exif:
                        del exif[tag]
                img.save(self.path, exif=exif)
        except Exception as exc:
            try:
                if backup.exists():
                    shutil.copy2(backup, self.path)
            except Exception:
                pass
            messagebox.showerror("保存失败", f"写入失败，原文件已尽量恢复：\n{exc}", parent=self)
            return
        self.result = MetadataEditResult(True, f"已保存，备份：{backup}")
        self.destroy()

    def _cancel(self) -> None:
        self.result = MetadataEditResult(False, "")
        self.destroy()


def show_metadata_edit_dialog(parent: tk.Widget, path: Path) -> MetadataEditResult:
    dialog = MetadataEditDialog(parent, path)
    dialog.wait_window()
    return dialog.result
