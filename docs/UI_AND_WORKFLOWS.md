# UI And Workflows

## 主界面结构

- 顶部：应用标题、长路径栏、主要操作按钮、筛选和最近扫描摘要入口；不再保留长期占位的主界面任务进度栏。
- 左侧：主图片列表、缩略图、勾选状态、列表标题统计、cleanup candidate 面板。
- 右侧上方：HUD 和问题强度条图，是分析结果仪表盘的第一优先级。
- 右侧下方：诊断说明、属性 / EXIF 和只读 Console；属性页可在支持格式上进入安全文本字段编辑。

当前主界面围绕主列表工作流运行。单张图片导入后也进入主列表，不存在独立单图窗口主路径。

## UI 代码边界

- `ui_app.py` 保留主窗口装配、实例状态和菜单/布局 wiring。
- `ui_scan_actions.py` 承接导入、拖拽和目录扫描。
- `ui_analysis_actions.py` 承接批量分析、取消和结果写回。
- `ui_repair_actions.py` 承接修复入口、修复 worker 和完成详情。
- `ui_file_list.py` 承接主列表、cleanup 列表、选择状态、HUD 和属性/诊断展示。
- `ui_task_console.py` 承接 UI 队列、任务进度、Console 合并刷新和性能摘要。
- `ui_review_actions.py` 承接 cleanup candidate 与相似组复核入口。
- `ui/` 包承接窗口标题、显示名映射、主题、HiDPI、Splash 和 EXIF 安全编辑等新 UI 基础能力。

新增 UI 逻辑时先放入对应边界；只有根窗口生命周期和控件装配继续留在 `ui_app.py`。

## 导入与扫描

### 图片导入

- “选择图片”可导入单张或多张图片。
- Windows 拖拽可导入图片或目录。
- 新导入图片默认进入主列表并可被勾选分析。

### 目录扫描

- 目录扫描入口来自“选择目录”、拖入文件夹和需要补扫的批量流程。
- 如果目录包含子目录，按设置决定是否询问；询问时显示四选项：扫描全部、只扫当前目录、只扫所有子目录、取消。
- 扫描必须遵守忽略目录前缀，默认至少包含 `_repair`，因此任意层级 `_repair*` 目录都会跳过。
- 扫描完成后 Console 输出摘要；完整跳过明细进入“最近扫描摘要”窗口。
- 扫描和扫描后的图片加载阶段都必须显示进度弹窗。Console 不刷完整跳过目录明细，避免大目录刷屏。

## 分析流程

1. UI 收集目标路径。
2. 创建新的 analysis run_id 和 cancel_event。
3. 根据 `resolve_analysis_worker_plan()` 决定 worker 数。
4. 后台 worker 调用 `analyze_image()`。
5. 单张结果写回前校验 run_id 和 cancel_event。
6. UI 主线程定点更新 Treeview 行、HUD、诊断区、cleanup 面板和 Console。
7. 批次完成后统一刷新排序、cleanup 标记和相似组标记。
8. 相似图检测作为批次附加流程运行，完成后只提示相似组。

取消规则：

- 点击“取消分析”或关闭进度窗口都走取消。
- 取消后保留文件列表，清空本轮目标已写入的结果、错误、进度、cleanup 标记和相似组标记。
- 后台 worker 可以自然结束 CPU 工作，但旧回调不得写回 UI。

## 修复流程

1. 用户点击“修复当前”或“批量修复勾选”。
2. `repair_dialog.py` 收集自动/手动方法、输出策略和 cleanup candidate 强制尝试开关。
3. 创建新的 repair run_id、cancel_event 和修复前分析状态快照。
4. 每张图由 `repair_planner.py` 生成独立 `RepairPlan`。
5. `repair_engine.py` 执行候选、评分、安全检查、回退/no-op、保存和元数据保留。
6. `repair_completion_dialog.py` 显示可筛选详情。
7. 成功修复的图片会取消勾选，统计同步更新。

降噪属于统一修复链的一部分，不能恢复成孤立旧按钮。

取消规则：

- 点击“取消修复”或关闭修复进度窗口都走同一套取消流程。
- 取消后回到分析完成、修复前状态；已有 `AnalysisResult`、issues、repair recommendations、method_ids、op_strengths、cleanup/similar 状态不因取消修复而清空。
- 修复中补分析得到的临时结果会按修复前快照恢复；已取消批次不得进入修复完成详情、统计或调试打开列表。
- 已写出的非覆盖输出优先删除；删除失败时移入 `_repair_canceled_outputs` 隔离目录并在 Console/弹窗说明。
- 覆盖原文件修复会在开始前创建 `_repair_cancel_backups` 回滚备份；取消时从备份恢复，正常完成后清理备份。
- 后台 worker 在进度、结果和最终摘要写回前必须校验 repair run_id 和 cancel_event。

