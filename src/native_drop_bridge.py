"""Windows OLE drag-and-drop bridge backed by the Rust native module."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from pathlib import Path
from typing import Callable, Iterable


class RustOleDropTarget:
    """Register Tk HWNDs as OLE DropTargets and poll path events on the UI thread."""

    backend_name = "rust-ole"

    def __init__(
        self,
        window: tk.Misc,
        callback: Callable[[Iterable[Path]], None],
        *,
        zones: Iterable[tk.Misc] = (),
        diagnostic_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.window = window
        self.callback = callback
        self.zones = tuple(zones)
        self.diagnostic_callback = diagnostic_callback
        self._dll: ctypes.WinDLL | None = None
        self._timer_id: str | None = None
        self._installed = False

    def install(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Rust OLE drop bridge is only available on Windows")
        self._dll = self._load_library()
        self._configure_exports(self._dll)
        self.window.update_idletasks()
        hwnds = self._collect_hwnds()
        if not hwnds:
            raise RuntimeError("No Tk HWND is available for native drop registration")
        failures: list[str] = []
        installed = 0
        for hwnd in hwnds:
            result = int(self._dll.syp_drop_register(hwnd))
            if result > 0:
                installed += 1
            else:
                failures.append(f"HWND {hwnd}: HRESULT/result {result}")
        if installed == 0:
            self._dll.syp_drop_shutdown()
            raise RuntimeError("; ".join(failures) or "native registration rejected all windows")
        self._installed = True
        if failures:
            self._diagnose("native drop partially registered: " + "; ".join(failures))
        self._timer_id = self.window.after(40, self._poll)

    def uninstall(self) -> None:
        if self._timer_id is not None:
            try:
                self.window.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            self._timer_id = None
        if self._dll is not None and self._installed:
            self._dll.syp_drop_shutdown()
        self._installed = False

    def _poll(self) -> None:
        if not self._installed or self._dll is None:
            return
        try:
            capacity = 8192
            while True:
                buffer = (ctypes.c_uint16 * capacity)()
                count = int(self._dll.syp_drop_poll(buffer, capacity))
                if count == 0:
                    break
                if count > capacity:
                    capacity = count
                    continue
                values = list(buffer[:count])
                pieces: list[str] = []
                current: list[int] = []
                for value in values:
                    if value == 0:
                        if current:
                            pieces.append(bytes(ctypes.c_uint16(*current)).decode("utf-16-le"))
                            current = []
                        continue
                    current.append(value)
                paths = [Path(value) for value in pieces if value]
                if paths:
                    self.callback(paths)
                capacity = 8192
        except Exception as exc:
            self._diagnose(f"native drop poll failed: {exc}")
        finally:
            if self._installed:
                self._timer_id = self.window.after(40, self._poll)

    def _collect_hwnds(self) -> list[int]:
        result: list[int] = []
        for widget in (self.window, *self.zones):
            try:
                hwnd = int(widget.winfo_id())
            except (AttributeError, tk.TclError, ValueError):
                continue
            if hwnd and hwnd not in result:
                result.append(hwnd)
        return result

    def _load_library(self) -> ctypes.WinDLL:
        project_root = Path(__file__).resolve().parent.parent
        names = ("shapeyourphoto_windows_drop.dll",)
        candidates = [
            Path(sys.executable).resolve().parent / names[0],
            project_root / "native" / "windows-drop" / "target" / "release" / names[0],
            project_root / "native" / "windows-drop" / "target" / "debug" / names[0],
            project_root / names[0],
        ]
        for path in candidates:
            if path.exists():
                return ctypes.WinDLL(str(path))
        raise RuntimeError("shapeyourphoto_windows_drop.dll was not found")

    @staticmethod
    def _configure_exports(dll: ctypes.WinDLL) -> None:
        dll.syp_drop_register.argtypes = [ctypes.c_ssize_t]
        dll.syp_drop_register.restype = ctypes.c_int
        dll.syp_drop_poll.argtypes = [ctypes.POINTER(ctypes.c_uint16), ctypes.c_size_t]
        dll.syp_drop_poll.restype = ctypes.c_size_t
        dll.syp_drop_shutdown.argtypes = []
        dll.syp_drop_shutdown.restype = None

    def _diagnose(self, message: str) -> None:
        if self.diagnostic_callback is not None:
            self.diagnostic_callback(message)
        else:
            print(f"[native_drop_bridge] {message}", file=sys.stderr)
