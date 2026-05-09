"""Windows 原生拖拽实现。

非 Windows 平台请改用 dnd_support.py 的跨平台分派；本文件仅在 win32 上做实际工作，
其他平台导出一个空壳 WindowsFileDropTarget 以保持旧代码 import 兼容。
"""

from __future__ import annotations

import tkinter as tk

from paths import IS_WIN


if IS_WIN:
    import ctypes
    from ctypes import wintypes
    from pathlib import Path

    WM_DROPFILES = 0x0233
    WM_COPYDATA = 0x004A
    WM_COPYGLOBALDATA = 0x0049
    GWL_WNDPROC = -4
    MSGFLT_ALLOW = 1
    LONG_PTR = getattr(wintypes, "LONG_PTR", ctypes.c_ssize_t)
    LRESULT = getattr(wintypes, "LRESULT", ctypes.c_ssize_t)

    def _iter_drop_files(hdrop) -> list[Path]:
        shell32 = ctypes.windll.shell32
        count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        results: list[Path] = []
        for index in range(count):
            length = shell32.DragQueryFileW(hdrop, index, None, 0) + 1
            buffer = ctypes.create_unicode_buffer(length)
            shell32.DragQueryFileW(hdrop, index, buffer, length)
            results.append(Path(buffer.value))
        shell32.DragFinish(hdrop)
        return results


    def _set_window_proc(user32, hwnd: int, wnd_proc) -> int:
        proc_value = ctypes.cast(wnd_proc, ctypes.c_void_p).value
        set_window_long_ptr = getattr(user32, "SetWindowLongPtrW", None)
        if set_window_long_ptr is not None:
            set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
            set_window_long_ptr.restype = LONG_PTR
            return int(set_window_long_ptr(hwnd, GWL_WNDPROC, proc_value))
        set_window_long = user32.SetWindowLongW
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        set_window_long.restype = ctypes.c_long
        return int(set_window_long(hwnd, GWL_WNDPROC, proc_value))


    def _restore_window_proc(user32, hwnd: int, old_proc: int) -> None:
        set_window_long_ptr = getattr(user32, "SetWindowLongPtrW", None)
        if set_window_long_ptr is not None:
            set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
            set_window_long_ptr.restype = LONG_PTR
            set_window_long_ptr(hwnd, GWL_WNDPROC, old_proc)
            return
        set_window_long = user32.SetWindowLongW
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        set_window_long.restype = ctypes.c_long
        set_window_long(hwnd, GWL_WNDPROC, old_proc)


    def _allow_drop_messages(user32, hwnd: int) -> None:
        change_filter = getattr(user32, "ChangeWindowMessageFilterEx", None)
        if change_filter is None:
            return
        change_filter.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.DWORD, ctypes.c_void_p]
        change_filter.restype = wintypes.BOOL
        for message in (WM_DROPFILES, WM_COPYDATA, WM_COPYGLOBALDATA):
            try:
                change_filter(hwnd, message, MSGFLT_ALLOW, None)
            except Exception:
                pass


    class WindowsFileDropTarget:
        def __init__(self, window: tk.Misc, callback) -> None:
            self.window = window
            self.callback = callback
            self._installed: dict[int, tuple[int, object]] = {}

        def install(self) -> None:
            if not hasattr(ctypes, "WINFUNCTYPE"):
                return
            self.window.update_idletasks()
            user32 = ctypes.windll.user32
            user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.DefWindowProcW.restype = LRESULT
            user32.CallWindowProcW.argtypes = [LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallWindowProcW.restype = LRESULT
            shell32 = ctypes.windll.shell32
            shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
            shell32.DragAcceptFiles.restype = None
            WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            def _install_widget(widget: tk.Misc) -> None:
                try:
                    hwnd = int(widget.winfo_id())
                except Exception:
                    return
                if hwnd in self._installed:
                    return

                @WNDPROC
                def _wnd_proc(hwnd_value, msg, wparam, lparam):
                    if msg == WM_DROPFILES:
                        dropped = _iter_drop_files(wparam)
                        self.window.after(0, lambda files=dropped: self.callback(files))
                        return 0
                    old_proc, _ = self._installed.get(hwnd_value, (0, None))
                    if not old_proc:
                        return user32.DefWindowProcW(hwnd_value, msg, wparam, lparam)
                    return user32.CallWindowProcW(old_proc, hwnd_value, msg, wparam, lparam)

                old_proc = _set_window_proc(user32, hwnd, _wnd_proc)
                self._installed[hwnd] = (old_proc, _wnd_proc)
                shell32.DragAcceptFiles(hwnd, True)
                _allow_drop_messages(user32, hwnd)
                for child in widget.winfo_children():
                    _install_widget(child)

            _install_widget(self.window)

        def uninstall(self) -> None:
            if not self._installed:
                return
            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32
            shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
            shell32.DragAcceptFiles.restype = None
            for hwnd, (old_proc, _new_proc) in list(self._installed.items()):
                shell32.DragAcceptFiles(hwnd, False)
                if old_proc:
                    _restore_window_proc(user32, hwnd, old_proc)
            self._installed.clear()

else:
    # 非 Windows 平台占位实现，保持旧 import 不报错；真正的拖拽走 dnd_support.py
    class WindowsFileDropTarget:  # type: ignore[no-redef]
        def __init__(self, window: tk.Misc, callback) -> None:
            self.window = window
            self.callback = callback

        def install(self) -> None:
            return None

        def uninstall(self) -> None:
            return None
