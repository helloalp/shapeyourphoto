from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app_settings import GPU_ACCELERATION_AUTO, GPU_ACCELERATION_OFF, GPU_ACCELERATION_ON
from paths import resource_path


NATIVE_BACKEND_VERSION = "1.2.6-native.1"
NATIVE_BACKEND_EXE = "shapeyourphoto_gpu_core.exe" if sys.platform == "win32" else "shapeyourphoto_gpu_core"


@dataclass(frozen=True)
class GPUDiagnostic:
    hardware_detected: bool = False
    hardware_name: str = "No GPU hardware detected"
    driver_version: str = ""
    native_backend_present: bool = False
    native_backend_version: str = ""
    selected_backend: str = "CPU fallback"
    acceleration_available: bool = False
    acceleration_active: bool = False
    last_accelerated_task: str = ""
    fallback_reason: str = ""
    self_test_result: dict[str, Any] = field(default_factory=dict)
    benchmark_result: dict[str, Any] = field(default_factory=dict)
    packaged_components_found: tuple[str, ...] = field(default_factory=tuple)
    packaged_components_missing: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> str:
        return json.dumps(
            {
                "hardware_detected": self.hardware_detected,
                "hardware_name": self.hardware_name,
                "driver_version": self.driver_version,
                "native_backend_present": self.native_backend_present,
                "native_backend_version": self.native_backend_version,
                "selected_backend": self.selected_backend,
                "acceleration_available": self.acceleration_available,
                "acceleration_active": self.acceleration_active,
                "last_accelerated_task": self.last_accelerated_task,
                "fallback_reason": self.fallback_reason,
                "self_test_result": self.self_test_result,
                "benchmark_result": self.benchmark_result,
                "packaged_components_found": list(self.packaged_components_found),
                "packaged_components_missing": list(self.packaged_components_missing),
            },
            ensure_ascii=False,
            indent=2,
        )


@dataclass(frozen=True)
class GPUBackendStatus:
    requested_mode: str
    backend_name: str = "Native GPU backend missing"
    available: bool = False
    active: bool = False
    reason: str = "GPU acceleration is not active; CPU fallback is in use."
    hardware_detected: bool = False
    hardware_name: str = "No GPU hardware detected"
    driver_version: str = ""
    backend_reasons: tuple[str, ...] = field(default_factory=tuple)
    detection_timed_out: bool = False
    native_backend_present: bool = False
    native_backend_path: str = ""
    native_backend_version: str = ""
    selected_backend: str = "CPU fallback"
    last_accelerated_task: str = ""
    self_test_result: dict[str, Any] = field(default_factory=dict)
    benchmark_result: dict[str, Any] = field(default_factory=dict)
    packaged_components_found: tuple[str, ...] = field(default_factory=tuple)
    packaged_components_missing: tuple[str, ...] = field(default_factory=tuple)

    def diagnostic(self) -> GPUDiagnostic:
        return GPUDiagnostic(
            hardware_detected=self.hardware_detected,
            hardware_name=self.hardware_name,
            driver_version=self.driver_version,
            native_backend_present=self.native_backend_present,
            native_backend_version=self.native_backend_version,
            selected_backend=self.selected_backend,
            acceleration_available=self.available,
            acceleration_active=self.active,
            last_accelerated_task=self.last_accelerated_task,
            fallback_reason="" if self.available else self.reason,
            self_test_result=self.self_test_result,
            benchmark_result=self.benchmark_result,
            packaged_components_found=self.packaged_components_found,
            packaged_components_missing=self.packaged_components_missing,
        )


@dataclass(frozen=True)
class AcceleratedLumaStats:
    accelerated: bool
    backend_name: str
    elapsed_ms: float
    stats: dict[str, float]
    fallback_reason: str = ""
    timings: dict[str, float] = field(default_factory=dict)


_CACHED_BACKEND: GPUBackendStatus | None = None
_CACHE_LOCK = threading.Lock()
_LAST_ACCELERATED_TASK = ""
_SERVER_LOCK = threading.Lock()
_SERVER: _NativeGpuServer | None = None


