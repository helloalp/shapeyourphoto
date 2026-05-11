from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec

from app_settings import GPU_ACCELERATION_AUTO, GPU_ACCELERATION_OFF, GPU_ACCELERATION_ON


@dataclass(frozen=True)
class GPUBackendStatus:
    requested_mode: str
    backend_name: str = "未检测到"
    available: bool = False
    active: bool = False
    reason: str = "未启用 GPU，加速回退 CPU。"


_CACHED_BACKEND: GPUBackendStatus | None = None


def detect_gpu_backend() -> GPUBackendStatus:
    global _CACHED_BACKEND
    if _CACHED_BACKEND is not None:
        return _CACHED_BACKEND

    checks = (_detect_cupy, _detect_opencv_cuda, _detect_torch_cuda)
    reasons: list[str] = []
    for check in checks:
        status = check()
        if status.available:
            _CACHED_BACKEND = status
            return status
        if status.reason:
            reasons.append(status.reason)

    reason = "未检测到可用 GPU 后端，可选依赖 CuPy / OpenCV-CUDA / torch CUDA 均不可用或没有 CUDA 设备。"
    if reasons:
        reason = "; ".join(dict.fromkeys(reasons))
    _CACHED_BACKEND = GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason=reason)
    return _CACHED_BACKEND


def resolve_gpu_status(mode: str) -> GPUBackendStatus:
    normalized = mode if mode in {GPU_ACCELERATION_OFF, GPU_ACCELERATION_AUTO, GPU_ACCELERATION_ON} else GPU_ACCELERATION_OFF
    if normalized == GPU_ACCELERATION_OFF:
        backend = detect_gpu_backend()
        reason = "GPU 加速已关闭，当前使用 CPU 分析。"
        if backend.available:
            reason = f"检测到 {backend.backend_name}，但 GPU 加速已关闭。"
        return GPUBackendStatus(
            requested_mode=normalized,
            backend_name=backend.backend_name,
            available=backend.available,
            active=False,
            reason=reason,
        )

    backend = detect_gpu_backend()
    if not backend.available:
        mode_label = "开启" if normalized == GPU_ACCELERATION_ON else "自动"
        return GPUBackendStatus(
            requested_mode=normalized,
            backend_name="未检测到",
            available=False,
            active=False,
            reason=f"GPU 加速设置为{mode_label}，但未检测到可用后端，已自动回退 CPU。",
        )

    return GPUBackendStatus(
        requested_mode=normalized,
        backend_name=backend.backend_name,
        available=True,
        active=False,
        reason=f"检测到 {backend.backend_name}；当前版本仍使用 CPU 稳定路径，GPU 数值阶段接入点已预留。",
    )


def gpu_console_label(status: GPUBackendStatus) -> str:
    if status.active:
        return f"GPU enabled ({status.backend_name})"
    if status.available and status.requested_mode == GPU_ACCELERATION_OFF:
        return f"GPU available but disabled ({status.backend_name})"
    if status.available:
        return f"GPU available, CPU fallback ({status.backend_name})"
    return "CPU only"


def _detect_cupy() -> GPUBackendStatus:
    if find_spec("cupy") is None:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="CuPy 未安装")
    try:
        import cupy as cp  # type: ignore

        count = int(cp.cuda.runtime.getDeviceCount())
    except Exception as exc:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason=f"CuPy 不可用：{exc}")
    if count <= 0:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="CuPy 未检测到 CUDA 设备")
    return GPUBackendStatus(
        requested_mode=GPU_ACCELERATION_AUTO,
        backend_name=f"CuPy CUDA ({count} device{'s' if count != 1 else ''})",
        available=True,
        reason="CuPy CUDA 可用",
    )


def _detect_opencv_cuda() -> GPUBackendStatus:
    if find_spec("cv2") is None:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="OpenCV 未安装")
    try:
        import cv2  # type: ignore

        cuda = getattr(cv2, "cuda", None)
        count = int(cuda.getCudaEnabledDeviceCount()) if cuda is not None else 0
    except Exception as exc:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason=f"OpenCV-CUDA 不可用：{exc}")
    if count <= 0:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="OpenCV 未检测到 CUDA 设备")
    return GPUBackendStatus(
        requested_mode=GPU_ACCELERATION_AUTO,
        backend_name=f"OpenCV CUDA ({count} device{'s' if count != 1 else ''})",
        available=True,
        reason="OpenCV CUDA 可用",
    )


def _detect_torch_cuda() -> GPUBackendStatus:
    if find_spec("torch") is None:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="torch 未安装")
    try:
        import torch  # type: ignore

        available = bool(torch.cuda.is_available())
        count = int(torch.cuda.device_count()) if available else 0
    except Exception as exc:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason=f"torch CUDA 不可用：{exc}")
    if count <= 0:
        return GPUBackendStatus(requested_mode=GPU_ACCELERATION_AUTO, reason="torch 未检测到 CUDA 设备")
    return GPUBackendStatus(
        requested_mode=GPU_ACCELERATION_AUTO,
        backend_name=f"torch CUDA ({count} device{'s' if count != 1 else ''})",
        available=True,
        reason="torch CUDA 可用",
    )
