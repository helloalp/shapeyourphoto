# Performance And Concurrency

## 线程模型

- Tk 控件只能在主线程更新。
- 目录扫描、批量分析、批量修复和相似检测可在后台线程运行。
- 后台线程只提交结果、日志或状态；UI 刷新通过主线程调度。
- 输出路径生成和文件保存要考虑并发冲突，不能绕开现有锁。
- UI 队列每轮只处理有限数量和有限时长的回调，避免进度事件、Console 刷新或列表更新挤占主事件循环。

## worker 规划

分析 worker 数由 `app_settings.resolve_analysis_worker_plan()` 统一决定：

- `auto`：默认保守自动模式。
- `low`：低并发。
- `medium`：平衡模式。
- `high`：激进模式。
- `extreme`：极高模式，按本机 CPU 规模给出更高默认值，但仍受 `max_analysis_workers()` 上限保护。
- `custom`：用户自定义，并受校验上限限制。

Console 和 benchmark 应同时显示 requested workers、actual workers 和限制原因。

设置-性能页必须显示当前模式默认 worker 数和本机允许范围；自定义值不能超过 `max_analysis_workers()`。UI 显示与运行时调度必须都来自 `resolve_analysis_worker_plan()` / `normalize_analysis_custom_workers()`，不得另写一套估算。

## 取消与旧结果防护

批量分析使用 run_id + cancel_event：

- run_id 防止旧轮次结果写回。
- cancel_event 表示本轮已取消。
- 取消后 UI 立即恢复可操作状态，同时清空本轮目标结果。
- 后台 worker 的迟到结果必须丢弃。

批量修复同样使用 repair run_id + cancel_event：

- 取消按钮和窗口关闭叉号走同一取消路径。
- 取消后恢复到分析完成、修复前状态，保留原有分析结果、推荐方法、cleanup/similar 状态和用户选择。
- 已写出的非覆盖输出优先删除，删除失败时移入 `_repair_canceled_outputs`；覆盖原文件修复依赖 `_repair_cancel_backups` 恢复。
- 大文件删除、隔离和覆盖回滚不得在 Tk 主线程执行；取消后 UI 先进入“正在收尾”状态，清理/回滚在后台线程完成，再回主线程恢复按钮、关闭进度窗口和提示警告。
- `repair_image_file()` 在生成计划、读取、处理、保存前检查 cancel_event；取消后不应继续进入后续重计算阶段。
- 已取消批次不得写入完成统计、调试打开列表或修复完成详情。

## Console 合并刷新

Console 文本框不应每条日志都重绘。当前策略是日志进入 `AppConsole` 缓存，UI 用短延迟合并刷新。维护时不得恢复成后台 worker 高频直接写 Text 控件。

Console 时间戳由 `AppConsole` 统一格式化，时间模式来自 `app_settings.py`。分析、修复、扫描等模块不得散落自己的 `strftime()`。目录扫描只输出摘要，完整跳过目录明细进入扫描摘要窗口，避免大批量扫描时 Console 刷屏拖慢主线程。

扫描完成应输出 wall time、访问文件数、导入数量和跳过文件夹数量。导入和扫描后不要整批清空缩略图缓存，除非确实需要让所有缩略图失效。

## 预览与缩略图

- 右侧大图预览不得在 Tk 主线程同步完整解码超高清原图。当前流程只在主线程读取尺寸和更新文字，预览像素解码交给后台线程，完成后通过 UI 队列回主线程创建 `ImageTk.PhotoImage`。
- 预览请求使用 run_id、当前路径和 `(path, target_width, target_height, mtime_ns)` 渲染 key 防护；快速连续点选或布局变化时，旧解码结果必须丢弃，不能刷回当前图片。
- 主列表缩略图缓存使用带 `mtime_ns` 的 LRU。新增缩略图缓存时要限制总量，并在文件修改后淘汰同路径旧 key，避免大文件夹长时间浏览导致内存无限增长或显示旧缩略图。
- 右侧大预览必须继续从原图生成，不得复用列表缩略图；JPEG 解码应继续使用接近目标显示尺寸的 `Image.draft()`。
- 清理复核、相似图片列表和相似图片抉择窗口不得在打开窗口或翻页时同步解码所有缩略图/预览图。窗口应先渲染可操作控件和文字，再由后台 worker 解码 PIL 图像，最后回主线程创建 `ImageTk.PhotoImage`。
- 后台缩略图 worker 不得调用 Tk API，也不得持有无界增长的旧结果。筛选、翻页或关闭窗口时必须使用 generation/stop event 丢弃过期结果。
- 所有 `_drain_*_queue()` 末尾重新安排 `after()` 前都要处理窗口已销毁的 `tk.TclError`，避免关闭阶段回调撞到已销毁 Tcl 对象。

