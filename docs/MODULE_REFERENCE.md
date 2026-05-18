# Module Reference

本文记录 1.2.6 当前真实模块职责。旧版本提到的独立单图窗口、孤立去噪按钮、普通 `messagebox` 长修复详情，以及"先运行 setup 再运行 start_app"的启动方式均不是当前主路径。

## 启动与布局

### [start.bat](/E:/aitools/shapeyourphoto/start.bat)

普通 Windows 用户双击入口。批处理本身保持 ASCII-only，只负责查找 Python 并进入 `tools/launcher/start_helper.py`。不得加入 benchmark、目录扫描或更新包下载。

### [tools/launcher/start_helper.py](/E:/aitools/shapeyourphoto/tools/launcher/start_helper.py)

源码包启动 helper。显示中英文阶段提示，检查 Python 版本、检查运行依赖、缺少依赖时按需执行 `python -m pip install -r requirements.txt`，然后启动 `app.pyw` / `app.py`。

### [tools/legacy/](/E:/aitools/shapeyourphoto/tools/legacy)

保留旧 `setup_deps.bat`、`start_app.bat` 和 `start_app.vbs` 作为兼容入口。日常启动不需要使用。

### [app.py](/E:/aitools/shapeyourphoto/app.py) / [app.pyw](/E:/aitools/shapeyourphoto/app.pyw)

源码包 GUI 薄启动器。`app.py` 将 `src/` 加入模块搜索路径，然后创建 Tk 根窗口、设置标题与图标、挂载 `PhotoAnalyzerApp` 并居中。

## 应用包

### [src/ui_app.py](/E:/aitools/shapeyourphoto/src/ui_app.py)

主窗口装配和高层协调入口。保留实例状态初始化、菜单 wiring、布局、拖拽安装/卸载和窗口关闭。扫描、分析、修复、列表、Console 和复核细节通过 `src/ui_*` mixin 接入。

### [src/ui/](/E:/aitools/shapeyourphoto/src/ui)

UI 基础设施包，包含窗口标题、语言状态、display mapping、主题、HiDPI、Splash、EXIF 编辑、更新和公告弹窗。新增共享 UI 能力优先进入这里。

### [src/analysis/](/E:/aitools/shapeyourphoto/src/analysis)

分析流水线包。`core.py` 承载主分析流程，`portrait.py` 承载人像候选和验证，`discard.py` 生成不适合保留候选（cleanup candidates），`common.py` 提供共享统计、掩膜和计时工具。

### [src/analyzer.py](/E:/aitools/shapeyourphoto/src/analyzer.py)

兼容薄入口，仅 re-export `analysis.analyze_image` 与 `analysis.is_supported_image`。新增分析逻辑不得重新堆回这里。

### [src/repair_planner.py](/E:/aitools/shapeyourphoto/src/repair_planner.py)

把单张 `AnalysisResult` 映射为 `RepairPlan`。计划包含 `method_ids`、`op_strengths`、`policy` 和 notes，避免批量图片共用统一强度。

### [src/repair_engine.py](/E:/aitools/shapeyourphoto/src/repair_engine.py) / [src/repair_ops.py](/E:/aitools/shapeyourphoto/src/repair_ops.py)

执行修复链和具体图像算子。这里会直接影响视觉风格、输出安全和元数据保留，修改后必须谨慎验证。

### [src/file_actions.py](/E:/aitools/shapeyourphoto/src/file_actions.py)

目录扫描、安全清理和输出路径生成。扫描必须遵守前缀、后缀、包含三类文件夹名称忽略规则，支持进度回调和取消事件；安全清理必须优先回收站，失败时移入 `_cleanup_candidates`。

### [src/legacy_cleanup.py](/E:/aitools/shapeyourphoto/src/legacy_cleanup.py)

启动准备阶段的旧版本残留整理模块。只识别旧根目录模块、旧入口和旧运行缓存，命中项移入 `data/update_quarantine/legacy_cleanup/` 并生成清单；受保护目录、用户数据、样张、私有文档和仓库文件必须跳过。

### [src/gpu_accel.py](/E:/aitools/shapeyourphoto/src/gpu_accel.py)

GPU 状态探测、native backend 调用与保守回退。负责查找随包分发的 `gpu/shapeyourphoto_gpu_core.exe`，通过 JSON / persistent worker 调用 Rust/wgpu 后端执行大图亮度统计，并输出诊断 JSON；native 组件缺失、超时、设备不可用或小图任务不划算时不得影响分析、修复或设置页打开。
### [native/gpu-core](/E:/aitools/shapeyourphoto/native/gpu-core)

ShapeYourPhoto 自带 GPU core。Rust + wgpu 实现，普通用户不需要安装 Rust、CUDA Toolkit、torch、CuPy 或 OpenCV CUDA。当前提供 `capabilities`、`self-test`、`luma-stats` 和 `serve`，打包后位于 `gpu/`。

### [src/stats_store.py](/E:/aitools/shapeyourphoto/src/stats_store.py)

统计持久化，写入系统用户数据目录。Windows 使用用户级 DPAPI 加密；旧 `usage_stats.json` 可迁移并保留 migrated 备份。

### [src/app_metadata.py](/E:/aitools/shapeyourphoto/src/app_metadata.py)

应用名、版本号、应用身份和内置更新历史。版本升级必须同步这里、根 `CHANGELOG.md` 和对应 `docs/updates/<version>.md`。

### [src/updater.py](/E:/aitools/shapeyourphoto/src/updater.py)

兼容 updater 入口，保留旧版本和旧文档中的启动路径。新版主程序优先启动 [src/updater_bootstrap.py](/E:/aitools/shapeyourphoto/src/updater_bootstrap.py)，实际实现位于 [src/updater_v2.py](/E:/aitools/shapeyourphoto/src/updater_v2.py)。更新 manifest 的 `managed_files` 应使用当前布局下的相对路径，例如 `src/ui/cloud_actions.py`；1.2.3/1.2.4 不再通过内置 updater 直升 1.2.5，相关止血发布使用手动下载提示 manifest。

## 工具与构建

### [tools/benchmark/benchmark_test_images.py](/E:/aitools/shapeyourphoto/tools/benchmark/benchmark_test_images.py)

本地 `test/` 真实图片 benchmark。输出 wall time、worker cumulative、queue/wait、慢图、慢阶段、相似检测耗时、问题图和不适合保留候选数量。`test/` 为空时跳过；报告写入被忽略的 `benchmark_reports/`。

### [build/](/E:/aitools/shapeyourphoto/build)

PyInstaller、Inno Setup 和 dmg 构建配置。`build/shapeyourphoto.spec` 仍以根 `app.py` 为入口，并将 `src/` 加入分析路径。

## 已废弃但需记住的旧入口

- 独立 `single_image_window.py` 和"单图模式"不是当前主路径；单张图片通过主列表导入。
- 孤立"去噪当前"按钮不是当前主路径；降噪由分析、修复规划和修复执行链统一处理。
- 批量修复长详情不应回退到普通 `messagebox`；应继续使用 `repair_completion_dialog.py`。
