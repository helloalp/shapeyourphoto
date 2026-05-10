# Module Reference

本文记录 1.1.6 当前真实模块职责。旧版本提到的独立单图窗口、孤立去噪按钮、普通 `messagebox` 长修复详情均不是当前主路径。

## 启动与窗口基础

### [start.bat](/E:/aitools/shapeyourphoto/start.bat)

日常双击入口，只负责进入 `start_app.bat`。不得加入依赖安装、扫描或其他耗时逻辑。

### [start_app.bat](/E:/aitools/shapeyourphoto/start_app.bat)

查找 `py` / `python` / `pythonw`，优先启动 `app.pyw`。Python 缺失时提示用户，不自动安装依赖。

### [app.py](/E:/aitools/shapeyourphoto/app.py) / [app.pyw](/E:/aitools/shapeyourphoto/app.pyw)

Python GUI 入口。`app.py` 创建 Tk 根窗口、设置标题与图标、挂载 `PhotoAnalyzerApp` 并居中。

### [desktop_integration.py](/E:/aitools/shapeyourphoto/desktop_integration.py) / [window_layout.py](/E:/aitools/shapeyourphoto/window_layout.py)

桌面图标、任务栏集成与窗口居中/二级窗口尺寸约束。

## 主界面与 UI 弹窗

### [ui_app.py](/E:/aitools/shapeyourphoto/ui_app.py)

主窗口装配和高层协调入口。当前保留：

- `PhotoAnalyzerApp` 实例状态初始化。
- Tk 样式、菜单、左右分栏、Treeview、cleanup 面板、HUD、诊断区、属性区和 Console 控件装配。
- Windows 拖拽安装/卸载、关闭窗口处理。
- 设置、历史、统计等高层菜单入口。

具体工作流通过下列 UI mixin 模块接入，避免继续把扫描、分析、修复、列表和复核细节堆回主类文件。维护时不要把算法判断塞进 UI；UI 只消费 `AnalysisResult`、`RepairRecord` 和批次附加结果。

### [ui_constants.py](/E:/aitools/shapeyourphoto/ui_constants.py)

主 UI 共享常量：筛选选项、分析进度粒度、默认 worker 上限、分析/修复阶段耗时标签和 `AnalysisCanceled`。

### [ui_task_console.py](/E:/aitools/shapeyourphoto/ui_task_console.py)

任务基础设施与 Console/perf 摘要 mixin。负责 UI 队列派发、Tk 主线程队列 drain、Console 合并刷新、控件启停、进度任务 begin/finish、worker 规划、耗时格式化、分析/修复性能 rollup 和慢阶段摘要。

### [ui_scan_actions.py](/E:/aitools/shapeyourphoto/ui_scan_actions.py)

导入与扫描 mixin。负责选择目录、选择单图、拖拽路径分流、单图入列、目录扫描模式解析、后台扫描 worker、扫描进度、扫描摘要和扫描完成后触发自动分析。

### [ui_analysis_actions.py](/E:/aitools/shapeyourphoto/ui_analysis_actions.py)

分析任务 mixin。负责“分析全部/选中”、run_id/cancel_event、后台分析 worker、单张结果主线程写回、取消回滚、相似图检测阶段提示和批次完成汇总。

### [ui_repair_actions.py](/E:/aitools/shapeyourphoto/ui_repair_actions.py)

修复任务 mixin。负责修复当前/批量修复入口、批量目标集合解析、修复弹窗、缺失分析的修复前补分析、后台修复 worker、修复阶段进度、修复完成详情、统计更新和调试打开前后对比。“修复当前”只用焦点图；“批量修复勾选”优先真正多选，其次勾选集合。

### [ui_file_list.py](/E:/aitools/shapeyourphoto/ui_file_list.py)

主列表与右侧详情 mixin。负责排序、Treeview/cleanup Treeview 刷新、单选/多选、勾选状态、当前项定位、预览摘要、HUD、EXIF/ICC/DPI/XMP 属性摘要、安全 EXIF 编辑入口和从列表移除。主界面已不提供“导出清理清单”入口。

### [ui_review_actions.py](/E:/aitools/shapeyourphoto/ui_review_actions.py)

cleanup candidate 与 similar group 复核入口 mixin。负责分析后候选复核、重新打开候选窗口、相似组列表和组内对比入口、安全删除回调、删除后刷新主列表/候选/相似组状态。

### [progress_dialog.py](/E:/aitools/shapeyourphoto/progress_dialog.py)

扫描、分析、修复共用进度弹窗。负责阶段文案、耗时显示、进度条和取消按钮。分析窗口关闭叉号等同取消分析。窗口内部使用固定区：标题、说明、进度条、计数/耗时、固定高度阶段摘要和底部按钮，长文本压缩显示，详细信息进入 Console。

