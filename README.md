﻿# ShapeYourPhoto

当前版本：`1.2.6`

ShapeYourPhoto 是一个本地桌面图片工具，用于导入图片、批量分析、查看质量提示、执行修复、复核不适合保留的图片和相似图片。图片分析和修复默认在本机进行，不主动上传用户图片。

## Windows 用户使用方法

1. 打开 [GitHub Releases](https://github.com/helloalp/shapeyourphoto/releases)，找到最新版本，展开最下方的列表，选择source_code.zip下载解压，至第3步。
2. 普通用户优先下载正式发布包；源码包更适合开发者和高级用户。
3. 如果下载的是源码包，解压到普通目录，例如：

```text
D:\ShapeYourPhoto\
```

4. 双击根目录里的：

```text
start.bat
```

`start.bat` 会检查 Python 和运行依赖。依赖齐全时会快速启动；缺少依赖时会按需安装 `requirements.txt` 中的运行依赖，然后继续启动。启动流程不会运行 benchmark、目录扫描或更新包下载。

## 没有 Python 时

源码包不能在没有 Python 的电脑上直接运行。双击 `start.bat` 时，如果没有找到 Python，会显示说明并保留窗口，不会直接闪退。

推荐做法：

- 普通用户：使用正式发布包或安装包。
- 需要运行源码包：先安装 Python 3.10 或更新版本，再双击 `start.bat`。

Python 下载地址：

```text
https://www.python.org/downloads/
```

`tools/legacy/setup_deps.bat` 和 `tools/legacy/start_app.bat` 仅作为兼容入口保留，普通用户不需要使用。

## macOS 用户

macOS 打包版本会在后续补充。源码方式运行时同样需要 Python 和 `requirements.txt` 中的依赖。

## 基本使用

1. 启动软件。
2. 点击“选择图片”或“选择目录”，也可以把图片或文件夹拖入主窗口。
3. 点击“分析全部”或“分析选中”。
4. 在右侧查看预览、风险提示、指标和属性信息。
5. 需要修复时，选择“修复当前”或“批量修复勾选”。
6. 如需复核不适合保留的图片或相似图片，可从主界面的相关入口打开。

## 更新

手动检查更新：打开“设置” -> “更新” -> 点击“检查更新”。

如果源码包环境提示依赖安装失败，请检查网络连接后重新双击 `start.bat`。也可以手动执行：

```text
python -m pip install -r requirements.txt
```

## 项目结构

- `start.bat`：普通用户入口。
- `app.py` / `app.pyw`：源码包 GUI 启动器。
- `src/`：应用代码。
- `tools/launcher/`：启动环境检查和按需依赖安装。
- `tools/legacy/`：旧入口兼容脚本。
- `tools/benchmark/`：本地 benchmark 工具，不属于日常启动流程。
- `build/`：打包配置。
- `docs/`：公开维护文档。

## 隐私说明

- 图片分析和修复默认在本地进行。
- 程序不会主动上传你的图片。
- 设置和统计数据保存在本机用户数据目录。
- 修复输出会尽量保留必要的图片元数据，并保护 ShapeYourPhoto 写入的来源信息。

Copyright (c) 2026 Francis Zhang & Helloalp. All rights reserved. No permission is granted to use, copy, modify, or distribute this project without explicit written permission.