批量目标集合规则：

- “修复当前”只使用当前蓝色高亮/当前焦点图片。
- “批量修复勾选”只有在主列表存在真正多选行（多于 1 张）时优先使用多选集合。
- 如果没有真正多选行，则使用主列表“处理状态”勾选集合；单个蓝色高亮行不会遮住勾选集合。
- 批量目标进入修复后，每张图都使用自己的 `AnalysisResult`、`repair_policy`、`method_ids`、`op_strengths`、候选评分和 no-op/回退判断。
- 批量修复准备窗口在多图时显示批量说明与方法汇总，不把当前焦点图的推荐方法描述成整批方案。

## cleanup candidate 工作流

- 分析阶段生成 `CleanupCandidate`，UI 只展示和复核。
- 候选默认不勾选。
- 清理前必须二次确认。
- 清理必须走 `safe_cleanup_paths()`：优先回收站，失败时移入 `_cleanup_candidates`。
- cleanup candidate 默认不进入修复；修复弹窗显式开启强制尝试后才允许进入修复链。

## 相似图片工作流

- 相似组在批次分析完成后生成，是批次级附加结果。
- 相似组列表支持筛选、多选和开始抉择。
- 组内对比窗口中每张图显示预览、文件名、风险、场景、人像、问题、修复建议和 cleanup 标记。
- 删除相似图也必须二次确认并走安全清理。
- 删除后刷新相似组、主列表、cleanup 面板和文件存在状态，不改写未删除图片的分析结论。

## Console 与性能摘要

- Console 是只读状态区，不提供命令输入。
- Console 时间戳可在设置中切换为 24 小时制、12 小时制或启动后经过时间；只影响新日志。
- 后台线程可以排队日志，但 Text 控件刷新由 UI 主线程合并执行。
- 分析和修复阶段耗时来自 `perf_timings` / `perf_notes`。
- Console 面向用户展示 `total_wall_time`、`worker_cumulative_time`、`average_wall_time_per_image`、`average_worker_time_per_image`、queue/wait、最慢图片、最慢阶段、相似检测、UI 刷新和 Console flush 等摘要。
- 面向用户的“本轮修复总耗时”必须是 `total_wall_time`，也就是用户真实等待时间；`worker_cumulative_time` 只能标注为并发 worker 累计耗时，不是用户等待时间。
- 内部阈值、评分公式和过细算法细节不应塞进 Console。

## 当前体验要求

- 弹窗底部关键按钮必须可见。
- 扫描范围窗口和相似图窗口需要受屏幕高度限制，内容区可滚动。
- 修复完成详情使用可筛选滚动窗口。
- 普通 `messagebox` 只适合短提示、确认和错误，不适合承载批量长详情。
- 右侧不恢复旧式大图查看器；主工作流以列表、HUD、指标和诊断说明为核心。
- UI 展示名通过 display mapping 中文化；内部 code/enum/storage 保持英文。
- 主界面“读取目录”和“导出清理清单”入口已移除。目录读取由“选择目录”、拖入目录和分析前补扫描触发；清理仍通过 cleanup candidate 安全复核流程执行。

进度窗口规则：

- 分析和修复进度弹窗分为标题、说明、进度条、计数/耗时、固定高度当前阶段摘要和底部按钮区。
- 当前阶段摘要不得塞入 Console 级长详情；长文本应压缩、省略或进入 Console。
- 每个进度窗口只保留一个明确取消按钮；按钮区固定在底部，进度条和取消按钮始终可见、可点击，关闭叉号与该按钮走同一取消路径。
- 进度更新仍必须通过 UI 主线程调度。

主要弹窗最小尺寸规则：

- 分析/修复进度、扫描四选项、修复完成详情、cleanup candidate、相似图列表、相似图组内对比和设置窗口都必须设置合理最小尺寸。
- 可调整大小的窗口压到最小尺寸附近时，使用统一提示“已达到最小可用窗口大小”。
- 不适合继续缩小的窗口应固定尺寸或只允许内容区滚动，不能让底部关键按钮被遮挡。