### [settings_dialog.py](/E:/aitools/shapeyourphoto/settings_dialog.py)

统一“应用设置”面板。当前管理扫描忽略前缀、默认扫描模式、修复完成详情默认筛选、分析并发模式、自定义 worker 数和 GPU 加速模式。

### [scan_dialogs.py](/E:/aitools/shapeyourphoto/scan_dialogs.py)

目录包含子目录时的扫描范围选择窗口。内容区可滚动，底部取消按钮必须在小屏/缩放环境下可达。

### [scan_summary_dialog.py](/E:/aitools/shapeyourphoto/scan_summary_dialog.py)

最近扫描摘要窗口，展示每次扫描根目录、模式、导入数量、访问文件数量、忽略前缀和被跳过目录明细。

### [repair_dialog.py](/E:/aitools/shapeyourphoto/repair_dialog.py)

修复准备窗口。收集自动/手动修复方法、输出目录名、后缀/覆盖策略，以及“强制修复不值得保留的图片”开关。多图批量时显示批量说明和方法汇总，不把当前焦点图推荐误显示为整批统一方案。

### [repair_completion_dialog.py](/E:/aitools/shapeyourphoto/repair_completion_dialog.py)

批量修复完成详情窗口。支持按已修复、已跳过、失败、强制尝试但未保存、强制尝试后保存、不适合保留相关、候选回退/no-op 等类别筛选。

### [cleanup_review_dialog.py](/E:/aitools/shapeyourphoto/cleanup_review_dialog.py)

cleanup candidate 复核窗口。本轮候选默认不勾选，用户确认后才可进入安全清理。

### [similar_review_dialog.py](/E:/aitools/shapeyourphoto/similar_review_dialog.py)

相似组列表窗口和组内对比窗口。列表支持滚动、筛选、多选；组内对比支持分页和每图删除。删除操作必须回调主应用的 `safe_cleanup_paths()`。

### 其他 UI 模块

- [debug_open_dialog.py](/E:/aitools/shapeyourphoto/debug_open_dialog.py)：调试模式打开本轮成功修复的前后对比文件。
- [diagnostics_chart.py](/E:/aitools/shapeyourphoto/diagnostics_chart.py)：右侧指标条图。
- [history_dialog.py](/E:/aitools/shapeyourphoto/history_dialog.py)：内置版本历史窗口。
- [stats_dialog.py](/E:/aitools/shapeyourphoto/stats_dialog.py)：统计和 CSV 导出窗口。

## 设置、扫描、文件与缓存

### [app_settings.py](/E:/aitools/shapeyourphoto/app_settings.py)

应用设置的默认值、校验、读写、损坏备份和 worker 规划。新增设置必须在这里统一定义和规范化，再接入 UI。

### [file_actions.py](/E:/aitools/shapeyourphoto/file_actions.py)

目录扫描、安全清理和输出路径生成。扫描必须遵守忽略前缀，默认包含 `_repair`。安全清理必须优先回收站，失败时移入 `_cleanup_candidates`。

### [drag_drop.py](/E:/aitools/shapeyourphoto/drag_drop.py)

Windows 原生拖拽支持。平台相关且高风险，修改后要验证图片和文件夹拖入。

### [preview_cache.py](/E:/aitools/shapeyourphoto/preview_cache.py)

缩略图缓存，避免主列表频繁重复读取大图。

### [result_sorting.py](/E:/aitools/shapeyourphoto/result_sorting.py)

主列表排序规则，避免排序逻辑散落在 UI 代码中。

### [metadata_utils.py](/E:/aitools/shapeyourphoto/metadata_utils.py)

右侧属性/EXIF 面板摘要生成。

## 分析模块

### [analyzer.py](/E:/aitools/shapeyourphoto/analyzer.py)

兼容薄入口，仅 re-export `analysis.analyze_image` 与 `analysis.is_supported_image`。新增分析逻辑不得重新堆回这里。

### [analysis/core.py](/E:/aitools/shapeyourphoto/analysis/core.py)

单张分析主流程。负责图片打开、`ImageOps.exif_transpose`、working image 缩放、基础统计、曝光/锐度/色彩/噪声判断、场景字段、issues、metrics、cleanup candidate 和 `perf_timings`。

### [analysis/portrait.py](/E:/aitools/shapeyourphoto/analysis/portrait.py)

人像候选、真实正面人脸验证、背身/侧背身/画作脸/纹理误检区分和人像区域构建。只有 validated real face 可进入真人虚焦和 portrait policy。

### [analysis/discard.py](/E:/aitools/shapeyourphoto/analysis/discard.py)

从 `Issue.meta` 生成 `CleanupCandidate`，使“不适合保留”规则与 UI/文件删除解耦。

