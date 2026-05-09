from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from app_settings import CONSOLE_TIME_12H, CONSOLE_TIME_24H, CONSOLE_TIME_ELAPSED, normalize_console_time_mode


@dataclass
class AppConsole:
    lines: list[str] = field(default_factory=list)
    time_mode: str = CONSOLE_TIME_24H
    started_at: float = field(default_factory=time.monotonic)

    def set_time_mode(self, mode: str) -> None:
        self.time_mode = normalize_console_time_mode(mode)

    def log(self, message: str) -> None:
        timestamp = self._timestamp()
        self.lines.append(f"[{timestamp}] {message}")
        self.lines = self.lines[-400:]

    def dump(self) -> str:
        return "\n".join(self.lines) if self.lines else "控制台暂无输出。"

    def _timestamp(self) -> str:
        mode = normalize_console_time_mode(self.time_mode)
        if mode == CONSOLE_TIME_12H:
            return datetime.now().strftime("%I:%M:%S %p")
        if mode == CONSOLE_TIME_ELAPSED:
            seconds = max(0, int(time.monotonic() - self.started_at))
            minutes, sec = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"T+{hours:02d}:{minutes:02d}:{sec:02d}"
        return datetime.now().strftime("%H:%M:%S")
