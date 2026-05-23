from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image

from ui.language import tr
from ui.window_titles import app_window_title
from dialog_factory import DialogSpec, finalize_dialog_window
from task_state import TaskManager
from window_layout import prepare_dialog_window


@dataclass
class GpsEditResult:
    saved: bool = False
    message: str = ""


def _tr_or(key: str, fallback: str) -> str:
    value = tr(key)
    return fallback if value == key else value


def _to_decimal(values, ref: str) -> float | None:
    try:
        deg, minutes, seconds = values
        value = float(deg) + float(minutes) / 60.0 + float(seconds) / 3600.0
        if str(ref).upper() in {"S", "W"}:
            value = -value
        return value
    except Exception:
        return None


def read_gps_decimal(path: Path) -> tuple[float | None, float | None]:
    with Image.open(path) as img:
        gps = img.getexif().get_ifd(34853)
    lat = _to_decimal(gps.get(2), gps.get(1, "N")) if gps else None
    lon = _to_decimal(gps.get(4), gps.get(3, "E")) if gps else None
    return lat, lon


def _dms(value: float):
    absolute = abs(value)
    deg = int(absolute)
    minutes_float = (absolute - deg) * 60.0
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60.0
    return (Fraction(deg, 1), Fraction(minutes, 1), Fraction(seconds).limit_denominator(1000000))


def write_gps_decimal(path: Path, latitude: float, longitude: float) -> Path:
    if not -90 <= latitude <= 90:
        raise ValueError("latitude")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude")
    backup = path.with_name(f"{path.stem}.gps-bak{path.suffix}")
    index = 1
    while backup.exists():
        backup = path.with_name(f"{path.stem}.gps-bak-{index}{path.suffix}")
        index += 1
    shutil.copy2(path, backup)
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            gps = exif.get_ifd(34853)
            gps[1] = "N" if latitude >= 0 else "S"
            gps[2] = _dms(latitude)
            gps[3] = "E" if longitude >= 0 else "W"
            gps[4] = _dms(longitude)
            gps[29] = datetime.utcnow().strftime("%Y:%m:%d")
            exif[34853] = gps
            save_kwargs = {"exif": exif.tobytes()}
            if img.info.get("icc_profile"):
                save_kwargs["icc_profile"] = img.info.get("icc_profile")
            if img.info.get("dpi"):
                save_kwargs["dpi"] = img.info.get("dpi")
            img.save(path, **save_kwargs)
    except Exception:
        try:
            shutil.copy2(backup, path)
        except Exception:
            pass
        raise
    return backup


class GpsEditDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, path: Path, log_callback=None, task_manager: TaskManager | None = None) -> None:
        super().__init__(parent)
        self.path = path
        self.result = GpsEditResult()
        self._log_callback = log_callback
        self.task_manager = task_manager or TaskManager(ui_dispatch=lambda callback: self.after(0, callback), max_workers=2)
        self._saving = False
        prepare_dialog_window(self, parent, title=app_window_title(tr("gps.title")), min_width=620, min_height=360)
        self.lat_var = tk.StringVar(value="")
        self.lon_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value=_tr_or("gps.loading", "正在读取 GPS 信息..."))

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        ttk.Label(outer, text=path.name, style="PanelTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(outer, text=tr("gps.desc"), wraplength=560).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 14))
        ttk.Label(outer, text=tr("gps.latitude")).grid(row=2, column=0, sticky="w")
        ttk.Entry(outer, textvariable=self.lat_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(outer, text=tr("gps.longitude")).grid(row=3, column=0, sticky="w")
        ttk.Entry(outer, textvariable=self.lon_var).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(outer, textvariable=self.status_var, wraplength=560).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        actions = ttk.Frame(outer)
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text=tr("gps.map_hint"), command=self._map_hint).grid(row=0, column=0, sticky="w")
        self._cancel_button = ttk.Button(actions, text=tr("meta.cancel"), command=self._cancel)
        self._cancel_button.grid(row=0, column=1, padx=(8, 0))
        self._save_button = ttk.Button(actions, text=tr("meta.save"), command=self._save, state="disabled")
        self._save_button.grid(row=0, column=2, padx=(8, 0))
        finalize_dialog_window(
            self,
            parent,
            DialogSpec(
                title=app_window_title(tr("gps.title")),
                min_width=620,
                min_height=360,
                fallback_width=660,
                fallback_height=390,
            ),
        )
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(20, self._start_gps_load)

    def _start_gps_load(self) -> None:
        def worker() -> tuple[float | None, float | None, Exception | None]:
            try:
                lat, lon = read_gps_decimal(self.path)
                error = None
            except Exception as exc:
                lat = lon = None
                error = exc
            return lat, lon, error

        self.task_manager.submit_worker(task_id=None, target=worker, on_done=lambda outcome: self._finish_gps_load(*outcome))

    def _finish_gps_load(self, lat: float | None, lon: float | None, error: Exception | None) -> None:
        if not self.winfo_exists():
            return
        if error is not None:
            self.status_var.set(_tr_or("gps.load_failed", "读取 GPS 信息失败：{error}").format(error=error))
            return
        self.lat_var.set("" if lat is None else f"{lat:.8f}")
        self.lon_var.set("" if lon is None else f"{lon:.8f}")
        self.status_var.set(tr("gps.empty") if lat is None or lon is None else tr("gps.existing"))
        self._save_button.configure(state="normal")

    def _map_hint(self) -> None:
        messagebox.showinfo(tr("gps.title"), tr("gps.map_placeholder"), parent=self)

    def _save(self) -> None:
        if self._saving:
            return
        try:
            lat = float(self.lat_var.get().strip())
            lon = float(self.lon_var.get().strip())
        except Exception as exc:
            messagebox.showerror(tr("gps.title"), tr("gps.save_failed").format(error=exc), parent=self)
            return
        self._saving = True
        self._save_button.configure(state="disabled")
        self._cancel_button.configure(state="disabled")
        self.status_var.set(_tr_or("gps.saving", "正在保存 GPS 信息..."))

        def worker() -> tuple[Path | None, Exception | None]:
            try:
                backup = write_gps_decimal(self.path, lat, lon)
                error = None
            except Exception as exc:
                backup = None
                error = exc
            return backup, error

        self.task_manager.submit_worker(
            task_id=None,
            target=worker,
            on_done=lambda outcome: self._finish_save(lat, lon, *outcome),
        )

    def _finish_save(self, lat: float, lon: float, backup: Path | None, error: Exception | None) -> None:
        if not self.winfo_exists():
            return
        self._saving = False
        self._save_button.configure(state="normal")
        self._cancel_button.configure(state="normal")
        if error is not None:
            self.status_var.set(tr("gps.existing"))
            messagebox.showerror(tr("gps.title"), tr("gps.save_failed").format(error=error), parent=self)
            return
        if self._log_callback:
            self._log_callback(f"gps metadata saved: {self.path.name} lat={lat:.6f} lon={lon:.6f}")
        backup_name = backup.name if backup is not None else tr("meta.no_visible_backup")
        self.result = GpsEditResult(True, tr("gps.saved").format(backup=backup_name))
        self.destroy()

    def _cancel(self) -> None:
        if self._saving:
            return
        self.destroy()


def show_gps_edit_dialog(parent: tk.Widget, path: Path, log_callback=None, task_manager: TaskManager | None = None) -> GpsEditResult:
    dialog = GpsEditDialog(parent, path, log_callback=log_callback, task_manager=task_manager)
    dialog.wait_window()
    return dialog.result
