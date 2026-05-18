# Maintenance Guide

本文是 1.2.6 当前维护规则。旧版本附录保留在 `docs/updates/`；如旧说明与本文冲突，以本文和当前代码为准。

## 基本原则

1. 先核代码，再改文档或实现。
2. 小步修改、可验证，不借维护任务重构核心算法。
3. 保留用户数据安全边界：不上传图片、不永久删除、不暗改输出规则。
4. 功能变化必须同步文档、CHANGELOG 和 `src/app_metadata.py`。
5. 不提交本地样张、缓存、patch、`__pycache__`、调试输出或临时文件。
6. 不得写入限制产品未来发展方向、适用人群、使用场景、AI 能力接入或专业化功能扩展的表述；任何文档修改、增删、更新、升级都只能描述当前实现事实、当前实现约束和当前安全要求，不能把阶段性功能状态写成长期产品边界。
7. 更新历史、根 README 和应用内版本记录不得暴露开发者设备型号、私有测试环境、内部依赖栈、AI 协作过程、提示词或适用对象标签；版本记录只写用户能感知的功能结果和安全结果。

## 启动链路保护

- 日常启动入口是根目录 `start.bat`。
- `start.bat` 保持 ASCII-only 和短逻辑：只查找 Python，并进入 `tools/launcher/start_helper.py`。
- `tools/launcher/start_helper.py` 可以做轻量环境检查和按需依赖安装；依赖齐全时必须快速进入 GUI。
- 不得把 benchmark、目录扫描、清理、更新包下载或其他与启动无关的重任务放入启动链路。
- `tools/legacy/setup_deps.bat` / `tools/legacy/start_app.bat` 只作为兼容入口，用户文档不得要求先运行它们。
- 源码包在无 Python 设备上不能直接运行；`start.bat` 必须保留可读提示窗口，不能闪退。

## Tk 主线程规则

- Tk 控件只能在主线程更新。
- 后台线程不得直接写 Treeview、Text、Label、Progressbar 或弹窗。
- 目录扫描、批量分析、批量修复和相似检测应通过回调/队列/`root.after()` 回主线程。
- Console Text 刷新必须保持合并刷新，避免每条日志重绘整块内容。
- 分析/修复进度窗口只显示固定高度阶段摘要；长阶段详情和性能细节进入 Console，不得撑开弹窗内部布局。
- 进度窗口只允许一个明确取消入口，关闭叉号与按钮应走同一取消路径。

## UI 主类拆分规则

- `src/ui_app.py` 只负责主窗口状态、控件装配和高层协调。
- 扫描/导入、分析任务、修复任务、主列表、Console/perf、不适合保留候选/相似组复核分别维护在 `src/ui_scan_actions.py`、`src/ui_analysis_actions.py`、`src/ui_repair_actions.py`、`src/ui_file_list.py`、`src/ui_task_console.py`、`src/ui_review_actions.py`。
- `src/ui/` 包承载窗口标题、display mapping、主题、HiDPI、Splash 和 EXIF 安全编辑等共享 UI 基础设施。
- 新增 UI 行为时优先放入对应 mixin 或 `src/ui/` 包；只有布局装配、菜单 wiring 和根窗口生命周期适合留在 `src/ui_app.py`。
- mixin 模块不得 import `ui_app.py`，共享常量放在 `ui_constants.py`，避免循环依赖。
- 拆分 UI 代码时必须保持后台回调回主线程、run_id/cancel_event 防旧写回和 Console 合并刷新规则。

## 后台线程、run_id 与取消规则

- 每轮批量分析都应有唯一 run_id。
- 取消分析通过 cancel_event 表达。
- 后台任务写回结果、进度、不适合保留提示、相似图提示或最终摘要前必须校验 run_id 和 cancel_event。
- 取消后保留文件列表，清空本轮目标已写入的结果、错误、进度、不适合保留标记和相似组标记。
- 已取消 worker 可以完成 CPU 工作，但结果必须丢弃。
- 每轮批量修复也应有唯一 run_id 和 cancel_event。
- 取消修复不得清空修复前已经存在的分析结果、错误、不适合保留/相似图状态或修复建议；如修复流程补分析了缺失图片，取消时必须按修复前快照恢复。
- 修复取消后不得保留已取消批次的完成统计、调试打开列表或修复完成详情。
- 已写出的非覆盖修复输出必须删除；删除失败时移入 `_repair_canceled_outputs` 隔离目录并提示。
- 覆盖原文件修复需要先创建 `_repair_cancel_backups` 备份，取消时恢复备份，正常完成后清理备份。

