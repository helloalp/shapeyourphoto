#!/usr/bin/env bash
# 本地 macOS 一键构建：从 PyInstaller 到 .dmg
# 前置：python3 安装带 Tk（推荐 python.org 安装包 或 brew install python-tk）
#       已 pip install -r requirements.txt pyinstaller
#       已 brew install create-dmg

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo ">>> Cleaning previous build outputs"
rm -rf build/build_cache build/dist build/__pycache__
rm -rf dist dist_installer

echo ">>> Running PyInstaller"
pyinstaller build/shapeyourphoto.spec --noconfirm --clean

echo ">>> Verifying .app exists"
test -d "dist/ShapeYourPhoto.app" || { echo "Error: .app not built"; exit 1; }

echo ">>> Removing macOS quarantine attribute (本地测试免 Gatekeeper 提示)"
xattr -dr com.apple.quarantine "dist/ShapeYourPhoto.app" || true

echo ">>> Building .dmg"
bash build/build_dmg.sh

echo ">>> Done. Outputs:"
ls -la dist/ShapeYourPhoto.app dist_installer/*.dmg 2>/dev/null
