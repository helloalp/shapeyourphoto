# 模块快速索引

本文是根目录快速索引，帮助接手者先定位文件。正式维护规则、流程细节和版本说明以 [docs/README.md](/E:/aitools/shapeyourphoto/docs/README.md) 为准；如果旧版本说明与当前行为冲突，以 1.1.6 文档和代码为准。

## 启动链路

- [start.bat](/E:/aitools/shapeyourphoto/start.bat)：日常双击入口，只转到 `start_app.bat`。
- [start_app.bat](/E:/aitools/shapeyourphoto/start_app.bat)：查找 `py`/`python`/`pythonw` 并启动 `app.pyw` 或 `app.py`，不安装依赖。
- [app.py](/E:/aitools/shapeyourphoto/app.py)：创建 Tk 根窗口、配置图标、挂载 `PhotoAnalyzerApp`。
- [app.pyw](/E:/aitools/shapeyourphoto/app.pyw)：无控制台 GUI 入口。
- [setup_deps.bat](/E:/aitools/shapeyourphoto/setup_deps.bat)：首次安装依赖入口，与日常启动隔离。

## 主界面与弹窗

- [ui_app.py](/E:/aitools/shapeyourphoto/ui_app.py)：主应用控制中心。管理列表、导入、扫描、分析/修复调度、run_id/cancel_event、Console 合并刷新、cleanup/similar 弹窗入口、统计和右侧信息区。
- [progress_dialog.py](/E:/aitools/shapeyourphoto/progress_dialog.py)：扫描、分析、修复共用进度控制器，包含阶段文案、耗时和取消入口。
- [settings_dialog.py](/E:/aitools/shapeyourphoto/settings_dialog.py)：统一“应用设置”面板，管理扫描、修复详情筛选、分析并发和 GPU 选项。
- [scan_dialogs.py](/E:/aitools/shapeyourphoto/scan_dialogs.py)：目录扫描范围选择对话框。
- [scan_summary_dialog.py](/E:/aitools/shapeyourphoto/scan_summary_dialog.py)：最近扫描摘要窗口，展示按前缀聚合的跳过统计和明细。
- [repair_dialog.py](/E:/aitools/shapeyourphoto/repair_dialog.py)：修复准备窗口，包含自动/手动方法、输出规则和 cleanup candidate 强制尝试开关。
- [repair_completion_dialog.py](/E:/aitools/shapeyourphoto/repair_completion_dialog.py)：修复完成详情窗口，支持筛选、滚动和复制。
- [cleanup_review_dialog.py](/E:/aitools/shapeyourphoto/cleanup_review_dialog.py)：本轮不适合保留候选复核窗口，默认不勾选任何图片。
- [similar_review_dialog.py](/E:/aitools/shapeyourphoto/similar_review_dialog.py)：相似组列表与组内对比窗口；删除操作回调主应用安全清理逻辑。
- [debug_open_dialog.py](/E:/aitools/shapeyourphoto/debug_open_dialog.py)：调试模式下选择打开本轮修复成功的原图/输出图。
- [history_dialog.py](/E:/aitools/shapeyourphoto/history_dialog.py)、[stats_dialog.py](/E:/aitools/shapeyourphoto/stats_dialog.py)：版本历史与统计窗口。

## 设置、扫描与文件动作

- [app_settings.py](/E:/aitools/shapeyourphoto/app_settings.py)：应用设置默认值、校验、读写、损坏备份和 worker 规划。`resolve_analysis_worker_plan()` 是分析并发配置的唯一入口。
- [file_actions.py](/E:/aitools/shapeyourphoto/file_actions.py)：目录扫描、忽略前缀、扫描摘要、安全清理、清理清单导出和修复输出路径生成。
- [drag_drop.py](/E:/aitools/shapeyourphoto/drag_drop.py)：Windows `WM_DROPFILES` 原生拖拽支持。
- [preview_cache.py](/E:/aitools/shapeyourphoto/preview_cache.py)：左侧缩略图缓存。
- [result_sorting.py](/E:/aitools/shapeyourphoto/result_sorting.py)：主列表排序逻辑。
- [metadata_utils.py](/E:/aitools/shapeyourphoto/metadata_utils.py)：右侧属性/EXIF 摘要。

