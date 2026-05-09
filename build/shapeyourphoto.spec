# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ShapeYourPhoto.

跨平台同一份 spec：根据 sys.platform 自动选择图标、bundle 配置与产物形态。
- macOS: 输出 dist/ShapeYourPhoto.app（onedir，含 BUNDLE）
- Windows: 输出 dist/ShapeYourPhoto/（onedir + .exe，便于 Inno Setup 直接打包）

执行：
    pyinstaller build/shapeyourphoto.spec --noconfirm
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


# spec 在 PyInstaller 上下文里，__file__ 不可靠；用工作目录推导项目根
PROJECT_ROOT = Path(os.getcwd()).resolve()
ASSETS_DIR = PROJECT_ROOT / "assets"

APP_NAME = "ShapeYourPhoto"
BUNDLE_ID = "com.helloalp.shapeyourphoto"

# 从 app_metadata 读取版本号，单一真源
sys.path.insert(0, str(PROJECT_ROOT))
from app_metadata import APP_VERSION  # type: ignore

if sys.platform == "darwin":
    icon_file = str(ASSETS_DIR / "app_icon.icns")
elif sys.platform == "win32":
    icon_file = str(ASSETS_DIR / "app_icon.ico")
else:
    icon_file = None

# tkinterdnd2 自带 tkdnd Tcl 扩展（动态库），必须显式收集
tkdnd_data = collect_data_files("tkinterdnd2", include_py_files=False)

# analysis 包内有动态导入，显式收集子模块更稳
analysis_submodules = collect_submodules("analysis")

datas = [
    (str(ASSETS_DIR), "assets"),
] + tkdnd_data

hiddenimports = [
    "PIL._tkinter_finder",
    "tkinterdnd2",
    "platformdirs",
] + analysis_submodules

excludes = [
    "matplotlib",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "tkinter.test",
    "test",
    "unittest",
    "pydoc_data",
]


a = Analysis(
    [str(PROJECT_ROOT / "app.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 在 mac 上破坏代码签名能力，windows 上偶被杀软误报
    console=False,
    disable_windowed_traceback=False,
    icon=icon_file,
    target_arch=None,  # mac job 默认 arm64，win job 默认 x86_64
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_file,
        bundle_identifier=BUNDLE_ID,
        version=APP_VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleVersion": APP_VERSION,
            "CFBundleShortVersionString": APP_VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "Copyright (c) 2026 Francis Zhang & Helloalp.",
            # 让 .app 接受图片文件拖拽到 Dock 图标
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "Image",
                    "CFBundleTypeRole": "Viewer",
                    "LSItemContentTypes": ["public.image"],
                }
            ],
        },
    )