## perf_timings / perf_notes 规则

- 分析和修复耗时统一写入 `perf_timings`。
- 面向维护者的轻量瓶颈提示写入 `perf_notes`。
- 不要新建平行计时体系。
- 分析建议记录读取、EXIF 转正、working image、基础统计、曝光、锐度、色彩、噪声、人像、不适合保留候选、相似图检测等阶段。
- 修复建议记录 planner、读取、各 op、候选生成/评分、安全检查、保存输出和元数据保留。
- Console 以 `total_wall_time` 为主；`worker_cumulative_time` 是并发 worker 累计工作量，不是用户等待时间。
- 如果同时显示平均耗时，必须区分 `average_wall_time_per_image` 和 `average_worker_time_per_image`。
- 不得把每张图耗时相加后作为面向用户的"本轮总耗时"。

## EXIF Orientation 归一

- 读取图片时使用 `ImageOps.exif_transpose` 将像素方向转正。
- 保存 JPEG/WebP 前将 EXIF Orientation 归一为 `1`。
- 回归时检查原图显示方向、输出物理尺寸和输出 Orientation。

## 不适合保留候选安全删除规则

- 不适合保留候选是建议，不是自动删除命令。
- UI 默认不勾选候选。
- 删除前必须二次确认。
- 删除必须走 `safe_cleanup_paths()`。
- 优先移入系统回收站；失败时移入项目内 `_cleanup_candidates` 隔离目录。
- 不得在不适合保留或相似图复核窗口中直接 `unlink()` 或永久删除。

## 修复目标集合规则

- "修复当前"只读取当前焦点图片。
- "批量修复勾选"优先使用真正的 Treeview 多选集合；只有当多选数量多于 1 张时才视为批量多选。
- 没有真正多选时，批量入口回退到勾选集合；单个蓝色高亮行不得覆盖勾选集合。
- 批量修复必须逐图调用 `repair_engine.repair_image_file()`，并让 `repair_planner.build_repair_plan()` 基于该图自己的 `AnalysisResult` 生成 `method_ids`、`op_strengths` 和 policy notes。
- 不得把当前焦点图的推荐方法、参数或力度套用到整批图片。
- 修复完成详情的成功、跳过、失败、候选回退/no-op 统计必须来自真实批量目标结果。

## 弹窗尺寸规则

- 分析/修复进度、扫描四选项、修复完成详情、不适合保留候选、相似图列表、相似图组内对比和设置窗口都应有明确 `minsize()` 或固定/滚动策略。
- 底部关键按钮应放在固定按钮区，内容过长时滚动内容区，不压缩按钮区。
- 进度窗口的底部提示与取消按钮必须使用独立布局单元，不能互相覆盖；关闭叉号必须等同取消或明确禁用，但取消按钮必须可达。
- 可缩放窗口达到最小尺寸附近时，统一显示"已达到最小可用窗口大小"。
- 二级窗口默认尺寸必须受屏幕可用区域限制，不能为了展示完整内容超出屏幕。

## 相似图维护规则

- 相似图只作为分析批次附加结果。
- `SimilarImageGroup` 不写回单张 `AnalysisResult.issues`、`scene_type`、人像字段、修复建议或不适合保留候选。
- 同一张图可以同时出现在不适合保留候选和 similar group 中；UI 只能提示，不自动处理。
- 相似图删除复用全局安全清理。

## 设置与扫描规则

- 应用设置统一由 `app_settings.py` 定义、校验和保存。
- UI 设置统一由 `settings_dialog.py` 管理，不新增零散菜单项。
- Console 时间模式和外观主题也属于 app_settings schema，不能在 UI 内私有保存。
- 扫描默认至少忽略 `_repair` 前缀，任意层级以 `_repair` 开头的目录都跳过。
- 扫描结果应写入 Console 简报和"最近扫描摘要"明细；完整跳过目录明细不得刷屏到 Console。
- 扫描和扫描后的图片加载阶段都必须显示进度弹窗；无法预知总数时显示已处理数量，不造假进度。
- 修改扫描逻辑时同时验证按钮扫描、拖拽文件夹、补扫、默认扫描模式和忽略前缀。

## 用户数据与统计规则

- 用户数据写入被忽略的 `data/` 目录。
- 统计只保存聚合数据，不保存完整图片路径。
- Windows 使用用户级 DPAPI 保护 `data/usage_stats.dpapi`；不可用时不得用 base64 或简单编码冒充加密。
- 旧 `usage_stats.json` 迁移时先写入新 store，成功后保留 migrated 备份或标记，不直接删除。

