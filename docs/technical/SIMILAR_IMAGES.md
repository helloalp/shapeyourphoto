# Similar Images

## 定位

相似图片检测是批量分析后的附加复核能力，用于帮助用户发现近重复、连拍或同场景同主体图片。它不是单张图片质量问题，也不是 cleanup candidate。

## 数据结构

`SimilarImageGroup` 位于 [src/models.py](/E:/aitools/shapeyourphoto/src/models.py)，包含：

- `group_id`
- `paths`
- `similarity`
- `level`
- `reason`
- `evidence`
- `possible_burst`

该结构只保存在批次结果中，不写回单张 `AnalysisResult`。

## 检测模块

[src/similar_detector.py](/E:/aitools/shapeyourphoto/src/similar_detector.py) 使用轻量特征：

- 缩略图颜色/亮度摘要。
- aHash / dHash。
- 低分辨率灰度结构向量。
- 尺寸比例。
- 文件编号连续性。
- 可靠 EXIF 或文件时间辅助。
- JPEG `draft()` 降低特征提取解码成本。

检测阶段耗时写入 `perf_timings`，包括 feature extract、pair build、pair compare、group build 和 total similar detection。

## UI 复核

[src/similar_review_dialog.py](/E:/aitools/shapeyourphoto/src/similar_review_dialog.py) 包含两个窗口：

- 相似组列表：滚动、筛选、多选和开始抉择。
- 组内对比：逐组处理，2-4 张网格，5 张以上分页。

图片区可滚动，底部全局按钮固定；每张图的“删除此图”按钮必须可达。

## 删除规则

- 删除前必须二次确认。
- 删除调用主应用回调，再走 `safe_cleanup_paths()`。
- 优先回收站，失败时进入 `_cleanup_candidates`。
- 删除后刷新相似组、主列表、cleanup 面板和文件存在状态。
- 未删除图片的分析结果、修复建议和扫描摘要不变。

## 禁止事项

- 不把相似组写入 `AnalysisResult.issues`。
- 不因为相似而自动标记 cleanup candidate。
- 不在相似窗口里直接永久删除。
- 不让相似图弹窗阻塞 cleanup candidate 复核；两个提示需要按顺序出现。
