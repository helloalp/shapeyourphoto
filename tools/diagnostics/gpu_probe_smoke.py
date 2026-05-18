from __future__ import annotations

import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import gpu_accel  # noqa: E402


def main() -> None:
    gpu_accel._CACHED_BACKEND = None
    gpu_accel._find_native_backend = lambda: None
    gpu_accel._detect_gpu_hardware = lambda *, timeout_seconds: (
        time.sleep(max(0.0, min(timeout_seconds, 0.12))) or ("Mock GPU", "1.0")
    )

    started = time.monotonic()
    status = gpu_accel.detect_gpu_backend(force_refresh=True, timeout_seconds=0.20)
    elapsed = time.monotonic() - started

    assert elapsed < 0.45, f"GPU probe exceeded shared budget: {elapsed:.3f}s"
    assert status.hardware_detected
    assert not status.available
    assert status.native_backend_present is False
    assert "CPU" in status.reason or "fallback" in status.reason.lower()
    print(f"gpu probe smoke passed in {elapsed:.3f}s")


if __name__ == "__main__":
    main()