## UI 显示名规则

- 内部英文 code/enum/storage 保持不变。
- UI 通过 `ui/display_names.py` 显示中文或中英结合名称，不把中文名写回业务判断。
- 未知值必须显示为带 raw value 的兜底文案，不能异常中断 UI。

## HiDPI 与 EXIF 编辑规则

- Windows GUI 启动前启用 DPI awareness，Tk scaling 与系统字体按 DPI 配置。
- 手工验收 100% / 125% / 150% / 200% 缩放下主窗口、设置、进度、修复详情和 Console 字体清晰度。
- ClearType、显卡驱动和远程桌面缩放不完全受应用控制，文档需说明边界。
- EXIF 编辑默认只读，保存前备份；只允许标题/描述、作者、版权、关键词/备注等安全文本字段。
- 禁止修改相机/镜头、拍摄时间、Orientation、ICC 和内部标记。

## GPU fallback 规则

- GPU 是可选加速能力，不是硬依赖。
- 普通用户主路径必须使用随包分发的 native GPU backend，不得要求用户自行安装 CUDA、torch、CuPy 或 OpenCV CUDA 才能启用 GPU。
- native backend 缺失、设备不可用、超时或任务规模不划算时，应用必须正常启动并回退 CPU。
- 只有 benchmark 证明真实收益的任务才能默认使用 GPU；当前大图分析亮度统计可走 Rust/wgpu 后端，小图、修复候选评分和相似图缩略特征继续按性能门控回 CPU。

## `/test` 本地样张规则

- `test/` 用于本地真实图片 benchmark 和回归。
- 图片文件由 `.gitignore` 忽略，不得提交。
- 真实 `test/manifest.json` 也默认忽略，因为可能包含用户图片文件名。
- 可提交的模板是 `test/manifest.example.json`。
- `tools/benchmark/benchmark_test_images.py` 必须允许 `test/` 为空时安全跳过。
- benchmark 摘要应记录 wall time、worker cumulative、queue/wait、慢图、慢阶段、相似检测、问题图和不适合保留候选数量。
- benchmark 报告写入被忽略的 `benchmark_reports/`，不得提交报告文件。

## 文档更新规则

- 不得删除 `docs/`、`docs/technical/`、`docs/updates/`。
- 不得清空正式文档。
- 过时内容应修订、迁移、标注历史上下文或指向当前说明。
- 新增模块或职责变化：更新 `MODULE_REFERENCE.md`。
- UI 流程变化：更新 `UI_AND_WORKFLOWS.md`。
- 技术链路变化：更新或新增 `docs/technical/` 专题。
- 产品和界面规范变化：更新或新增 `docs/specs/` 专题。
- 版本升级：更新 `CHANGELOG.md`、`src/app_metadata.py` 和 `docs/updates/<version>.md`。

## 版本记录语言规范

- `src/app_metadata.py` 内置 `CHANGELOG` 会在应用内展示，默认必须使用中文书写。
- 根目录 `CHANGELOG.md` 和 `docs/updates/<version>.md` 默认也使用中文书写，并与 `app_metadata.CHANGELOG` 保持同一事实口径。
- 同一个版本号在 `CHANGELOG.md`、`src/app_metadata.py` 的 `CHANGELOG` / `CHANGELOG_I18N` 中只能有一个版本块；版本准备期间的后续补充必须追加到既有版本块的 `items` 后面，不得因为日期、分点数量或阶段不同新开第二个同版本条目。
- 内部模块名、文件名、函数名、字段名、code、enum、storage key、环境变量和协议字段继续保留英文原文，不为了中文化而改写技术标识。
- 如必须引用英文库名、异常名、命令名或协议字段，可直接保留英文；解释性文案仍使用中文。
- 发布前检查 1.1.8 及之后的新增版本记录，不得出现整条英文更新说明混入中文版本历史。

## 推荐验证顺序

1. `python -m compileall -q .`
2. 静态检查 `start.bat` / `tools/launcher/start_helper.py` 未加入 benchmark、扫描、更新包下载或其他启动无关重任务。
3. 搜索旧入口描述：`single_image_window`、孤立"去噪当前"、普通 `messagebox` 长修复详情。
4. 检查文档是否存在明显乱码。
5. 检查 `git status --short`，确认没有本地样张、`__pycache__`、patch、tmp 或 debug 输出进入版本控制。

## 高风险修改点

