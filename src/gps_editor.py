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
from window_layout import center_window, prepare_dialog_window


@dataclass
class GpsEditResult:
    saved: bool = False
    message: str = ""


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
    def __init__(self, parent: tk.Widget, path: Path, log_callback=None) -> None:
        super().__init__(parent)
        self.path = path
        self.result = GpsEditResult()
        self._log_callback = log_callback
        prepare_dialog_window(self, parent, title=app_window_title(tr("gps.title")), min_width=620, min_height=360)
        lat, lon = read_gps_decimal(path)
        self.lat_var = tk.StringVar(value="" if lat is None else f"{lat:.8f}")
        self.lon_var = tk.StringVar(value="" if lon is None else f"{lon:.8f}")
        self.status_var = tk.StringVar(value=tr("gps.empty") if lat is None or lon is None else tr("gps.existing"))

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
        ttk.Button(actions, text=tr("meta.cancel"), command=self._cancel).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(actions, text=tr("meta.save"), command=self._save).grid(row=0, column=2, padx=(8, 0))
        center_window(self, 660, 390)

    def _map_hint(self) -> None:
        messagebox.showinfo(tr("gps.title"), tr("gps.map_placeholder"), parent=self)

    def _save(self) -> None:
        try:
            lat = float(self.lat_var.get().strip())
            lon = float(self.lon_var.get().strip())
            backup = write_gps_decimal(self.path, lat, lon)
        except Exception as exc:
            messagebox.showerror(tr("gps.title"), tr("gps.save_failed").format(error=exc), parent=self)
            return
        if self._log_callback:
            self._log_callback(f"gps metadata saved: {self.path.name} lat={lat:.6f} lon={lon:.6f}")
        self.result = GpsEditResult(True, tr("gps.saved").format(backup=backup.name))
        self.destroy()

    def _cancel(self) -> None:
        self.destroy()


def show_gps_edit_dialog(parent: tk.Widget, path: Path, log_callback=None) -> GpsEditResult:
    dialog = GpsEditDialog(parent, path, log_callback=log_callback)
    dialog.wait_window()
    return dialog.result
