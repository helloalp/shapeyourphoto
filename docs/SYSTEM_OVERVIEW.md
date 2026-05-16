# System Overview

## 项目定位

ShapeYourPhoto 是一个本地图片质量分析、修复与清理工具，面向 Windows 桌面使用。项目优先保证：

- 双击快速启动。
- 图片本地处理，不上传用户数据。
- 主列表工作流稳定可理解。
- 分析、修复、清理和相似图复核都有明确解释。
- 后续维护能在不破坏用户数据规则的前提下小步演进。

## 系统边界

- 当前没有独立单图窗口主路径；单张图片通过主列表导入、分析和修复。
- 当前没有孤立"去噪当前"主入口；降噪由分析结果、repair planner 和 repair engine 统一决策。
- 不适合保留候选（cleanup candidate）默认不删除、不修复；删除必须用户复核并走安全清理。
- 相似图片只作为批次附加结果，不进入单张质量问题、不改变修复建议。
- GPU 只做可选后端检测和 CPU 回退提示，不改变启动依赖。

## 主流程

1. `start.bat` 查找 Python，并调用 `tools/launcher/start_helper.py` 检查运行依赖、按需安装依赖和启动 GUI。
2. `app.py` 创建 Tk 根窗口，挂载 `PhotoAnalyzerApp`。
3. 用户选择图片、目录或拖入路径，`src/ui_app.py` 将图片加入主列表。
4. 目录扫描走 `src/file_actions.py`，遵守默认扫描模式和忽略前缀，结果写入扫描摘要。
5. 批量分析由 `src/ui_app.py` 分配后台 worker，单张分析通过 `src/analyzer.py` 进入 `src/analysis/core.py`。
6. `AnalysisResult` 写回主列表、右侧 HUD、指标、诊断说明、不适合保留候选面板和 Console。
7. 批次分析完成后，`similar_detector.py` 可生成批次级 `SimilarImageGroup`。
8. 修复准备由 `repair_dialog.py` 收集选择，`repair_planner.py` 按单图生成 `RepairPlan`，`repair_engine.py` 执行、评分、回退和保存。
9. 修复详情由 `repair_completion_dialog.py` 展示；统计由 `stats_store.py` 持久化。

## 关键数据结构

- `Issue`：单个质量问题。
- `AnalysisResult`：单张图片分析结果，包含问题、指标、人像字段、场景字段、不适合保留候选（cleanup_candidates）、`perf_timings` 和 `perf_notes`。
- `CleanupCandidate`：不适合保留候选原因，供 UI 复核和安全清理使用。
- `SimilarImageGroup`：批次级相似组，不属于单张分析结果。
- `RepairPlan`：单图修复方法、强度和策略。
- `RepairRecord`：修复结果、输出路径、跳过原因、outcome 分类和修复耗时。

## 高敏感链路

- 启动链路：只允许轻量环境检查和按需安装运行依赖，不得运行 benchmark、扫描或更新包下载。
- Tk 主线程：后台线程不得直接写 Treeview、Text、Label、Progressbar。
- 取消分析：后台任务写回前必须校验 run_id 和 cancel_event。
- EXIF Orientation：读取时像素转正，输出时 Orientation 归一，避免双重旋转。
- 安全清理：优先回收站，失败才进入 `_cleanup_candidates`，不得永久删除。
- 设置持久化：`app_settings.json` 缺失自动创建，损坏备份并回退默认值。
- 性能计时：统一写入 `perf_timings` / `perf_notes`，Console 合并刷新。

## 技术专题

- [分析流水线](/E:/aitools/shapeyourphoto/docs/technical/ANALYSIS_PIPELINE.md)
- [性能与并发](/E:/aitools/shapeyourphoto/docs/technical/PERFORMANCE_AND_CONCURRENCY.md)
- [相似图片](/E:/aitools/shapeyourphoto/docs/technical/SIMILAR_IMAGES.md)
- [不适合保留候选](/E:/aitools/shapeyourphoto/docs/technical/CLEANUP_CANDIDATES.md)
- [设置与扫描](/E:/aitools/shapeyourphoto/docs/technical/SETTINGS_AND_SCAN.md)