- `src/ui_app.py` 与 `src/ui_*` mixin：主线程、run_id、取消、列表刷新、Console 合并刷新和弹窗入口。
- `src/analysis/core.py` / `src/analysis/portrait.py`：分析结论与人像误判。
- `repair_ops.py` / `repair_engine.py`：视觉风格、输出安全和元数据。
- `file_actions.py`：扫描忽略、清理安全和输出路径。
- `app_settings.py`：设置兼容、默认值和 worker 规划。
- `similar_detector.py` / `similar_review_dialog.py`：相似图算法与安全删除。

# 1.2.5 维护补充说明

- UI 所有内部名词如 `cleanup candidate`、`no-op` 等面向用户展示时必须通过 `display_names.py` 转为"不适合保留"、"未生成新版本"等中文；上述文档已将描述更新为中文化词汇。
- `start.bat` 已支持按需安装 `requirements.txt` 中的依赖（包括正式依赖 `cryptography`），但依然禁止包含任何其他重型操作。
- 开发者私有文件如部署流程、AI协作提示词等归档于 `private_docs/`，严禁提交到公开仓库或发版包中。
- UI/云端操作相关的网络调用必须放置于后台线程，超时和重试必须不阻塞主界面的重绘和用户操作，关闭窗口时必须能安全切断关联。

# 1.2.6 维护补充说明

- 设置页保存动作应立即应用配置但保留窗口，方便用户连续调整；只有取消或关闭才退出设置页。
- 右侧预览图必须从原图生成，不复用列表缩略图；首次选择图片时需在布局稳定后重绘，避免首屏小图。超高清图片预览应按显示区域降采样解码，后台完成像素解码，并缓存当前路径、尺寸和文件时间戳，避免主线程等待完整解码或重复解码。
- 主列表缩略图缓存必须有容量上限并带文件时间戳；大文件夹浏览不能让 `PhotoImage` 缓存无限增长，原图修改后也不能继续复用旧缩略图。
- 列表、清理复核和相似图复核的缩略图应按目标尺寸解码，不得为了小缩略图完整解码大 JPEG。
- GPU 状态必须区分硬件检测、native 组件是否随包存在、当前任务是否实际使用三层。硬件可见但 native 组件缺失时继续 CPU 回退，并提示重新安装完整版本或获取 GPU 组件包，不得把 Python GPU 依赖作为普通用户主解决方案。
- GPU 后端探测必须使用共享总耗时预算，不能让多个可选库串行累积完整超时。

---
> 下方内容为旧版本的维护规范英文历史记录，供追溯使用。

# 1.1.8 Maintenance Addendum

- Settings additions must be defined in `app_settings.py` and surfaced from `settings_dialog.py`.
- Update and cloud-message UI orchestration lives in `ui/cloud_actions.py` and `ui/cloud_dialogs.py`; do not move protocol logic into `ui_app.py`.
- Developer mode is session-only and backed by `developer_mode.py`; never store an unlocked flag in `app_settings.json`.
- EXIF edits must preserve ShapeYourPhoto provenance fields and block any value containing `shapeyourphoto`.
- Startup scripts must stay fast; 1.2.6 allows only on-demand runtime dependency installation from `requirements.txt`, and still forbids benchmarks, scans or update-package downloads during startup.
- GitHub auto-packaging workflow is paused in 1.1.8; release/server steps live in ignored private docs.

# 1.1.9 Maintenance Addendum

- Production update and cloud-message URLs are fixed internal constants. Do not expose them in Settings, do not persist them in ordinary `app_settings.json`, and do not add user-editable URL fields back.
- Settings pages shown to regular users should use short, understandable descriptions. Keep implementation notes in docs or private docs instead of user-facing labels.
- Theme settings may show theme names only; do not expose concrete color token values in the user settings dialog.
- The main window title format is `Shape Your Photo | v<version> | by Helloalp`.

# 1.2.0 Maintenance Addendum

- `cryptography` 是 updater 验签的正式依赖，必须通过 `requirements.txt`、`tools/launcher/start_helper.py` 和打包配置进入发布流程。
- 1.2.5 起 `start.bat` 可以触发按需依赖安装；但仍不得加入更新下载、benchmark、扫描或其他启动无关重任务。
- 正式包应包含 `assets/update_public_key.pem`；开发测试可用 `SHAPEYOURPHOTO_UPDATE_PUBLIC_KEY_FILE` 覆盖公钥文件。
- `update_private_key.pem` 永远不得进入仓库、源码包、安装包或普通项目目录。
- 文档中的历史版本号可保留上下文；下一次真实 updater 测试流程使用 `1.2.0 -> 1.2.1`。
