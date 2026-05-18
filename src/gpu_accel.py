from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from importlib.util import find_spec

from app_settings import GPU_ACCELERATION_AUTO, GPU_ACCELERATION_OFF, GPU_ACCELERATION_ON


@dataclass(frozen=True)
class GPUBackendStatus:
    requested_mode: str
    backend_name: str = "ShapeYourPhoto GPU 后端未准备"
    available: bool = False
    active: bool = False
    reason: str = "未启用 GPU，加速回退 CPU。"
    hardware_detected: bool = False
    hardware_name: str = "未检测到 GPU 硬件"
    driver_version: str = ""
    backend_reasons: tuple[str, ...] = field(default_factory=tuple)
    detection_timed_out: bool = False


_CACHED_BACKEND: GPUBackendStatus | None = None
_CACHE_LOCK = threading.Lock()


def detect_gpu_backend(*, force_refresh: bool = False, timeout_seconds: float = 2.5) -> GPUBackendStatus:
    global _CACHED_BACKEND
    with _CACHE_LOCK:
        if _CACHED_BACKEND is not None and not force_refresh:
            return _CACHED_BACKEND

    total_budget = max(0.8, float(timeout_seconds or 0.0))
    deadline = time.monotonic() + total_budget
    hardware_name, driver_version = _detect_gpu_hardware(timeout_seconds=min(0.8, total_budget))
    remaining_budget = max(0.0, deadline - time.monotonic())
    backend_status, backend_reasons, timed_out = _detect_runtime_backend(timeout_seconds=remaining_budget)
    hardware_detected = bool(hardware_name)

    if backend_status is not None:
        status = GPUBackendStatus(
            requested_mode=GPU_ACCELERATION_AUTO,
            backend_name=backend_status.backend_name,
            available=True,
            active=False,
            reason=f"检测到 {backend_status.backend_name}；当前版本仍使用 CPU 稳定路径，GPU 数值阶段接入点已预留。",
            hardware_detected=hardware_detected,
            hardware_name=hardware_name or backend_status.hardware_name,
            driver_version=driver_version,
            backend_reasons=tuple(backend_reasons),
            detection_timed_out=timed_out,
        )
    else:
        if hardware_detected:
            reason = f"已检测到 {hardware_name}，显卡和驱动可用；当前 ShapeYourPhoto 运行环境还没有准备好图像处理加速组件，已继续使用 CPU。"
        else:
            reason = "当前 ShapeYourPhoto 没有可用的图像处理加速组件，已继续使用 CPU。"
        if backend_reasons:
            reason += " " + "；".join(dict.fromkeys(backend_reasons[:4]))
        if timed_out:
            reason += " 部分后端检测超时，已跳过以避免卡住界面。"
        status = GPUBackendStatus(
            requested_mode=GPU_ACCELERATION_AUTO,
            backend_name="ShapeYourPhoto GPU 后端未准备",
            available=False,
            active=False,
            reason=reason,
            hardware_detected=hardware_detected,
            hardware_name=hardware_name or "未检测到 GPU 硬件",
            driver_version=driver_version,
            backend_reasons=tuple(backend_reasons),
            detection_timed_out=timed_out,
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
            active=False,
            reason="GPU 状态尚未完成检测，当前任务使用 CPU。",
        )
    backend = cached or detect_gpu_backend()
    if normalized == GPU_ACCELERATION_OFF:
        reason = "GPU 加速已关闭，当前使用 CPU 分析。"
        if backend.hardware_detected and backend.available:
            reason = f"检测到 {backend.hardware_name} 和 {backend.backend_name}，但 GPU 加速已关闭。"
        elif backend.hardware_detected:
            reason = f"检测到 {backend.hardware_name}，但 GPU 加速已关闭；当前使用 CPU。"
        return _copy_status(backend, requested_mode=normalized, active=False, reason=reason)

    if not backend.available:
        mode_label = "开启" if normalized == GPU_ACCELERATION_ON else "自动"
        hardware_text = f"已检测到 {backend.hardware_name}；" if backend.hardware_detected else ""
        return _copy_status(
            backend,
            requested_mode=normalized,
            active=False,
            reason=f"GPU 加速设置为{mode_label}，{hardware_text}没有可用运行后端，已自动使用 CPU。",
        )

    return _copy_status(
        backend,
        requested_mode=normalized,
        active=False,
        reason=f"检测到 {backend.hardware_name} 和 {backend.backend_name}；当前任务仍使用 CPU 稳定路径。",
    )


def gpu_console_label(status: GPUBackendStatus) -> str:
    if status.active:
        return f"GPU enabled ({status.backend_name})"
    if status.available and status.requested_mode == GPU_ACCELERATION_OFF:
        return f"GPU available but disabled ({status.backend_name})"
    if status.available:
        return f"GPU available, CPU fallback ({status.backend_name})"
    if status.hardware_detected:
        return f"GPU hardware detected, CPU fallback ({status.hardware_name})"
    return "CPU only"


def _copy_status(status: GPUBackendStatus, **updates) -> GPUBackendStatus:
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
    }
    payload.update(updates)
    return GPUBackendStatus(**payload)


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
    name = parts[0]
    driver = parts[1] if len(parts) > 1 else ""
    return name, driver


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
        if "NVIDIA" not in line.upper():
            continue
        parts = [part.strip() for part in line.split(",") if part.strip()]
        if len(parts) >= 3:
            return parts[-1], parts[-2]
        if parts:
            return parts[-1], ""
    return "", ""


