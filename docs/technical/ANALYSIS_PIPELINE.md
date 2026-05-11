# Analysis Pipeline

本文说明当前分析流水线和维护边界。

## 入口

- 外部兼容入口：[src/analyzer.py](/E:/aitools/shapeyourphoto/src/analyzer.py)
- 主实现：[src/analysis/core.py](/E:/aitools/shapeyourphoto/src/analysis/core.py)
- 人像专题：[src/analysis/portrait.py](/E:/aitools/shapeyourphoto/src/analysis/portrait.py)
- cleanup candidate：[src/analysis/discard.py](/E:/aitools/shapeyourphoto/src/analysis/discard.py)
- 共享工具：[src/analysis/common.py](/E:/aitools/shapeyourphoto/src/analysis/common.py)

`src/analyzer.py` 不承载新逻辑；新增分析能力应进入 `src/analysis/` 包。

## 单张分析阶段

1. 打开图片并读取基础元数据。
2. 使用 `ImageOps.exif_transpose` 归一像素方向。
3. 转 RGB，并为大图生成 bounded working image。
4. 计算基础统计、曝光、清晰度、色彩、噪声。
5. 执行人像候选、验证和区域构建。
6. 生成场景字段、诊断标签、问题列表和指标条。
7. 从 issue meta 生成 cleanup candidates。
8. 写入 `perf_timings` / `perf_notes`。
9. 返回 `AnalysisResult`。

## AnalysisResult 维护要点

- 单张质量问题进入 `issues`。
- 批次级相似图不进入 `AnalysisResult`。
- cleanup candidates 只承载不适合保留建议，不代表自动删除。
- `perf_timings` 是正式阶段耗时入口。
- `perf_notes` 是轻量瓶颈提示入口。

## working image 规则

大图分析可在缩小后的 working image 上进行重型 numpy/Pillow 统计，但返回尺寸、区域坐标和 UI 展示应回到原图坐标。修改 working image 尺寸或采样规则时，必须用 `test/` 样张验证问题图数量、cleanup candidate 数量和相似组数量是否异常漂移。

## 批量写回规则

批量分析由 `src/ui_app.py` 分配 worker。后台结果写回 UI 前必须确认：

- run_id 仍是当前轮次。
- cancel_event 未设置。
- 目标路径仍属于当前批次。

取消后旧 worker 结果必须丢弃，不能刷新 UI、cleanup prompt、similar prompt 或最终摘要。

## 相似图位置

相似检测在批次单图分析完成后运行。它读取路径和已有 `AnalysisResult`，输出 `SimilarImageGroup` 列表。它不改变单张 `AnalysisResult` 的 issues、scene、portrait、repair 或 cleanup 字段。
