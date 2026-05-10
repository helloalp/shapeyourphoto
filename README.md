# ShapeYourPhoto

当前版本：`1.2.3`

ShapeYourPhoto 是一个本地桌面图片工具，用于导入图片、批量分析、查看质量提示、执行修复、复核不适合保留的图片和相似图片。图片分析和修复默认在本机进行，不主动上传用户图片。

## Windows 用户使用方法

1. 打开 [GitHub Releases](https://github.com/helloalp/shapeyourphoto/releases)。
2. 下载最新版本的源码包或发布包。
3. 解压到普通目录，例如：

```text
D:\ShapeYourPhoto\
```

4. 如果下载的是源码包，第一次使用前双击运行：

```text
setup_deps.bat
```

`setup_deps.bat` 会按 `requirements.txt` 安装 Pillow、numpy、platformdirs 和 `cryptography`。`cryptography` 用于云端更新 manifest 和 messages 的 Ed25519 签名验证。`tkinterdnd2` 仅用于支持该库的平台；Windows 版本使用原生拖放路径。

5. 以后启动软件，双击运行：

```text
start_app.bat
```

`start.bat` 和 `start_app.bat` 只负责启动程序，不会联网安装依赖、下载更新包、运行 benchmark 或执行耗时扫描。

## macOS 用户

macOS 打包版本会在后续补充。源码方式运行时同样需要先安装 `requirements.txt` 中的依赖。

## 基本使用

1. 启动软件。
2. 点击“选择图片”或“选择目录”，也可以把图片或文件夹拖入主窗口。
3. 点击“分析全部”或“分析选中”。
4. 在右侧查看预览、风险提示、指标和属性信息。
5. 需要修复时，选择“修复当前”或“批量修复勾选”。
6. 如需复核不适合保留的图片或相似图片，可从主界面的相关入口打开。

## 更新

ShapeYourPhoto 使用内置固定更新地址检查新版本，更新 manifest 和云端消息都需要签名验证。普通用户不需要填写更新 URL 或消息 URL。

手动检查更新：打开“设置” -> “更新” -> 点击“检查更新”。

如果源码包环境提示缺少 `cryptography`，请重新运行 `setup_deps.bat`，或手动执行：

```text
python -m pip install cryptography
```

## 隐私说明

- 图片分析和修复默认在本地进行。
- 程序不会主动上传你的图片。
- 设置和统计数据保存在本机用户数据目录。
- 修复输出会尽量保留必要的图片元数据，并保护 ShapeYourPhoto 写入的来源信息。

Copyright (c) 2026 Francis Zhang & Helloalp. All rights reserved. No permission is granted to use, copy, modify, or distribute this project without explicit written permission.
