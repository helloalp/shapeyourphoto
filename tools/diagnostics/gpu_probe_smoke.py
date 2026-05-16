from __future__ import annotations

import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import gpu_accel  # noqa: E402
from app_settings import GPU_ACCELERATION_AUTO  # noqa: E402


def _slow_unavailable_probe(*, timeout_seconds: float) -> tuple[gpu_accel.GPUBackendStatus, bool]:
    time.sleep(max(0.0, min(timeout_seconds, 0.12)))
    return (
        gpu_accel.GPUBackendStatus(
            requested_mode=GPU_ACCELERATION_AUTO,
            reason=f"probe budget {timeout_seconds:.3f}s exhausted",
        ),
        True,
    )


def main() -> None:
    gpu_accel._CACHED_BACKEND = None
    gpu_accel._detect_gpu_hardware = lambda *, timeout_seconds: ("Mock GPU", "1.0")
    gpu_accel._detect_cupy = _slow_unavailable_probe
    gpu_accel._detect_opencv_cuda = _slow_unavailable_probe
    gpu_accel._detect_torch_cuda = _slow_unavailable_probe

    started = time.monotonic()
    status = gpu_accel.detect_gpu_backend(force_refresh=True, timeout_seconds=0.20)
    elapsed = time.monotonic() - started

    assert elapsed < 0.45, f"GPU probe exceeded shared budget: {elapsed:.3f}s"
    assert status.hardware_detected
    assert not status.available
    assert status.detection_timed_out
    assert "CPU" in status.reason
    print(f"gpu probe smoke passed in {elapsed:.3f}s")


if __name__ == "__main__":
    main()
