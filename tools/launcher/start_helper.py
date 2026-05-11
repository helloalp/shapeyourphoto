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
REQUIREMENTS = ROOT / "requirements.txt"
APP_PYW = ROOT / "app.pyw"
APP_PY = ROOT / "app.py"

REQUIRED_IMPORTS = [
    ("Pillow", "PIL"),
    ("numpy", "numpy"),
    ("platformdirs", "platformdirs"),
    ("cryptography", "cryptography"),
]

if sys.platform != "win32" and sys.version_info < (3, 14):
    REQUIRED_IMPORTS.append(("tkinterdnd2", "tkinterdnd2"))


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
    if not REQUIREMENTS.exists():
        raise RuntimeError(f"requirements.txt not found: {REQUIREMENTS}")
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
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
        raise RuntimeError("ShapeYourPhoto needs Python 3.10 or newer.")

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

    if args.check_only:
        return 0
    if args.install_only:
        info("依赖已准备完成。", "Dependencies are ready.")
        return 0

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
        print("请检查网络连接，或稍后重新运行 start.bat。/ Check your network connection, then run start.bat again.")
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print()
        print("启动准备失败。/ Startup preparation failed.")
        print(str(exc))
        raise SystemExit(1)
