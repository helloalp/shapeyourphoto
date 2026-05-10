# ShapeYourPhoto

当前版本：`1.1.9`

ShapeYourPhoto 是一个本地桌面图片工具，用于导入图片、批量分析、查看质量提示、执行修复、复核不适合保留的图片和相似图片。程序默认在本机运行，不上传用户图片。

## Windows 用户使用方法

1. 打开 [GitHub Releases](https://github.com/helloalp/shapeyourphoto/releases)。
2. 下载最新版本的源码包或发布包。
3. 解压到一个普通目录，例如：

```text
D:\ShapeYourPhoto\
```

4. 第一次使用时，双击运行：

```text
setup_deps.bat
```

5. 以后启动软件，双击运行：

```text
start_app.bat
```

如果 Windows 弹出安全提示，确认来源是本项目 Release 后，选择继续运行。

## macOS 用户

macOS 版本会在后续补充。请不要继续使用旧版本指引作为当前安装说明。

## 基本使用

1. 启动软件。
2. 点击“选择图片”或“选择目录”，也可以把图片或文件夹拖入主窗口。
3. 点击“分析全部”或“分析选中”。
4. 在右侧查看预览、风险提示、指标和属性信息。
5. 需要修复时，选择“修复当前”或“批量修复勾选”。
6. 如需复核不适合保留的图片或相似图片，可从主界面的相关入口打开。

## 更新

ShapeYourPhoto 会使用内置更新地址检查新版本。你也可以在“设置 -> 更新”中查看当前版本并手动检查更新。

## 隐私说明

- 图片分析和修复默认在本地进行。
- 程序不会主动上传你的图片。
- 设置和统计数据保存在本机用户数据目录。
- 修复输出会尽量保留必要的图片元数据，并保护 ShapeYourPhoto 写入的溯源信息。

Copyright (c) 2026 Francis Zhang & Helloalp. All rights reserved. No permission is granted to use, copy, modify, or distribute this project without explicit written permission.