class _NativeGpuServer:
    def __init__(self, backend_path: str) -> None:
        self.backend_path = backend_path
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    def request_luma_stats(self, *, input_path: Path, width: int, height: int, timeout_seconds: float = 6.0) -> dict[str, Any]:
        with self._lock:
            process = self._ensure_process()
            if process.stdin is None or process.stdout is None:
                self.close()
                raise RuntimeError("native GPU server pipes are not available")
            request = {
                "cmd": "luma-stats",
                "input": str(input_path),
                "width": int(width),
                "height": int(height),
            }
            try:
                process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                process.stdin.flush()
            except Exception as exc:
                self.close()
                raise RuntimeError(f"native GPU server write failed: {exc}") from exc

            response_queue: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

            def _reader() -> None:
                try:
                    assert process.stdout is not None
                    response_queue.put(process.stdout.readline())
                except BaseException as exc:
                    response_queue.put(exc)

            reader = threading.Thread(target=_reader, daemon=True)
            reader.start()
            try:
                line_or_error = response_queue.get(timeout=timeout_seconds)
            except queue.Empty as exc:
                self.close()
                raise TimeoutError("native GPU server response timed out") from exc
            if isinstance(line_or_error, BaseException):
                self.close()
                raise RuntimeError(f"native GPU server read failed: {line_or_error}") from line_or_error
            line = str(line_or_error).strip()
            if not line:
                self.close()
                raise RuntimeError("native GPU server stopped without a response")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                self.close()
                raise RuntimeError(f"invalid native GPU server JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise RuntimeError("native GPU server returned non-object JSON")
            return payload

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.stdin is not None and process.poll() is None:
                process.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
                process.stdin.flush()
        except Exception:
            pass
        try:
            process.terminate()
        except Exception:
            pass
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._process = subprocess.Popen(
            [self.backend_path, "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_subprocess_creation_flags(),
        )
        return self._process


def detect_gpu_backend(*, force_refresh: bool = False, timeout_seconds: float = 3.0) -> GPUBackendStatus:
    global _CACHED_BACKEND
    with _CACHE_LOCK:
        if _CACHED_BACKEND is not None and not force_refresh:
            return _CACHED_BACKEND

    started_at = time.perf_counter()
    backend_path = _find_native_backend()
    found_components, missing_components = _packaged_components(backend_path)
    hardware_name, driver_version = _detect_gpu_hardware(timeout_seconds=min(0.8, timeout_seconds))
    reasons: list[str] = []
    timed_out = False
    capabilities: dict[str, Any] = {}
    self_test: dict[str, Any] = {}

    if backend_path is None:
        reasons.append("The installed package does not include the native GPU component.")
    else:
        try:
            capabilities = _run_backend_json([str(backend_path), "capabilities"], timeout_seconds=max(0.8, timeout_seconds))
        except subprocess.TimeoutExpired:
            timed_out = True
            reasons.append("Native GPU backend capability probe timed out.")
        except Exception as exc:
            reasons.append(f"Native GPU backend capability probe failed: {exc}")

    if capabilities.get("hardware_name"):
        hardware_name = str(capabilities.get("hardware_name") or hardware_name)
    if capabilities.get("driver_version"):
        driver_version = str(capabilities.get("driver_version") or driver_version)

    native_present = backend_path is not None
    backend_version = str(capabilities.get("version") or (NATIVE_BACKEND_VERSION if native_present else ""))
    selected_backend = str(capabilities.get("backend") or "CPU fallback")
    acceleration_available = bool(capabilities.get("acceleration_available"))

    if native_present and acceleration_available:
        try:
            self_test = _run_backend_json([str(backend_path), "self-test"], timeout_seconds=max(1.2, timeout_seconds))
            acceleration_available = bool(self_test.get("ok")) and bool(self_test.get("accelerated"))
            if not acceleration_available:
                reasons.append(str(self_test.get("fallback_reason") or "Native GPU self-test did not use GPU acceleration."))
        except subprocess.TimeoutExpired:
            timed_out = True
            acceleration_available = False
            reasons.append("Native GPU self-test timed out.")
        except Exception as exc:
            acceleration_available = False
            reasons.append(f"Native GPU self-test failed: {exc}")

    if acceleration_available:
        reason = "Native GPU backend is available and will be selected automatically for supported image tasks."
        backend_name = selected_backend
    elif native_present:
        reason = "Native GPU backend is present but could not start acceleration; ShapeYourPhoto will use CPU fallback automatically."
        backend_name = selected_backend if selected_backend != "CPU fallback" else "Native GPU backend"
    else:
        reason = "This package is missing the bundled GPU acceleration component; ShapeYourPhoto will use CPU fallback automatically."
        backend_name = "Native GPU backend missing"

    if reasons:
        reason = f"{reason} {' '.join(dict.fromkeys(reasons[:4]))}"

    status = GPUBackendStatus(
        requested_mode=GPU_ACCELERATION_AUTO,
        backend_name=backend_name,
        available=acceleration_available,
        active=False,
        reason=reason,
        hardware_detected=bool(hardware_name) or bool(capabilities.get("hardware_detected")),
        hardware_name=hardware_name or str(capabilities.get("hardware_name") or "No GPU hardware detected"),
        driver_version=driver_version,
        backend_reasons=tuple(dict.fromkeys(reasons)),
        detection_timed_out=timed_out,
        native_backend_present=native_present,
        native_backend_path=str(backend_path or ""),
        native_backend_version=backend_version,
        selected_backend=selected_backend,
        last_accelerated_task=_LAST_ACCELERATED_TASK,
        self_test_result=self_test,
        benchmark_result={
            "probe_elapsed_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
        },
        packaged_components_found=found_components,
        packaged_components_missing=missing_components,
    )
    with _CACHE_LOCK:
        _CACHED_BACKEND = status
    return status


def resolve_gpu_status(mode: str, *, allow_probe: bool = True) -> GPUBackendStatus:
    normalized = mode if mode in {GPU_ACCELERATION_OFF, GPU_ACCELERATION_AUTO, GPU_ACCELERATION_ON} else GPU_ACCELERATION_OFF
    with _CACHE_LOCK:
        cached = _CACHED_BACKEND
    if cached is None and not allow_probe:
        return GPUBackendStatus(
            requested_mode=normalized,
            reason="GPU status has not been detected yet; current tasks use CPU fallback.",
        )
    backend = cached or detect_gpu_backend()
    if normalized == GPU_ACCELERATION_OFF:
        return _copy_status(
            backend,
            requested_mode=normalized,
            active=False,
            reason="GPU acceleration is disabled in settings; CPU fallback is in use.",
        )
    if not backend.available:
        return _copy_status(backend, requested_mode=normalized, active=False)
    return _copy_status(
        backend,
        requested_mode=normalized,
        active=True,
        reason="Native GPU backend is enabled for supported tasks.",
    )


def gpu_console_label(status: GPUBackendStatus) -> str:
    if status.active:
        return f"GPU enabled ({status.backend_name})"
    if status.available and status.requested_mode == GPU_ACCELERATION_OFF:
        return f"GPU available but disabled ({status.backend_name})"
    if status.available:
        return f"GPU available ({status.backend_name})"
    if status.native_backend_present:
        return "native GPU backend present, CPU fallback"
    if status.hardware_detected:
        return f"GPU hardware detected, packaged backend missing ({status.hardware_name})"
    return "CPU fallback"


def export_gpu_diagnostics_json(force_refresh: bool = False) -> str:
    return detect_gpu_backend(force_refresh=force_refresh).diagnostic().to_json()


def accelerated_luma_stats(image: Image.Image, mode: str = GPU_ACCELERATION_AUTO) -> AcceleratedLumaStats | None:
    global _CACHED_BACKEND, _LAST_ACCELERATED_TASK
    call_started_at = time.perf_counter()
    status = resolve_gpu_status(mode)
    if mode == GPU_ACCELERATION_OFF or not status.available or not status.native_backend_path:
        return None
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width <= 0 or height <= 0:
        return None
    if width * height < 1_500_000:
        return None

    raw_bytes = rgb.tobytes()
    with tempfile.NamedTemporaryFile(prefix="syp-gpu-", suffix=".rgb", delete=False) as temp:
        temp.write(raw_bytes)
        temp_path = Path(temp.name)
    started_at = time.perf_counter()
    try:
        payload = _get_native_server(status.native_backend_path).request_luma_stats(
            input_path=temp_path,
            width=width,
            height=height,
            timeout_seconds=6.0,
        )
    except Exception as exc:
        return AcceleratedLumaStats(
            accelerated=False,
            backend_name=status.backend_name,
            elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
            stats={},
            fallback_reason=str(exc),
            timings={},
        )
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    elapsed_ms = float(payload.get("elapsed_ms") or ((time.perf_counter() - started_at) * 1000.0))
    accelerated = bool(payload.get("accelerated"))
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    timings_payload = payload.get("timings") if isinstance(payload.get("timings"), dict) else {}
    timings = {str(key): float(value) for key, value in timings_payload.items() if _is_number(value)}
    timings["python_total_ms"] = (time.perf_counter() - call_started_at) * 1000.0
    if accelerated and stats:
        _LAST_ACCELERATED_TASK = "analysis.luma_stats"
        with _CACHE_LOCK:
            if _CACHED_BACKEND is not None:
                _CACHED_BACKEND = _copy_status(
                    _CACHED_BACKEND,
                    active=True,
                    last_accelerated_task=_LAST_ACCELERATED_TASK,
                    benchmark_result={
                        **_CACHED_BACKEND.benchmark_result,
                        "last_task_elapsed_ms": round(elapsed_ms, 3),
                    },
                )
    return AcceleratedLumaStats(
        accelerated=accelerated,
        backend_name=str(payload.get("backend") or status.backend_name),
        elapsed_ms=elapsed_ms,
        stats={str(key): float(value) for key, value in stats.items() if _is_number(value)},
        fallback_reason=str(payload.get("fallback_reason") or ""),
        timings=timings,
    )


def shutdown_native_gpu_server() -> None:
    global _SERVER
    with _SERVER_LOCK:
        server = _SERVER
        _SERVER = None
    if server is not None:
        server.close()


def _get_native_server(backend_path: str) -> _NativeGpuServer:
    global _SERVER
    with _SERVER_LOCK:
        if _SERVER is None or _SERVER.backend_path != backend_path:
            if _SERVER is not None:
                _SERVER.close()
            _SERVER = _NativeGpuServer(backend_path)
        return _SERVER


def _copy_status(status: GPUBackendStatus, **updates: Any) -> GPUBackendStatus:
    payload = {
        "requested_mode": status.requested_mode,
        "backend_name": status.backend_name,
        "available": status.available,
        "active": status.active,
        "reason": status.reason,
        "hardware_detected": status.hardware_detected,
        "hardware_name": status.hardware_name,
        "driver_version": status.driver_version,
        "backend_reasons": status.backend_reasons,
        "detection_timed_out": status.detection_timed_out,
        "native_backend_present": status.native_backend_present,
        "native_backend_path": status.native_backend_path,
        "native_backend_version": status.native_backend_version,
        "selected_backend": status.selected_backend,
        "last_accelerated_task": status.last_accelerated_task,
        "self_test_result": status.self_test_result,
        "benchmark_result": status.benchmark_result,
        "packaged_components_found": status.packaged_components_found,
        "packaged_components_missing": status.packaged_components_missing,
    }
    payload.update(updates)
    return GPUBackendStatus(**payload)


def _find_native_backend() -> Path | None:
    env_path = os.environ.get("SHAPEYOURPHOTO_GPU_CORE")
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(
        [
            resource_path(Path("gpu") / NATIVE_BACKEND_EXE),
            resource_path(Path("native") / "gpu-core" / "target" / "release" / NATIVE_BACKEND_EXE),
            resource_path(Path("native") / "gpu-core" / "target" / "debug" / NATIVE_BACKEND_EXE),
            Path(__file__).resolve().parent.parent / "native" / "gpu-core" / "target" / "release" / NATIVE_BACKEND_EXE,
            Path(__file__).resolve().parent.parent / "native" / "gpu-core" / "target" / "debug" / NATIVE_BACKEND_EXE,
        ]
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _packaged_components(backend_path: Path | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    found: list[str] = []
    missing: list[str] = []
    if backend_path is not None:
        found.append(str(backend_path))
    else:
        missing.append(f"gpu/{NATIVE_BACKEND_EXE}")
    return tuple(found), tuple(missing)


def _run_backend_json(args: list[str], *, timeout_seconds: float) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        creationflags=_subprocess_creation_flags(),
        check=False,
    )
    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        message = (completed.stderr or output or f"exit {completed.returncode}").strip()
        raise RuntimeError(message)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid native GPU JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("native GPU backend returned non-object JSON")
    return payload


def _detect_gpu_hardware(*, timeout_seconds: float) -> tuple[str, str]:
    status = _query_nvidia_smi(timeout_seconds=timeout_seconds)
    if status[0]:
        return status
    return _query_windows_video_controller(timeout_seconds=timeout_seconds)


def _query_nvidia_smi(*, timeout_seconds: float) -> tuple[str, str]:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            creationflags=_subprocess_creation_flags(),
            check=False,
        )
    except Exception:
        return "", ""
    if completed.returncode != 0:
        return "", ""
    line = next((item.strip() for item in completed.stdout.splitlines() if item.strip()), "")
    if not line:
        return "", ""
    parts = [part.strip() for part in line.split(",", 1)]
    return parts[0], parts[1] if len(parts) > 1 else ""


def _query_windows_video_controller(*, timeout_seconds: float) -> tuple[str, str]:
    if not sys.platform.startswith("win"):
        return "", ""
    try:
        completed = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "Name,DriverVersion", "/format:csv"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            creationflags=_subprocess_creation_flags(),
            check=False,
        )
    except Exception:
        return "", ""
    if completed.returncode != 0:
        return "", ""
    for line in completed.stdout.splitlines():
        lowered = line.lower()
        if not any(token in lowered for token in ("nvidia", "amd", "radeon", "intel")):
            continue
        parts = [part.strip() for part in line.split(",") if part.strip()]
        if len(parts) >= 3:
            return parts[-1], parts[-2]
        if parts:
            return parts[-1], ""
    return "", ""


def _subprocess_creation_flags() -> int:
    if not sys.platform.startswith("win"):
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float, np.floating)) and not isinstance(value, bool)
