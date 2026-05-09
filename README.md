# ShapeYourPhoto

图片质量分析、修复与清理工具。当前版本：`1.1.7`。

ShapeYourPhoto 是一个面向**桌面本地**使用的图像工具，支持图片导入、目录扫描、批量分析、自动/手动修复、不适合保留候选复核、相似图片复核删除、累计统计和本地性能基准。程序默认离线运行，**不上传用户图片**。

支持的桌面端：

- **macOS 11+ (Apple Silicon, arm64)** — `.dmg` 安装
- **Windows 10/11 (x64)** — Inno Setup 安装程序

## 下载安装

预编译产物挂在 [GitHub Releases](https://github.com/cwenwensen/shapeyourphoto/releases) 页，每个 tag 同时发布两个平台的安装包：

| 平台 | 文件名约定 | 说明 |
|---|---|---|
| macOS (Apple Silicon) | `ShapeYourPhoto-<version>-macOS-arm64.dmg` | 双击挂载 → 拖入 Applications |
| Windows (x64) | `ShapeYourPhoto-<version>-Windows-x64-Setup.exe` | 双击运行 Inno Setup 安装向导 |

例：版本 `1.1.6` 对应 `ShapeYourPhoto-1.1.6-macOS-arm64.dmg` 与 `ShapeYourPhoto-1.1.6-Windows-x64-Setup.exe`。

### macOS 首次启动

应用未做 Apple Developer 公证，Gatekeeper 首次会拦截。任选一种方式：

1. 在访达里**右键 ShapeYourPhoto.app → 打开**，确认对话框中再点"打开"，仅需一次。
2. 或终端执行一次：
   ```bash
   xattr -dr com.apple.quarantine /Applications/ShapeYourPhoto.app
   ```

### Windows 首次启动

SmartScreen 可能提示"未识别的应用"。点击**详细信息 → 仍要运行**即可，仅需一次。

### 用户数据存放位置

设置与统计自动持久化到系统标准目录，**卸载时不会被删除**：

- macOS: `~/Library/Application Support/ShapeYourPhoto/`
- Windows: `%APPDATA%\Helloalp\ShapeYourPhoto\`

## 当前主路径

1. 双击应用图标启动（Mac 走 .app，Windows 走 Inno Setup 装好的快捷方式）；开发态启动用 `python app.py`。
2. 选择图片、选择目录，或把图片/文件夹拖入主窗口。
3. 图片进入左侧主列表；单张图片也是加入主列表处理，不再存在独立单图窗口。
4. 点击"分析选中"或"分析全部"，后台线程池执行分析，Tk 控件更新回主线程。
5. 分析结果刷新右侧 HUD、指标条、诊断说明、属性和 Console。
6. 批次分析完成后，应用可生成 cleanup candidates 和批次级相似图片组。
7. 修复通过 `repair_planner.py` 和 `repair_engine.py` 生成单图自适应方案；降噪也在这条统一链路内执行。
8. 修复完成详情使用可筛选滚动窗口，不再用普通 `messagebox` 承载长结果列表。

## 当前能力

- 识别过曝、欠曝、失焦/模糊、低对比度、偏色、噪点偏高、层次不足、色彩寡淡、饱和度偏高等问题。
- 人像感知分析区分 raw face candidates、validated real faces、背身/侧背身人物、画作/海报脸和纹理误检。
- 场景字段包括 `scene_type`、`portrait_type`、`exposure_type`、`highlight_recovery_type`、`color_type`。
- cleanup candidate 默认不进入修复；只有在修复弹窗显式开启强制尝试后，才允许进入修复链，并仍会经过评分、安全检查和回退。
- 相似图片检测是分析批次的附加结果，只生成 `SimilarImageGroup`，不写回单张 `AnalysisResult`。
- 目录扫描支持默认扫描模式、四选项范围选择、忽略目录前缀和"最近扫描摘要"；默认跳过任意层级的 `_repair*` 输出目录。
- 性能审计通过 `perf_timings` / `perf_notes`、Console 摘要和 `/test` 本地 benchmark 维护。
- GPU 设置仅做可选后端检测和 CPU 回退提示；CUDA、CuPy、OpenCV-CUDA、torch CUDA 都不是硬依赖。

## 从源码运行

如果你想直接在 Python 环境里跑（不打包）：

```bash
# Windows
python app.py
# 或双击 start.bat / start_app.bat

# macOS / Linux
python3 app.py
```

依赖：

- `Python 3.10+` （**必须带 Tkinter**：macOS 上推荐 [python.org 官方安装包](https://www.python.org/downloads/macos/) 或 `brew install python-tk`）
- `Pillow >= 10.0.0`
- `numpy >= 1.26.0`
- `tkinterdnd2 >= 0.4.0` （跨平台拖拽）
- `platformdirs >= 4.0.0` （用户数据目录）

```bash
pip install -r requirements.txt
```

Windows 首次安装依赖也可以执行 `setup_deps.bat`。

## 从源码自行打包

打包工具链：**PyInstaller** 出可执行体，macOS 用 `create-dmg` 打 .dmg，Windows 用 **Inno Setup 6** 出安装向导。配置位于 `build/` 目录。

### macOS 本地打包

```bash
# 一次性安装
brew install create-dmg
pip install -r requirements.txt pyinstaller

# 一键构建：从 .app 到 .dmg
bash build/build_mac.sh
```

产物：`dist/ShapeYourPhoto.app` 和 `dist_installer/ShapeYourPhoto-<version>-macOS-arm64.dmg`。

### Windows 本地打包

```powershell
pip install -r requirements.txt pyinstaller
choco install innosetup -y    # 或从官网下载

# 1) 出 PyInstaller onedir
pyinstaller build\shapeyourphoto.spec --noconfirm --clean

# 2) 出 Inno Setup 安装包，版本号从 app_metadata.APP_VERSION 注入
for /f %v in ('python -c "from app_metadata import APP_VERSION; print(APP_VERSION)"') do set APP_VER=%v
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss /DAppVersion=%APP_VER%
```

产物：`dist_installer\ShapeYourPhoto-<version>-Windows-x64-Setup.exe`。

### 通过 GitHub Actions 自动构建并发版

仓库已配置 [`.github/workflows/release.yml`](.github/workflows/release.yml)：

```bash
# 1) 同步 app_metadata.APP_VERSION 与 tag
git tag v1.1.7
git push origin v1.1.7
```

CI 会并行在 `macos-14` (Apple Silicon) 和 `windows-latest` runner 上构建，校验 tag 与 `APP_VERSION` 一致后，自动把两份产物挂到对应 tag 的 GitHub Release。**tag 必须以 `v` 开头**且去掉 `v` 后等于 `APP_VERSION`，否则 CI 直接 fail。

也支持 `workflow_dispatch` 手动触发（不会发 Release，仅产 artifacts 用于测试）。

## 文档阅读顺序

正式维护文档从 [docs/README.md](docs/README.md) 开始。建议顺序：

1. [docs/PRESERVATION_RULES.md](docs/PRESERVATION_RULES.md)
2. [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md)
3. [docs/MODULE_REFERENCE.md](docs/MODULE_REFERENCE.md)
4. [docs/UI_AND_WORKFLOWS.md](docs/UI_AND_WORKFLOWS.md)
5. [docs/MAINTENANCE_GUIDE.md](docs/MAINTENANCE_GUIDE.md)
6. [docs/technical/README.md](docs/technical/README.md)
7. [docs/updates/README.md](docs/updates/README.md)

根目录 [MODULES.md](MODULES.md) 是快速模块索引；更完整说明以 `docs/` 为准。旧版本更新说明保留历史上下文，如与 1.1.6 当前文档冲突，以 1.1.6 文档和代码为准。

## 本地测试样张

`test/` 用于本地真实图片 benchmark 和回归检查。图片文件被 `.gitignore` 忽略，不应提交；只保留 [test/README.md](test/README.md) 作为约定说明。

## 元数据与输出边界

- 修复输出尽量保留 EXIF、DPI、ICC Profile 和可用 XMP。
- 输出前会归一 EXIF Orientation，避免像素已转正但查看器再次旋转。
- 程序写入可追踪的图片元数据，不生成 Windows 文件属性里的真正代码签名页。
- 默认修复流程不叠加可见水印；`watermark_signature.py` 仅作为保留模块。

Copyright (c) 2026 Francis Zhang & Helloalp. All rights reserved. No permission is granted to use, copy, modify, or distribute this project without explicit written permission.
