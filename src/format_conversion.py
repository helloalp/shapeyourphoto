from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, PngImagePlugin

from app_metadata import APP_VERSION
from file_safety import get_file_safety_service
from task_state import TaskManager, TaskRecord, TaskStateMachine, TaskStatus
from ui.language import tr
from ui.window_titles import app_window_title
from dialog_factory import DialogSpec, finalize_dialog_window
from window_layout import prepare_dialog_window


FORMATS = ("PNG", "JPG", "WebP")
SOFTWARE_TAG = f"Converted by ShapeYourPhoto v{APP_VERSION}"


@dataclass
class ConversionResult:
    source: Path
    output: Path | None
    ok: bool
    message: str
    skipped: bool = False


def _default_output_dir(paths: list[Path]) -> Path:
    parent = paths[0].parent if paths else Path.cwd()
    return parent / "fmt_output"


def _output_path(source: Path, output_dir: Path, target_format: str) -> Path:
    suffix = ".jpg" if target_format == "JPG" else f".{target_format.lower()}"
    return get_file_safety_service().unique_path(output_dir / f"{source.stem}{suffix}")


def _atomic_save(image: Image.Image, target: Path, fmt: str, save_kwargs: dict[str, object]) -> None:
    result = get_file_safety_service().atomic_save_image(image, target, fmt, save_kwargs)
    if not result.ok:
        raise RuntimeError(result.message)


def _png_info(raw: Image.Image) -> PngImagePlugin.PngInfo:
    info = PngImagePlugin.PngInfo()
    info.add_text("Software", SOFTWARE_TAG)
    for key in ("Description", "Author", "Creation Time", "XML:com.adobe.xmp"):
        value = raw.info.get(key)
        if isinstance(value, str) and value:
            info.add_text(key, value)
    return info


def _save_kwargs(raw: Image.Image, target_format: str) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    save_kwargs: dict[str, object] = {}
    exif = raw.getexif()
    if exif:
        exif[274] = 1
        exif[305] = SOFTWARE_TAG
        save_kwargs["exif"] = exif.tobytes()
    if raw.info.get("icc_profile"):
        save_kwargs["icc_profile"] = raw.info["icc_profile"]
    if raw.info.get("dpi"):
        save_kwargs["dpi"] = raw.info["dpi"]
    for key in ("xmp", "iptc"):
        if raw.info.get(key) is not None:
            save_kwargs[key] = raw.info[key]
    fmt = target_format.upper()
    if fmt == "PNG":
        save_kwargs["pnginfo"] = _png_info(raw)
    if fmt == "JPG":
        if raw.mode in {"RGBA", "LA", "P"} and ("transparency" in raw.info or raw.mode in {"RGBA", "LA"}):
            warnings.append("JPG does not support transparency; alpha was flattened to RGB.")
        warnings.append("JPG is high quality, not mathematically lossless.")
    return save_kwargs, warnings


def convert_image_loss_preserving(source: Path, output_dir: Path, target_format: str) -> ConversionResult:
    try:
        target = _output_path(source, output_dir, target_format)
        with Image.open(source) as raw:
            save_kwargs, warnings = _save_kwargs(raw, target_format)
            image = ImageOps.exif_transpose(raw)
            fmt = target_format.upper()
            if fmt == "PNG":
                _atomic_save(image, target, "PNG", {"compress_level": 0, **save_kwargs})
            elif fmt == "WEBP":
                _atomic_save(image, target, "WEBP", {"lossless": True, "quality": 100, "method": 6, **save_kwargs})
            elif fmt == "JPG":
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                _atomic_save(image, target, "JPEG", {"quality": 100, "subsampling": 0, "optimize": False, **save_kwargs})
            else:
                raise ValueError(target_format)
        message = "ok" if not warnings else " ".join(warnings)
        return ConversionResult(source, target, True, message)
    except Exception as exc:
        return ConversionResult(source, None, False, str(exc))


class FormatConversionDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, paths: list[Path], log_callback=None, task_manager: TaskManager | None = None) -> None:
        super().__init__(parent)
        self.paths = [path for path in paths if path.exists()]
        self._log_callback = log_callback
        self._task_manager = task_manager or TaskManager(ui_dispatch=lambda callback: self.after(0, callback), max_workers=1)
        self._cancel_event = threading.Event()
        self._finish_after_current = threading.Event()
        self._running = False
        self._task_record: TaskRecord | None = None
        self._created_outputs: list[Path] = []
        self._started_at = 0.0
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()
        self.output_var = tk.StringVar(value=str(_default_output_dir(self.paths)))
        self.format_var = tk.StringVar(value=FORMATS[0])
        self.status_var = tk.StringVar(value=tr("format.hint").format(count=len(self.paths)))
        self.detail_var = tk.StringVar(value="")
        self.count_var = tk.StringVar(value="")
        self._size_notice_var = tk.StringVar(value="")
        prepare_dialog_window(self, parent, title=app_window_title(tr("format.title")), min_width=780, min_height=560)
        self.protocol("WM_DELETE_WINDOW", self._close_or_cancel)

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text=tr("format.title"), style="PanelTitle.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(outer, text=tr("format.desc"), wraplength=720, justify="left").grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 14))
        ttk.Label(outer, text=tr("format.target")).grid(row=2, column=0, sticky="w")
        self.format_box = ttk.Combobox(outer, textvariable=self.format_var, values=list(FORMATS), state="readonly", width=12)
        self.format_box.grid(row=2, column=1, sticky="w")
        ttk.Label(outer, text=tr("format.output_dir")).grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.output_entry = ttk.Entry(outer, textvariable=self.output_var)
        self.output_entry.grid(row=3, column=1, sticky="ew", pady=(10, 0), padx=(8, 8))
        self.choose_button = ttk.Button(outer, text=tr("format.choose_dir"), command=self._choose_dir)
        self.choose_button.grid(row=3, column=2, sticky="e", pady=(10, 0))

        list_frame = ttk.Frame(outer)
        list_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.file_list = tk.Listbox(list_frame, height=12, activestyle="dotbox", exportselection=False)
        self.file_list.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        x_scroll = ttk.Scrollbar(list_frame, orient="horizontal", command=self.file_list.xview)
        self.file_list.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        for path in self.paths:
            self.file_list.insert("end", path.name)

        self.progress = ttk.Progressbar(outer, maximum=max(1, len(self.paths)), value=0)
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Label(outer, textvariable=self.count_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(outer, textvariable=self.detail_var, wraplength=720).grid(row=7, column=0, columnspan=3, sticky="ew")

        actions = ttk.Frame(outer)
        actions.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        actions.columnconfigure(1, weight=1)
        ttk.Label(actions, textvariable=self._size_notice_var).grid(row=0, column=0, sticky="w")
        ttk.Label(actions, textvariable=self.status_var, wraplength=300).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.cancel_button = ttk.Button(actions, text=tr("action.cancel"), command=self._cancel_and_rollback, state="disabled")
        self.stop_button = ttk.Button(actions, text=tr("format.finish_after_current"), command=self._finish_after_current_request, state="disabled")
        self.start_button = ttk.Button(actions, text=tr("format.start"), command=self._start)
        self.close_button = ttk.Button(actions, text=tr("action.close"), command=self._close_or_cancel)
        self.cancel_button.grid(row=0, column=2, padx=(8, 0))
        self.stop_button.grid(row=0, column=3, padx=(8, 0))
        self.start_button.grid(row=0, column=4, padx=(8, 0))
        self.close_button.grid(row=0, column=5, padx=(8, 0))

        finalize_dialog_window(
            self,
            parent,
            DialogSpec(
                title=app_window_title(tr("format.title")),
                min_width=780,
                min_height=560,
                fallback_width=860,
                fallback_height=680,
            ),
            size_notice_var=self._size_notice_var,
        )
        self.after(40, self._drain_ui_queue)

    def _dispatch_ui(self, callback) -> None:
        self._ui_queue.put(callback)

    def _drain_ui_queue(self) -> None:
        drained = 0
        try:
            while drained < 80:
                callback = self._ui_queue.get_nowait()
                if self.winfo_exists():
                    callback()
                drained += 1
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            alive = self.winfo_exists()
        except tk.TclError:
            return
        if alive:
            self.after(1 if drained >= 80 else 40, self._drain_ui_queue)

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(parent=self, initialdir=self.output_var.get() or str(Path.cwd()))
        if chosen:
            self.output_var.set(chosen)

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _set_running_controls(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.start_button.configure(state=state)
        self.format_box.configure(state="disabled" if running else "readonly")
        self.output_entry.configure(state=state)
        self.choose_button.configure(state=state)
        self.cancel_button.configure(state="normal" if running else "disabled")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.close_button.configure(text=tr("action.cancel") if running else tr("action.close"))

    def _elapsed_text(self) -> str:
        elapsed = max(0, int(time.monotonic() - self._started_at))
        minutes, seconds = divmod(elapsed, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _update_progress(self, index: int, total: int, filename: str, ok: int, failed: int, skipped: int) -> None:
        self.progress.configure(value=index, maximum=max(1, total))
        self.count_var.set(
            tr("format.progress_counts").format(
                index=index,
                total=total,
                ok=ok,
                failed=failed,
                skipped=skipped,
                elapsed=self._elapsed_text(),
            )
        )
        self.detail_var.set(tr("format.current_file").format(filename=filename))
        if 0 < index <= self.file_list.size():
            self.file_list.selection_clear(0, "end")
            self.file_list.selection_set(index - 1)
            self.file_list.see(index - 1)

    def _start(self) -> None:
        if not self.paths:
            messagebox.showinfo(tr("format.title"), tr("format.no_selection"), parent=self)
            return
        self._running = True
        self._cancel_event.clear()
        self._finish_after_current.clear()
        self._created_outputs.clear()
        self._started_at = time.monotonic()
        self._task_record = self._task_manager.create(
            kind="format_conversion",
            name=f"format:{self.format_var.get()}",
            total=max(1, len(self.paths)),
            cancel_event=self._cancel_event,
            exclusive=False,
        )
        self._set_running_controls(True)
        target_format = self.format_var.get()
        output_dir = Path(self.output_var.get() or str(_default_output_dir(self.paths)))
        self._log(f"format conversion started: count={len(self.paths)} target={target_format} output={output_dir}")

        def worker() -> None:
            ok = failed = skipped = 0
            results: list[ConversionResult] = []
            total = len(self.paths)
            for offset, path in enumerate(self.paths, start=1):
                if self._cancel_event.is_set() or self._finish_after_current.is_set():
                    skipped += total - offset + 1
                    results.extend(ConversionResult(item, None, False, "not started", skipped=True) for item in self.paths[offset - 1 :])
                    break
                self._dispatch_ui(lambda i=offset, p=path, o=ok, f=failed, s=skipped: self._update_progress(i, total, p.name, o, f, s))
                result = convert_image_loss_preserving(path, output_dir, target_format)
                results.append(result)
                if result.ok and result.output is not None:
                    ok += 1
                    self._created_outputs.append(result.output)
                    self._log(f"format converted: {path.name} -> {result.output} | {result.message}")
                else:
                    failed += 1
                    self._log(f"format conversion failed: {path.name} | {result.message}")
                self._dispatch_ui(lambda i=offset, p=path, o=ok, f=failed, s=skipped: self._update_progress(i, total, p.name, o, f, s))
            self._dispatch_ui(lambda r=results, o=ok, f=failed, s=skipped: self._finish(r, o, f, s, output_dir))

        self._task_manager.submit_worker(task_id=self._task_record.task_id, target=worker)

    def _finish(self, results: list[ConversionResult], ok: int, failed: int, skipped: int, output_dir: Path) -> None:
        self._running = False
        self._set_running_controls(False)
        if self._cancel_event.is_set():
            if self._task_record is not None and self._task_record.is_active:
                TaskStateMachine(self._task_record).transition(TaskStatus.CANCELING)
            rolled = self._rollback_outputs()
            if self._task_record is not None and self._task_record.is_active:
                TaskStateMachine(self._task_record).transition(TaskStatus.CANCELED)
            self.status_var.set(tr("format.canceled").format(rolled=rolled))
            self._log(f"format conversion canceled: rolled_back={rolled} failed={failed} skipped={skipped}")
        elif self._finish_after_current.is_set():
            if self._task_record is not None and self._task_record.is_active:
                TaskStateMachine(self._task_record).transition(TaskStatus.COMPLETED)
            self.status_var.set(tr("format.early_done").format(ok=ok, failed=failed, skipped=skipped, output=output_dir))
            self._log(f"format conversion stopped early: success={ok} failed={failed} skipped={skipped}")
        else:
            if self._task_record is not None and self._task_record.is_active:
                TaskStateMachine(self._task_record).transition(TaskStatus.COMPLETED)
            self.status_var.set(tr("format.done").format(ok=ok, failed=failed, output=output_dir))
            self._log(f"format conversion finished: success={ok} failed={failed} skipped={skipped}")
        if failed:
            messagebox.showwarning(tr("format.title"), self.status_var.get(), parent=self)

    def _rollback_outputs(self) -> int:
        rolled = 0
        for index, path in enumerate(list(reversed(self._created_outputs)), start=1):
            self.detail_var.set(tr("format.rollback_progress").format(index=index, total=len(self._created_outputs), filename=path.name))
            try:
                if path.exists():
                    get_file_safety_service().move_to_quarantine(path, reason="format rollback")
                    rolled += 1
            except OSError as exc:
                self._log(f"format rollback failed: {path} | {exc}")
        self._created_outputs.clear()
        self._log(f"format rollback complete: rolled_back={rolled}")
        return rolled

    def _cancel_and_rollback(self) -> None:
        if not self._running:
            return
        self._log("format conversion cancel requested")
        self.status_var.set(tr("format.canceling"))
        if self._task_record is not None and self._task_record.status == TaskStatus.RUNNING:
            TaskStateMachine(self._task_record).transition(TaskStatus.CANCEL_REQUESTED)
        self._cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")

    def _finish_after_current_request(self) -> None:
        if not self._running:
            return
        self._log("format conversion finish-after-current requested")
        self.status_var.set(tr("format.finishing_after_current"))
        self._finish_after_current.set()
        self.stop_button.configure(state="disabled")

    def _close_or_cancel(self) -> None:
        if self._running:
            self._cancel_and_rollback()
            return
        self.destroy()


def show_format_conversion_dialog(parent: tk.Widget, paths: list[Path], log_callback=None, task_manager: TaskManager | None = None) -> None:
    FormatConversionDialog(parent, paths, log_callback=log_callback, task_manager=task_manager)
