﻿# ShapeYourPhoto

当前版本：`1.2.7`

ShapeYourPhoto 是一个本地桌面图片工具，用于导入图片、批量分析、查看质量提示、执行修复、复核不适合保留的图片和相似图片。图片分析和修复默认在本机进行，不主动上传用户图片。

## 文档入口

本 README 只保留快速启动和项目入口。功能、维护、版本记录和文档写作规则以 [docs/README.md](E:/aitools/shapeyourphoto/docs/README.md) 为准；修改 README、`docs/CHANGELOG.md` 或任何文档前，先阅读 `docs/` 中的维护规范。

## Windows 使用方法

1. 打开 [GitHub Releases](https://github.com/helloalp/shapeyourphoto/releases)，下载正式发布包或源码包。
2. 正式发布包优先双击根目录的 `ShapeYourPhoto.exe`。源码包保留开发、审计和手动运行入口。
3. 如果下载的是源码包，解压到普通目录，例如：

```text
D:\ShapeYourPhoto\
```

4. 如果下载的是源码包且已经构建原生启动器，双击根目录：

```text
ShapeYourPhoto.exe
```

未构建原生启动器时，可使用 `tools/launcher/start.bat` 作为源码包兼容入口。它会检查 Python 和运行依赖；缺少依赖时会按需安装 `requirements/runtime.txt` 中的运行依赖，然后继续启动。启动流程不会运行 benchmark、目录扫描或更新包下载。

v1.2.6 入口整理：统计在“查看”菜单，官网和日志导出在“帮助”菜单，更新历史在“设置 -> 更新”。批量质量保持格式转换入口位于主按钮区，GPS 编辑入口位于“属性 / EXIF”页。

## 没有 Python 时

源码包不能在没有 Python 的电脑上直接运行。通过 `ShapeYourPhoto.exe` 或 `tools/launcher/start.bat` 启动时，如果没有找到 Python，会显示说明，不会直接闪退。

推荐做法：

- 使用正式发布包或安装包。
- 运行源码包时，先安装 Python 3.10 或更新版本，再启动 `ShapeYourPhoto.exe`；未构建原生启动器时使用 `tools/launcher/start.bat`。

Python 下载地址：

```text
https://www.python.org/downloads/
```

`tools/legacy/setup_deps.bat` 和 `tools/legacy/start_app.bat` 仅作为兼容入口保留，日常启动不需要使用。

## macOS 用户

macOS 打包版本会在后续补充。源码方式运行时同样需要 Python 和 `requirements/runtime.txt` 中的依赖。

## 基本使用

1. 启动软件。
2. 点击“选择图片”或“选择目录”，也可以把图片或文件夹拖入主窗口。
3. 点击“分析全部”或“分析选中”。
4. 在右侧查看预览、风险提示、指标和属性信息。
5. 需要修复时，选择“修复当前”或“批量修复勾选”。
6. 如需复核不适合保留的图片或相似图片，可从主界面的相关入口打开。

## 更新

手动检查更新：打开“设置” -> “更新” -> 点击“检查更新”。

如果源码包环境提示依赖安装失败，请检查网络连接后重新启动。也可以手动执行：

```text
python -m pip install -r requirements/runtime.txt
```

## 项目结构

- `ShapeYourPhoto.exe`：根目录主启动入口。
- `requirements/runtime.txt`：源码包运行依赖。
- `native/launcher/`：原生 Rust 启动 host。
- `native/gpu-core/`：Rust/wgpu native GPU backend。
- `tools/entry/app.py` / `tools/entry/app.pyw`：源码包 GUI 启动器。
- `src/`：应用代码。
- `tools/launcher/`：启动环境检查、按需依赖安装和源码包 bat 兼容入口。
- `tools/legacy/`：旧入口兼容脚本。
- `tools/benchmark/`：本地 benchmark 工具，不属于日常启动流程。
- `build/`：打包配置。
- `docs/`：公开维护文档和版本记录。

更新历史不得写入开发者设备型号、私有测试环境、内部依赖栈细节、适用人群限制或产品发展边界；相关规则见 [docs/README.md](E:/aitools/shapeyourphoto/docs/README.md) 和 [docs/PRESERVATION_RULES.md](E:/aitools/shapeyourphoto/docs/PRESERVATION_RULES.md)。

## 隐私说明

- 图片分析和修复默认在本地进行。
- 程序不会主动上传你的图片。
- 设置和统计数据保存在本机用户数据目录。
- 修复输出会尽量保留必要的图片元数据，并保护 ShapeYourPhoto 写入的来源信息。

Copyright (c) 2026 Francis Zhang & Helloalp. All rights reserved. No permission is granted to use, copy, modify, or distribute this project without explicit written permission.
# Shape Your Photo v1.2.7

v1.2.7 focuses on runtime responsiveness, clearer performance diagnostics, and the native Windows startup host while preserving the current Python/Tk app surface.

- Batch analysis, scanning, conversion, cleanup review, similar review, and preview dialogs reduce avoidable UI stalls.
- Benchmark output separates wall time, worker cumulative time, and queue wait more clearly.
- Native GPU diagnostics now report the 1.2.7 core version, and the Windows startup path now prefers root `ShapeYourPhoto.exe`; `tools/launcher/start.bat` remains as a source-tree compatibility fallback.
- The recommended Windows release remains the portable package. GitHub Actions test EXE artifacts are experimental smoke-test builds.
