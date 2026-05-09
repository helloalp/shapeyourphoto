# UI Main Class Split

本专题记录 1.1.6 的 `PhotoAnalyzerApp` 拆分边界。目标是结构性降复杂度，不改变用户行为、分析算法、修复风格、扫描规则或安全清理规则。

## 当前边界

- `ui/`：1.1.7 新增 UI 基础设施包。当前承载窗口标题、display mapping、主题 token、HiDPI、Splash 和 EXIF 安全编辑。新增共享 UI 能力优先放入这里。
- `ui_app.py`：主窗口装配、实例状态初始化、菜单 wiring、布局、拖拽安装/卸载和窗口关闭。
- `ui_constants.py`：UI 共享常量、分析/修复耗时标签和 `AnalysisCanceled`。
- `ui_task_console.py`：UI 队列、主线程 drain、Console 合并刷新、任务 begin/finish、worker 规划和性能摘要。
- `ui_scan_actions.py`：选择目录、选择单图、拖拽分流、目录扫描、扫描摘要和扫描完成后的自动分析衔接。
- `ui_analysis_actions.py`：分析入口、run_id/cancel_event、后台 worker、进度阶段、结果写回、取消回滚和相似图检测衔接。
- `ui_repair_actions.py`：修复入口、修复弹窗、修复前补分析、后台修复、完成详情和调试打开前后对比。
- `ui_file_list.py`：主 Treeview、cleanup Treeview、排序、选择/勾选、当前项、HUD、属性摘要和诊断说明。
- `ui_review_actions.py`：cleanup candidate 复核、相似组复核、安全删除回调和删除后状态刷新。

## 维护规则

- 内部字段、枚举、issue code、repair method id 和存储结构继续使用英文；UI 通过 `ui/display_names.py` 做中文化展示，不反向写入逻辑判断。
- 新增主题、Console、EXIF 编辑、Splash、窗口标题等基础 UI 能力优先进入 `ui/` 包；不要把新功能继续堆回 `ui_app.py`。
- mixin 模块不得 import `ui_app.py`，需要共享的常量放入 `ui_constants.py`。
- Tk 控件更新仍必须通过主线程执行；后台 worker 只通过 `_dispatch_ui()` 或既有主线程回调写 UI。
- 分析写回必须继续校验 run_id 和 cancel_event；取消后要清空本轮结果、错误、cleanup 标记和相似组标记。
- cleanup/similar 删除必须继续走 `safe_cleanup_paths()`，不得直接删除文件。
- EXIF/ICC/DPI/XMP 展示与修复元数据保留链路不在本拆分中改变。

## 兼容层

根级 `ui_*` mixin 仍保留为兼容层，避免一次性大搬迁造成循环 import 或窗口打不开。后续迁移应按职责逐步移动到 `ui/mixins/` 或更具体的包内模块，并保持根级薄封装一到两个版本。

布局构建 `_build_ui()` 仍留在 `ui_app.py`，但 1.1.7 已把标题、主题、HiDPI、Splash、显示名和 EXIF 编辑移入 `ui/`。后续可继续拆出主界面布局 builder。
