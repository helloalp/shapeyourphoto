from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from app_settings import (
    CONSOLE_TIME_12H,
    CONSOLE_TIME_24H,
    CONSOLE_TIME_24H_TZ,
    CONSOLE_TIME_ELAPSED,
    LOG_LANGUAGE_BILINGUAL,
    LOG_LANGUAGE_FOLLOW_UI,
    normalize_console_time_mode,
    normalize_log_language_mode,
)
from log_manager import append_log_line


@dataclass
class AppConsole:
    lines: list[str] = field(default_factory=list)
    time_mode: str = CONSOLE_TIME_24H
    started_at: float = field(default_factory=time.monotonic)
    log_level: str = "detailed"
    log_language_mode: str = LOG_LANGUAGE_FOLLOW_UI

    def set_time_mode(self, mode: str) -> None:
        self.time_mode = normalize_console_time_mode(mode)

    def set_log_language_mode(self, mode: str) -> None:
        self.log_language_mode = normalize_log_language_mode(mode)

    def log(self, message: str) -> None:
        timestamp = self._timestamp()
        if self.log_language_mode == LOG_LANGUAGE_BILINGUAL and " | " not in message:
            message = f"{message} | log-language=bilingual"
        line = f"[{timestamp}] {message}"
        self.lines.append(line)
        self.lines = self.lines[-400:]
        try:
            append_log_line(line)
        except Exception:
            pass

    def dump(self) -> str:
        return "\n".join(self.lines) if self.lines else "控制台暂无输出。"

    def _timestamp(self) -> str:
        mode = normalize_console_time_mode(self.time_mode)
        if mode == CONSOLE_TIME_12H:
            return datetime.now().strftime("%I:%M:%S %p")
        if mode == CONSOLE_TIME_24H_TZ:
            now = datetime.now().astimezone()
            offset = now.strftime("%z")
            return f"{now.strftime('%H:%M:%S')} UTC{offset[:3]}:{offset[3:]}"
        if mode == CONSOLE_TIME_ELAPSED:
            seconds = max(0, int(time.monotonic() - self.started_at))
            minutes, sec = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"T+{hours:02d}:{minutes:02d}:{sec:02d}"
        return datetime.now().strftime("%H:%M:%S")
