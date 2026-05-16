# Technical Docs

`docs/technical/` 存放跨模块技术专题。这里不替代代码，但要记录维护者最容易误解的链路和约束。

## 当前专题

- [ANALYSIS_PIPELINE.md](/E:/aitools/shapeyourphoto/docs/technical/ANALYSIS_PIPELINE.md)：分析流水线、`AnalysisResult` 字段、run_id/cancel_event 写回边界。
- [PORTRAIT_AWARE_ANALYSIS.md](/E:/aitools/shapeyourphoto/docs/technical/PORTRAIT_AWARE_ANALYSIS.md)：人像候选、真实人脸验证和 portrait policy。
- [PERFORMANCE_AND_CONCURRENCY.md](/E:/aitools/shapeyourphoto/docs/technical/PERFORMANCE_AND_CONCURRENCY.md)：worker 规划、Tk 主线程、Console 合并刷新、GPU fallback。
- [PERFORMANCE_BENCHMARKS.md](/E:/aitools/shapeyourphoto/docs/technical/PERFORMANCE_BENCHMARKS.md)：`test/` 本地真实图片 benchmark 和 1.1.5 基线。
- [UI_MAIN_CLASS_SPLIT.md](/E:/aitools/shapeyourphoto/docs/technical/UI_MAIN_CLASS_SPLIT.md)：`PhotoAnalyzerApp` 拆分边界、UI mixin 职责和维护规则。
- [SIMILAR_IMAGES.md](/E:/aitools/shapeyourphoto/docs/technical/SIMILAR_IMAGES.md)：相似图批次结果、复核窗口和安全删除。
- [CLEANUP_CANDIDATES.md](/E:/aitools/shapeyourphoto/docs/technical/CLEANUP_CANDIDATES.md)：不适合保留候选、强制修复和安全清理。
- [SETTINGS_AND_SCAN.md](/E:/aitools/shapeyourphoto/docs/technical/SETTINGS_AND_SCAN.md)：应用设置、目录扫描模式、忽略前缀和扫描摘要。
- [UI_SETTINGS_DATA.md](/E:/aitools/shapeyourphoto/docs/technical/UI_SETTINGS_DATA.md)：UI 包、Console 设置、外观主题、DPAPI 统计、EXIF 安全编辑和用户数据边界。
- [UPDATES_AND_CLOUD.md](/E:/aitools/shapeyourphoto/docs/technical/UPDATES_AND_CLOUD.md)：签名更新检查、云端公告和 updater 客户端安全边界。

## 关联主文档

- [系统总览](/E:/aitools/shapeyourphoto/docs/SYSTEM_OVERVIEW.md)
- [模块参考](/E:/aitools/shapeyourphoto/docs/MODULE_REFERENCE.md)
- [UI 与流程](/E:/aitools/shapeyourphoto/docs/UI_AND_WORKFLOWS.md)
- [维护指南](/E:/aitools/shapeyourphoto/docs/MAINTENANCE_GUIDE.md)
- [保留规则](/E:/aitools/shapeyourphoto/docs/PRESERVATION_RULES.md)
- [产品与界面规范](/E:/aitools/shapeyourphoto/docs/specs/README.md)

## 维护规则

- 新增跨模块能力时，优先补专题文档，而不是只改根 README。
- 旧版本行为可在更新文档中保留；专题文档描述当前 1.2.6 维护口径。
- 如果专题文档和旧 `docs/updates/` 冲突，以当前专题文档和代码为准。
- benchmark 自动报告写入被忽略的 `benchmark_reports/`，本地 manifest 使用 `test/manifest.json`，二者都不应提交；可提交的模板是 `test/manifest.example.json`。

# 1.1.8 Technical Addendum

New technical topics:

- `UPDATES_AND_CLOUD.md` for signed update checks, cloud messages and updater client safety.
- `docs/specs/EXIF_AND_DEVELOPER_MODE.md` for EXIF protection and session-only developer mode boundaries.

# 1.1.9 Technical Addendum

- Update and cloud-message URLs are fixed internal endpoints and must not be exposed as user-editable settings.
- Console has a timezone timestamp mode.
- Settings UI should show ordinary user descriptions; implementation details belong in technical or private docs.

# 1.2.5 技术文档补充说明

- `src/ui/` 包成为 UI 基础设施核心：包含 `display_names.py`（内部 code/enum 到中文显示名映射）、`themes.py`、`hidpi.py`、`language.py`、`cloud_actions.py`、`cloud_dialogs.py`、`metadata_editor.py`、`splash.py`、`window_titles.py`。
- UI mixin 拆分：扫描（`ui_scan_actions.py`）、分析（`ui_analysis_actions.py`）、修复（`ui_repair_actions.py`）、列表（`ui_file_list.py`）、Console（`ui_task_console.py`）、复核（`ui_review_actions.py`）各自独立，`ui_app.py` 只保留装配和生命周期。
- `updater_v2.py` 是当前 updater 主实现，具备 deferred stager 机制、多次重试下载、取消立即生效、30 秒回滚超时、`moved_paths` 支持和 `post_update_required_files` 校验。
- `cloud_security.py` 验签改为 canonical JSON（sort_keys=True）后再做 Ed25519 签名，与服务端签名脚本保持一致。
- `paths.py` 新增 `user_data_dir()` 跨平台用户数据目录和 `migrate_legacy_file()` 自动迁移。
- 1.2.3/1.2.4 不再通过内置 updater 直升 1.2.5；相关发布使用 `external_download_only` manifest 字段提示手动下载。

# 1.2.6 技术文档补充说明

- 设置页保存后保持打开，主程序通过回调立即保存并应用配置。
- GPU 探测区分硬件与 Python/CUDA 运行后端；可选 GPU 后端依赖不进入默认 `requirements.txt`，仅记录在 `requirements-gpu.txt`。
- 右侧大预览从原图生成，并在 Notebook/布局尺寸稳定后自动重绘，避免首次显示使用过小尺寸；超高清图片按目标显示区域降采样解码，避免重复完整解码。
