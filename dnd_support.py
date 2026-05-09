"""跨平台文件拖拽分派。

Windows: 复用 drag_drop.WindowsFileDropTarget 的原生 ctypes 实现，行为/性能不变。
macOS / Linux: 使用 tkinterdnd2，要求根窗口由 TkinterDnD.Tk() 创建（见 app.py）。

对外只暴露：
- create_root() —— 按平台返回正确的 Tk 根实例
- install_drop_target(root, callback) —— 在主窗口安装拖拽接收器
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Callable, Iterable

from paths import IS_WIN


def create_root() -> tk.Tk:
    """按平台创建根窗口。"""
    if not IS_WIN:
        try:
            from tkinterdnd2 import TkinterDnD

            return TkinterDnD.Tk()
        except Exception as exc:
            # 让用户能在 stderr 里看到原因，避免拖拽失效却找不到线索
            print(f"[dnd_support] tkinterdnd2 unavailable, drag-drop disabled: {exc}", file=sys.stderr)
    return tk.Tk()


def _parse_tkdnd_data(widget: tk.Misc, data: str) -> list[Path]:
    """tkinterdnd2 的 event.data 是 Tcl 列表字符串，含空格的路径用 {} 包围。

    用 widget 自身 Tcl 解释器的 splitlist，比手写解析稳。
    """
    try:
        parts = widget.tk.splitlist(data)
    except tk.TclError:
        return []
    return [Path(p) for p in parts]


class _NoopDropTarget:
    """tkinterdnd2 不可用时的占位实现，保证调用方不报错。"""

    def install(self) -> None:
        return None

    def uninstall(self) -> None:
        return None


class _Tkdnd2DropTarget:
    """基于 tkinterdnd2 的跨平台拖拽接收器。"""

    def __init__(self, window: tk.Misc, callback: Callable[[Iterable[Path]], None]) -> None:
        self.window = window
        self.callback = callback
        self._installed = False

    def install(self) -> None:
        try:
            from tkinterdnd2 import DND_FILES
        except ImportError:
            return
        try:
            self.window.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.window.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
            self._installed = True
        except (AttributeError, tk.TclError):
            self._installed = False

    def uninstall(self) -> None:
        if not self._installed:
            return
        try:
            self.window.drop_target_unregister()  # type: ignore[attr-defined]
        except (AttributeError, tk.TclError):
            pass
        self._installed = False

    def _on_drop(self, event) -> None:
        paths = _parse_tkdnd_data(self.window, str(event.data))
        if paths:
            self.window.after(0, lambda p=paths: self.callback(p))


def install_drop_target(root: tk.Misc, callback: Callable[[Iterable[Path]], None]):
    """根据平台返回已就绪的拖拽接收器（已调用 install）。"""
    if IS_WIN:
        from drag_drop import WindowsFileDropTarget

        target = WindowsFileDropTarget(root, callback)
    else:
        target = _Tkdnd2DropTarget(root, callback)

    try:
        target.install()
    except Exception:
        return _NoopDropTarget()
    return target