### [analysis/common.py](/E:/aitools/shapeyourphoto/analysis/common.py)

共享统计、掩膜、形态学清理、性能计时和中文问题文案兜底。

### [similar_detector.py](/E:/aitools/shapeyourphoto/similar_detector.py)

分析批次完成后的相似图检测。使用轻量缩略特征、感知哈希、结构向量、尺寸和时间辅助生成 `SimilarImageGroup`，并记录相似检测分段耗时。

### [gpu_accel.py](/E:/aitools/shapeyourphoto/gpu_accel.py)

可选 GPU 后端检测和状态文案。检测 CuPy、OpenCV-CUDA、torch CUDA，但不把它们变成必需依赖，也不声明默认 GPU offload。

### [benchmark_test_images.py](/E:/aitools/shapeyourphoto/benchmark_test_images.py)

本地 `test/` 真实图片 benchmark。输出 wall time、worker cumulative、queue/wait、慢图、慢阶段、相似检测耗时、问题图和 cleanup candidate 数量。`test/` 为空时跳过；有图片时会在被忽略的 `benchmark_reports/` 生成 JSON/Markdown 报告，并可读取本地 `test/manifest.json` 做简单预期对比。

## 修复模块

### [repair_planner.py](/E:/aitools/shapeyourphoto/repair_planner.py)

把单张 `AnalysisResult` 映射为 `RepairPlan`。计划包含 `method_ids`、`op_strengths`、`policy` 和 notes，避免批量图片共用统一强度。

### [repair_engine.py](/E:/aitools/shapeyourphoto/repair_engine.py)

执行修复链。负责读取图片、执行候选、评分、安全检查、cleanup candidate 强制尝试、回退/no-op、输出保存、元数据保留和修复耗时记录。

### [repair_ops.py](/E:/aitools/shapeyourphoto/repair_ops.py)

具体修复算子，包括曝光、阴影、高光、对比、色彩、锐化和场景化降噪。修改这里会直接影响视觉风格，需要谨慎验证。

## 数据、统计与元信息

### [models.py](/E:/aitools/shapeyourphoto/models.py)

统一数据结构定义。新增字段应先在这里设计，再接入分析、修复和 UI。

### [stats_store.py](/E:/aitools/shapeyourphoto/stats_store.py)

统计持久化，1.1.7 起默认写入被忽略的 `data/usage_stats.dpapi`。Windows 使用用户级 DPAPI 加密；旧 `usage_stats.json` 会迁移并保留 migrated 备份。

### `ui/`

1.1.7 新增 UI 基础设施包：

- `ui/window_titles.py`：二级窗口标题统一格式。
- `ui/display_names.py`：内部英文值到 UI 中文显示名映射。
- `ui/themes.py`：五套外观风格 token。
- `ui/hidpi.py`：DPI awareness、Tk scaling 和系统字体配置。
- `ui/splash.py`：启动 Splash。
- `ui/metadata_editor.py`：安全 EXIF 文本字段编辑。

### [app_console.py](/E:/aitools/shapeyourphoto/app_console.py)

只读 Console 缓存。UI 层负责合并刷新到 Text 控件。

### [app_metadata.py](/E:/aitools/shapeyourphoto/app_metadata.py)

应用名、版本号和内置更新历史。

### [watermark_signature.py](/E:/aitools/shapeyourphoto/watermark_signature.py)

保留的可见水印/签名叠加模块。默认修复输出不调用它。
# 1.1.8 Module Addendum

- `developer_mode.py`: session-only developer unlock using PBKDF2-SHA256 password hashes from local secret sources.
- `cloud_client.py`, `cloud_security.py`, `cloud_state.py`, `integrity_guard.py`: signed update/message fetch, signature/sha256 helpers, HMAC local state and module integrity checks.
- `ui/cloud_actions.py`, `ui/cloud_dialogs.py`: update and cloud-message Tk UI flow.
- `updater.py`: independent update process with safe extraction, replacement, quarantine and rollback.
- `ui/metadata_editor.py`: normal/developer EXIF editor with ShapeYourPhoto provenance protection.

# 1.2.0 Module Addendum

- `cloud_security.py`: 继续使用小写 `cryptography` 包导入 Ed25519 验签后端；缺少依赖时返回面向用户可理解的依赖安装提示，同时保留维护者调试信息。
- `assets/update_public_key.pem`: 正式内置更新公钥。该文件只能包含 public key，不得替换为私钥。
- `requirements.txt` / `setup_deps.bat`: 源码包依赖入口，包含 `cryptography>=42.0.0`。启动脚本不承担依赖安装。
- `build/shapeyourphoto.spec`: 打包入口显式包含 `cryptography` Ed25519 验签相关 hidden imports。