def _detect_runtime_backend(*, timeout_seconds: float) -> tuple[GPUBackendStatus | None, list[str], bool]:
    checks = (_detect_cupy, _detect_opencv_cuda, _detect_torch_cuda)
    reasons: list[str] = []
    timed_out = False
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    for check in checks:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            reasons.append("GPU 后端检测总耗时已达到上限")
            break
        status, did_timeout = check(timeout_seconds=min(remaining, 1.0))
        timed_out = timed_out or did_timeout
        if status.available:
            return status, reasons, timed_out
        if status.reason:
            reasons.append(status.reason)
    return None, reasons, timed_out


def _python_probe(code: str, *, timeout_seconds: float) -> tuple[str, bool, str]:
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            creationflags=_subprocess_creation_flags(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "", True, "检测超时"
    except Exception as exc:
        return "", False, str(exc)
    if completed.returncode != 0:
        return "", False, (completed.stderr or completed.stdout or f"exit {completed.returncode}").strip()
    return completed.stdout.strip(), False, ""


def _detect_cupy(*, timeout_seconds: float) -> tuple[GPUBackendStatus, bool]:
    if find_spec("cupy") is None:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="CuPy 未准备"), False
    if getattr(sys, "frozen", False):
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="CuPy 后端检测已跳过"), False
    code = (
        "import cupy as cp\n"
        "count=int(cp.cuda.runtime.getDeviceCount())\n"
        "name=''\n"
        "if count>0:\n"
        "    props=cp.cuda.runtime.getDeviceProperties(0)\n"
        "    raw=props.get('name', b'') if isinstance(props, dict) else b''\n"
        "    name=raw.decode('utf-8','replace') if isinstance(raw, bytes) else str(raw or '')\n"
        "print(f'{count}\\t{name}')\n"
    )
    output, timed_out, error = _python_probe(code, timeout_seconds=timeout_seconds)
    if timed_out:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="CuPy 检测超时"), True
    if error:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason=f"CuPy 不可用：{error}"), False
    line = output.splitlines()[-1] if output else "0"
    parts = line.split("\t", 1)
    count = _safe_int(parts[0])
    name = parts[1] if len(parts) > 1 else ""
    if count <= 0:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="CuPy 未检测到 CUDA 设备"), False
    hardware = name or f"CUDA 设备 {count} 个"
    return GPUBackendStatus(
        requested_mode=GPU_ACCELERATION_AUTO,
        backend_name=f"CuPy CUDA ({count} device{'s' if count != 1 else ''})",
        available=True,
        hardware_detected=True,
        hardware_name=hardware,
        reason="CuPy CUDA 可用",
    ), False


def _detect_opencv_cuda(*, timeout_seconds: float) -> tuple[GPUBackendStatus, bool]:
    if find_spec("cv2") is None:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="OpenCV 加速组件未准备"), False
    if getattr(sys, "frozen", False):
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="OpenCV CUDA 后端检测已跳过"), False
    code = (
        "import cv2\n"
        "cuda=getattr(cv2, 'cuda', None)\n"
        "count=int(cuda.getCudaEnabledDeviceCount()) if cuda is not None else 0\n"
        "print(count)\n"
    )
    output, timed_out, error = _python_probe(code, timeout_seconds=timeout_seconds)
    if timed_out:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="OpenCV CUDA 检测超时"), True
    if error:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason=f"OpenCV-CUDA 不可用：{error}"), False
    line = output.splitlines()[-1] if output else "0"
    count = _safe_int(line.strip())
    if count <= 0:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="OpenCV 未检测到 CUDA 设备"), False
    return GPUBackendStatus(
        requested_mode=GPU_ACCELERATION_AUTO,
        backend_name=f"OpenCV CUDA ({count} device{'s' if count != 1 else ''})",
        available=True,
        reason="OpenCV CUDA 可用",
    ), False


def _detect_torch_cuda(*, timeout_seconds: float) -> tuple[GPUBackendStatus, bool]:
    if find_spec("torch") is None:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="torch 加速组件未准备"), False
    if getattr(sys, "frozen", False):
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="torch CUDA 后端检测已跳过"), False
    code = (
        "import torch\n"
        "available=bool(torch.cuda.is_available())\n"
        "count=int(torch.cuda.device_count()) if available else 0\n"
        "name=torch.cuda.get_device_name(0) if count>0 else ''\n"
        "print(f'{count}\\t{name}')\n"
    )
    output, timed_out, error = _python_probe(code, timeout_seconds=timeout_seconds)
    if timed_out:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="torch CUDA 检测超时"), True
    if error:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason=f"torch CUDA 不可用：{error}"), False
    line = output.splitlines()[-1] if output else "0"
    parts = line.split("\t", 1)
    count = _safe_int(parts[0])
    name = parts[1] if len(parts) > 1 else ""
    if count <= 0:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="torch 未检测到 CUDA 设备"), False
    return GPUBackendStatus(
        requested_mode=GPU_ACCELERATION_AUTO,
        backend_name=f"torch CUDA ({count} device{'s' if count != 1 else ''})",
        available=True,
        hardware_detected=True,
        hardware_name=name or f"CUDA 设备 {count} 个",
        reason="torch CUDA 可用",
    ), False


def _subprocess_creation_flags() -> int:
    if not sys.platform.startswith("win"):
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _safe_int(value: str) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 0
