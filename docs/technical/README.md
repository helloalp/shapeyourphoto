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

## 关联主文档

- [系统总览](/E:/aitools/shapeyourphoto/docs/SYSTEM_OVERVIEW.md)
- [模块参考](/E:/aitools/shapeyourphoto/docs/MODULE_REFERENCE.md)
- [UI 与流程](/E:/aitools/shapeyourphoto/docs/UI_AND_WORKFLOWS.md)
- [维护指南](/E:/aitools/shapeyourphoto/docs/MAINTENANCE_GUIDE.md)
- [保留规则](/E:/aitools/shapeyourphoto/docs/PRESERVATION_RULES.md)
- [产品与界面规范](/E:/aitools/shapeyourphoto/docs/specs/README.md)

## 维护规则

- 新增跨模块能力时，优先补专题文档，而不是只改根 README。
- 旧版本行为可在更新文档中保留；专题文档描述当前 1.1.7 维护口径。
- 如果专题文档和旧 `docs/updates/` 冲突，以当前专题文档和代码为准。
- benchmark 自动报告写入被忽略的 `benchmark_reports/`，本地 manifest 使用 `test/manifest.json`，二者都不应提交；可提交的模板是 `test/manifest.example.json`。
