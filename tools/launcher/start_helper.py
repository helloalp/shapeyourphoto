from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "src"
REQUIREMENTS = ROOT / "requirements" / "runtime.txt"
LEGACY_REQUIREMENTS = ROOT / "requirements.txt"
APP_PYW = ROOT / "tools" / "entry" / "app.pyw"
APP_PY = ROOT / "tools" / "entry" / "app.py"
GPU_CORE_EXE = ROOT / "native" / "gpu-core" / "target" / "release" / (
    "shapeyourphoto_gpu_core.exe" if sys.platform == "win32" else "shapeyourphoto_gpu_core"
)

REQUIRED_IMPORTS = [
    ("Pillow", "PIL"),
    ("numpy", "numpy"),
    ("platformdirs", "platformdirs"),
    ("cryptography", "cryptography"),
]

if sys.platform != "win32" and sys.version_info < (3, 14):
    REQUIRED_IMPORTS.append(("tkinterdnd2", "tkinterdnd2"))

if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))


def stage(cn: str, en: str) -> None:
    print(f"\n== {cn} / {en} ==")


def info(cn: str, en: str) -> None:
    print(f"{cn} / {en}")


def check_imports() -> list[str]:
    missing: list[str] = []
    for package_name, module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(package_name)
    return missing


def install_dependencies() -> None:
    requirements = REQUIREMENTS if REQUIREMENTS.exists() else LEGACY_REQUIREMENTS
    if not requirements.exists():
        raise RuntimeError(f"runtime requirements not found: {REQUIREMENTS}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"], cwd=str(ROOT))
    except subprocess.CalledProcessError:
        stage("正在准备 pip", "Preparing pip")
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"], cwd=str(ROOT))
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
    subprocess.check_call(cmd, cwd=str(ROOT))


def pythonw_executable() -> str | None:
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        candidate = executable.with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
    found = shutil.which("pythonw")
    return found


def launch_app() -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    prefix = str(PACKAGE_DIR)
    env["PYTHONPATH"] = prefix if not existing else prefix + os.pathsep + existing
    if APP_PYW.exists():
        pythonw = pythonw_executable()
        if pythonw:
            subprocess.Popen([pythonw, str(APP_PYW)], cwd=str(ROOT), env=env, close_fds=True)
            return
    subprocess.Popen([sys.executable, str(APP_PY)], cwd=str(ROOT), env=env, close_fds=True)


def organize_legacy_files() -> None:
    try:
        from legacy_cleanup import quarantine_legacy_files

        report = quarantine_legacy_files(ROOT)
    except Exception as exc:
        info(
            f"旧文件整理未完成：{exc}",
            f"Legacy file organization did not finish: {exc}",
        )
        return
    if not report.moved and not report.skipped:
        info("未发现需要整理的旧版本文件。", "No legacy files need to be organized.")
        return
    if report.moved:
        info(
            f"已整理旧版本文件 {len(report.moved)} 项，清单：{report.manifest_path}",
            f"Organized {len(report.moved)} legacy item(s), report: {report.manifest_path}",
        )
    if report.skipped:
        info(
            f"保留受保护项目 {len(report.skipped)} 项。",
            f"Kept {len(report.skipped)} protected item(s).",
        )


def check_native_gpu_component() -> None:
    packaged = ROOT / "gpu" / GPU_CORE_EXE.name
    if packaged.exists() or GPU_CORE_EXE.exists() or os.environ.get("SHAPEYOURPHOTO_GPU_CORE"):
        info("Native GPU 组件已找到。", "Native GPU component found.")
        return
    info(
        "Native GPU 组件未找到；应用会自动使用 CPU 回退。发布包应包含 gpu\\shapeyourphoto_gpu_core.exe。",
        "Native GPU component was not found; the app will use CPU fallback. Release builds should include gpu\\shapeyourphoto_gpu_core.exe.",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if os.environ.get("SHAPEYOURPHOTO_START_CHECK_ONLY") == "1":
        args.check_only = True

    stage("正在检查 Python", "Checking Python")
    info(f"Python {sys.version.split()[0]}", f"Using {sys.executable}")
    if sys.version_info < (3, 10):
        raise RuntimeError(
            "ShapeYourPhoto needs Python 3.10 or newer. "
            "请安装 Python 3.10 或更新版本后重试。"
        )

    stage("正在检查依赖", "Checking dependencies")
    missing = check_imports()
    if missing:
        info("缺少运行依赖：" + ", ".join(missing), "Missing required packages: " + ", ".join(missing))
        stage("正在安装依赖", "Installing dependencies")
        install_dependencies()
        missing = check_imports()
        if missing:
            raise RuntimeError("Still missing packages after install: " + ", ".join(missing))
    else:
        info("运行环境已就绪。", "Runtime environment is ready.")

    stage("正在检查 Native GPU 组件", "Checking native GPU component")
    check_native_gpu_component()

    if args.check_only:
        return 0
    if args.install_only:
        info("依赖已准备完成。", "Dependencies are ready.")
        return 0

    stage("正在整理旧版本文件", "Organizing legacy files")
    organize_legacy_files()

    stage("正在启动应用", "Starting ShapeYourPhoto")
    launch_app()
    info("启动命令已发送。", "Launch command sent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print()
        print("依赖安装失败。/ Dependency installation failed.")
        print(f"Command exited with code {exc.returncode}: {' '.join(map(str, exc.cmd))}")
        print("请检查网络连接，或稍后重新运行 ShapeYourPhoto.exe。/ Check your network connection, then run ShapeYourPhoto.exe again.")
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print()
        print("启动准备失败。/ Startup preparation failed.")
        print(str(exc))
        raise SystemExit(1)