## 高频进度与持久化

- 扫描、分析、修复、转换等按项循环不得把每个文件的进度无节制投递到 UI 队列。后台线程应先按时间或批次节流，再提交主线程更新。
- 更新器、转换器和设置页等独立窗口的后台 worker 不得直接调用 Tk API 或 `after()`。需要弹窗、关闭窗口、改变按钮状态或安排延迟关闭时，必须先投递到主线程 UI 队列。
- 统计持久化属于批次收尾动作。除取消、完成、设置保存等明确边界外，不得在每张图片完成后同步加密并写盘。
- 文件夹扫描在 `os.walk()` 的 `filenames` 列表中已经拿到文件名，不得再对每个文件做重复 `Path.is_file()` stat 检查。
- benchmark 中的排队等待、worker 累计耗时和 wall time 必须分列显示；不能把累计 queue/wait 当作单张图片真实等待。

## 修复目标与补分析

- 修复入口的目标校验只应剔除不在当前列表内或文件已不存在的图片。缺少分析结果的有效图片应进入修复前补分析阶段，不能在打开修复对话框前被提前丢弃。
- 修复对话框的推荐方法只能基于已有分析结果汇总；未分析目标必须通过 `analyzed_count/target_count` 继续暴露给用户，并由修复 worker 在执行前补齐。

## perf_timings / perf_notes

- 阶段耗时统一用 `perf_timings`，单位为毫秒。
- `perf_notes` 写用户/维护者可读瓶颈提示。
- 分析和修复的慢阶段应在批量摘要中聚合为 top slow steps。
- Console 以 `total_wall_time` 为主，表示用户真实等待时间。
- `worker_cumulative_time` 只作为并发诊断，表示并发 worker 单图耗时累计，不是用户等待时间。
- 同时显示平均值时使用 `average_wall_time_per_image` 与 `average_worker_time_per_image`，不得用每图耗时相加冒充总 wall time。

## GPU fallback

[src/gpu_accel.py](/E:/aitools/shapeyourphoto/src/gpu_accel.py) 当前只检测可选后端并返回状态文案：

- 硬件可见性
- 加速组件准备情况
- 当前任务使用状态

GPU 状态分为硬件存在、可用运行后端和当前任务是否使用三层。硬件可通过 `nvidia-smi` 或 Windows 显卡控制器信息识别；后端检测必须有超时并允许后台执行。无论 GPU 设置为关闭、自动或开启，缺少后端时都必须安全回退 CPU。除非未来有 `/test` 真实样张证明数据搬运收益，否则不要声称默认 GPU offload 已启用。

GPU 检测使用共享总耗时预算，不能让不同加速组件分别等待完整超时时间后线性累加。硬件可见但加速组件未准备时属于运行环境能力未就绪，不是硬件检测失败；日常运行继续使用 CPU。

## Rust 化判断

Python 热点可以迁入 Rust，但必须满足以下条件：

- 有 benchmark 或运行日志证明 Python 路径是瓶颈、稳定性风险或打包缺陷来源。
- Rust 路径能保留现有用户能力，并在失败时安全回退或给出清晰诊断。
- 迁移后继续接入现有 `perf_timings`、Console 摘要和 benchmark 报告。
- 原生组件版本必须跟随应用版本更新，并纳入 release 构建检查。

详细路线见 [RUST_NATIVE_ROADMAP.md](/E:/aitools/shapeyourphoto/docs/technical/RUST_NATIVE_ROADMAP.md)。