## 分析链路

- [analyzer.py](/E:/aitools/shapeyourphoto/analyzer.py)：兼容入口，只导出 `analysis` 包中的 `analyze_image()` 和 `is_supported_image()`。
- [analysis/core.py](/E:/aitools/shapeyourphoto/analysis/core.py)：主分析流程，负责图片读取、EXIF 转正、working image、基础统计、问题生成、诊断字段和 `perf_timings`。
- [analysis/portrait.py](/E:/aitools/shapeyourphoto/analysis/portrait.py)：人像候选、真实正面人脸验证、背身/画作/纹理误检区分和人像区域构建。
- [analysis/discard.py](/E:/aitools/shapeyourphoto/analysis/discard.py)：从 issue meta 生成通用 cleanup candidates。
- [analysis/common.py](/E:/aitools/shapeyourphoto/analysis/common.py)：共享统计、掩膜、计时和文案兜底工具。
- [similar_detector.py](/E:/aitools/shapeyourphoto/similar_detector.py)：批次级相似图片检测，输出 `SimilarImageGroup`，不改写单张 `AnalysisResult`。
- [gpu_accel.py](/E:/aitools/shapeyourphoto/gpu_accel.py)：可选 GPU 后端探测和 CPU 回退说明，不提供硬依赖。
- [benchmark_test_images.py](/E:/aitools/shapeyourphoto/benchmark_test_images.py)：读取本地 `test/` 样张执行性能基准；`test/` 为空时安全跳过。

## 修复链路

- [repair_planner.py](/E:/aitools/shapeyourphoto/repair_planner.py)：按单张 `AnalysisResult` 生成 `RepairPlan`，包含方法、强度、策略和说明。
- [repair_engine.py](/E:/aitools/shapeyourphoto/repair_engine.py)：执行修复、候选评分、安全检查、回退/no-op、元数据保留和输出保存。
- [repair_ops.py](/E:/aitools/shapeyourphoto/repair_ops.py)：曝光、对比、色彩、清晰度和场景化降噪等具体算子。
- [watermark_signature.py](/E:/aitools/shapeyourphoto/watermark_signature.py)：保留的可见水印/签名叠加模块，默认不接入修复输出。

## 数据结构与元信息

- [models.py](/E:/aitools/shapeyourphoto/models.py)：`AnalysisResult`、`Issue`、`CleanupCandidate`、`SimilarImageGroup`、`RepairPlan`、`RepairRecord` 等结构定义。
- [app_metadata.py](/E:/aitools/shapeyourphoto/app_metadata.py)：应用名、版本号和内置版本历史。
- [CHANGELOG.md](/E:/aitools/shapeyourphoto/CHANGELOG.md)：根版本变更记录。
- [docs/](/E:/aitools/shapeyourphoto/docs/README.md)：正式维护文档体系。

## 已废弃但需记住的旧入口

- 独立 `single_image_window.py` 和“单图模式”不是当前主路径；单张图片通过主列表导入。
- 孤立“去噪当前”按钮不是当前主路径；降噪由分析、修复规划和修复执行链统一处理。
- 批量修复长详情不应回退到普通 `messagebox`；应继续使用 `repair_completion_dialog.py`。
# 1.1.8 Quick Index Addendum

- [developer_mode.py](/E:/aitools/shapeyourphoto/developer_mode.py): session-only developer password verification.
- [cloud_client.py](/E:/aitools/shapeyourphoto/cloud_client.py), [cloud_security.py](/E:/aitools/shapeyourphoto/cloud_security.py), [cloud_state.py](/E:/aitools/shapeyourphoto/cloud_state.py), [integrity_guard.py](/E:/aitools/shapeyourphoto/integrity_guard.py): signed update/cloud-message client and local integrity state.
- [ui/cloud_actions.py](/E:/aitools/shapeyourphoto/ui/cloud_actions.py), [ui/cloud_dialogs.py](/E:/aitools/shapeyourphoto/ui/cloud_dialogs.py): update/message UI flows.
- [updater.py](/E:/aitools/shapeyourphoto/updater.py): independent updater.
