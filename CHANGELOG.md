# 更新历史

## 1.1.7 - 2026-05-10

- 融合 main 已合入的外部 PR 与 Codex 修复 PR，并重新叠回 `backup-v1.1.7-before-pr` 的本地 v1.1.7 能力；本轮目标是保留两边有效功能，不回退任一侧。
- 保留跨平台打包链路：macOS Apple Silicon `.dmg`、Windows Inno Setup 安装包、`build/` 配置、`assets/app_icon.icns`、GitHub Actions 双 runner 构建与 Release 发布。
- 保留跨平台拖放：Windows 继续使用原生 `ctypes` 拖放，macOS / Linux 使用 `tkinterdnd2`；根窗口由 `dnd_support.create_root()` 统一选择，路径解析改用 Tcl `splitlist`。
- 保留 Codex 平台检测修复：`paths.IS_WIN` / `IS_MAC` / `IS_LINUX` 集中管理平台判断，`drag_drop.py` 等模块避免非 Windows import-time 崩溃。
- 保留用户数据目录迁移：设置与统计进入系统标准用户数据目录，PyInstaller 资源加载继续使用 `paths.resource_path()`，卸载不会删除用户数据。
- 保留 v1.1.7 修复取消链路：repair run_id/cancel_event、防旧写回、修复前状态快照、取消后恢复、非覆盖输出清理、覆盖修复备份和正常完成后备份清理。
- 保留 Console 设置与主题系统：Console 支持 24 小时制、12 小时制、启动后经过时间；外观保留五套主题 token，设置 schema 为 2。
- 保留 HiDPI 与 Splash：启动阶段配置 DPI awareness、Tk scaling、字体和居中 Splash，同时仍使用跨平台拖放根窗口。
- 保留 UI 结构升级：`ui/` 包承载 display mapping、主题、HiDPI、Splash、窗口标题和 EXIF 编辑；根级 `ui_*` mixin 继续承担主窗口功能拆分。
- 保留主界面布局调整：路径栏扩展、列表统计、HUD/条图权重提升、移除重复顶部任务进度栏，并维持统一扫描范围与扫描摘要流程。
- 保留统计安全存储：Windows 写入用户数据目录下 `usage_stats.dpapi` 并使用用户级 DPAPI；非 Windows 回落到用户数据目录 JSON；旧 `usage_stats.json` 迁移后保留 `.migrated-*` 备份。
- 保留属性 / EXIF 安全编辑：只允许写入标题/描述、作者、版权、关键词/备注，保存前备份，禁止修改相机、镜头、拍摄时间、Orientation、ICC 和内部标记。
- 修复 `drag_drop.py` 融合后的缩进错误，避免 `WindowsFileDropTarget` 在 import 阶段触发 `NameError` 导致 `start_app.bat` 无法打开窗口。
- 同步更新 `app_metadata.py` 内置 CHANGELOG、根 `CHANGELOG.md`、`README.md` 当前版本和 `docs/updates/1.1.7.md`，把 main 修改与本地修改都写入 1.1.7 版本说明。

- 修正修复批次总耗时口径：Console 面向用户的“本轮修复总耗时”改为 `total_wall_time`，即用户真实等待时间，不再把每张图 `repair_total` 相加当总耗时。
- 修复性能审计明确区分 `total_wall_time`、`worker_cumulative_time`、`average_wall_time_per_image` 和 `average_worker_time_per_image`；`worker_cumulative_time` 标注为并发 worker 累计耗时，不是用户等待时间。
- 分析/修复进度窗口底部按钮区改为固定两列布局，尺寸提示与取消按钮不再共用同一单元；窗口初始高度按屏幕高度钳制，避免取消按钮被阶段文本挤走或遮挡。
- 修复进度窗口新增“取消修复”，窗口关闭叉号与按钮走同一取消流程。
- 批量修复新增 repair run_id/cancel_event 防旧写回；取消后恢复修复前分析状态快照，保留原有分析结果、issues、推荐方法、cleanup/similar 状态，不弹正常完成详情、不更新修复统计或调试打开列表。
- 已取消批次写出的非覆盖修复输出会优先删除，删除失败时移入 `_repair_canceled_outputs` 并提示；覆盖原文件修复会先创建 `_repair_cancel_backups`，取消时恢复备份，正常完成后清理备份。
- 设置新增 Console 与外观/风格页：Console 支持 24 小时制、12 小时制和启动后经过时间；外观提供经典清绿、石墨灰、影像蓝、暖白纸和高对比五套 token 风格。
- Windows 启动阶段启用 DPI awareness，按 DPI 配置 Tk scaling、系统字体与 ttk 样式；新增居中 Splash，主窗口准备好后自动关闭。
- 主界面重排为更清晰的仪表盘：移除顶部重复任务进度栏，路径栏扩展为横向长栏，分析统计移到缩略图列表标题区，右侧 HUD/条图获得更高优先级。
- “读取目录”和“导出清理清单”主入口已移除；选择目录、拖入目录和分析前补扫描继续使用统一扫描范围与扫描摘要流程。
- 目录扫描后新增“正在加载图片”阶段提示，扫描进度弹窗显示发现/导入数量、当前路径和 elapsed time；Console 只输出扫描摘要，跳过明细进入扫描摘要窗口。
- 二级窗口标题统一为 `ShapeYourPhoto v.x.x.x - 功能名`，覆盖设置、扫描、修复、cleanup、相似图、统计、历史和进度弹窗等主要窗口。
- 新增 UI display mapping 层，内部英文 code/enum/storage 保持不变，UI 对 issue、scene/portrait/exposure/color、repair method/policy、outcome、worker/GPU/scan/Console 时间模式和 perf stage 做中文化展示，未知值优雅回退。
- 修复完成详情窗口摘要区改成紧凑 chip 信息条，筛选、列表、详情滚动区和底部关闭按钮优先可用。
- “累计统计”调整为“统计”，统计持久化迁移到被忽略的 `data/usage_stats.dpapi`；Windows 使用用户级 DPAPI 加密，旧 `usage_stats.json` 成功迁移后保留 `.migrated-*` 备份，不直接删除。
- 右侧“属性 / EXIF”新增安全编辑入口：默认只读，只允许写入标题/描述、作者、版权、关键词/备注，保存前创建备份，禁止修改相机、镜头、拍摄时间、Orientation、ICC 和内部标记。
- 新增 `ui/` 包承载标题、显示名映射、主题、HiDPI、Splash 和 EXIF 编辑等 UI 基础设施；根级 `ui_*` mixin 继续作为兼容层保留。
- 新增 `docs/specs/` 产品规范目录，并补充技术文档中的 UI 包、设置扩展、用户数据目录、加密边界、主题 token、Console 设置和 EXIF 安全编辑说明。
- 本轮未改变分析算法、修复风格、相似图算法或 cleanup 安全规则。

## 1.1.6 - 2026-05-08

- 重整文档体系：明确根 README、根 MODULES、`docs/`、`docs/technical/` 与 `docs/updates/` 的分工，并给出后续维护阅读顺序。
- 重写核心维护文档：系统总览、模块参考、UI 工作流、维护指南和保留规则均更新为 1.1.6 当前口径。
- 新增技术专题：分析流水线、性能与并发、相似图片、cleanup candidates、设置与扫描。
- 修正旧内容误导：明确独立单图窗口、孤立“去噪当前”入口、普通 messagebox 承载批量长修复详情都不是当前主路径。
- 补齐 1.1.5 后的性能、benchmark、GPU fallback、相似图、cleanup、取消分析、设置、扫描和修复完成详情维护规则。
- 更新 `app_metadata.py` 应用版本与内置版本历史，并新增 `docs/updates/1.1.6.md`。
- 清理临时编译缓存，并修正 `gpu_accel.py` 中仍指向 1.1.5 的过时提示文案；本轮未改变分析算法、修复风格、UI 主交互逻辑或用户数据处理规则。
- 低风险基础建设补充：`benchmark_test_images.py` 运行后会写入忽略目录 `benchmark_reports/`，包含 JSON 与 Markdown 报告、慢阶段/慢图片 top 5、核心计数和与上一份报告的简单对比。
- `app_settings.py` 新增 `settings_schema_version` 与 `migrate_settings()` 入口；旧设置、缺字段、错误类型和未知字段会规范化保存，损坏 JSON 继续备份并回退默认值。
- `test/README.md` 补充本地样张命名和 manifest 标注约定，新增可提交的 `test/manifest.example.json`；真实 `test/manifest.json` 和 benchmark 报告继续不进入 git。
- UI 主类拆分：`ui_app.py` 保留主窗口装配和高层协调，扫描、分析、修复、主列表、Console/perf、cleanup/similar 复核拆入独立 `ui_*` mixin 模块；本轮保持用户行为、算法和修复风格不变。
- 修复“批量修复勾选”目标集合语义：真正多选优先，其次使用勾选集合；单个蓝色高亮行只用于“修复当前”，不再把批量目标错误缩成 1 张。
- 修复准备窗口在多图时显示批量说明和方法汇总，强调逐张生成独立修复计划；批量修复仍按每张图自己的分析结果、policy、方法、力度、候选评分和 no-op/回退决策执行。
- 稳定分析/修复进度弹窗内部布局：固定标题、说明、进度条、计数/耗时、阶段摘要和底部按钮区，长阶段文本压缩显示，避免控件跳动、重叠或出现重复取消入口观感。
- 主要弹窗补齐最小尺寸与统一最小尺寸提示，修复完成详情窗口修正伸缩权重，保证列表/详情滚动且底部按钮可达。

## 1.1.5 - 2026-05-07

- 修复“相似图片组内对比”窗口默认尺寸不足时每张图片下方“删除此图”按钮可能被遮挡的问题；图片区改为独立可滚动区域，底部“跳过本组 / 跳过所有剩余组 / 结束选择”固定在窗口底部。
- 调整组内对比窗口默认尺寸与小窗口提示阈值：常规屏幕默认尽量展示 2/3/4 张的完整卡片，5 张以上继续分页；小屏不超出屏幕，图片区滚动可达。
- 分析阶段补齐 `perf_timings`：读取图片、基础统计、场景判断、人像/清晰度/噪声/色彩判断、cleanup candidate、相似图检测与 UI 刷新耗时会进入 Console 摘要。
- 修复阶段补齐 Console 摘要：生成修复方案、读取图片、执行主要修复步骤、候选评分/安全检查、保存输出、元数据保留和批量 top slow steps。
- 分析结束后新增批次级性能审计：输出 total/wall/worker/average、queue/wait、slowest images top 5、slowest stages top 5、相似检测、UI 刷新与 Console 刷新耗时，并给出轻量瓶颈提示。
- 应用设置新增分析并发模式（自动/低/中/高/自定义 worker 数）和 GPU 加速模式（关闭/自动/开启）；GPU 后端只做可选检测，缺少 CuPy、OpenCV-CUDA、torch CUDA 或设备时自动回退 CPU。
- 批量分析单张完成后改为定点更新 Treeview 行，避免反复重建整张缩略图列表；默认自动分析 worker 上限从 8 提升到 12，同时保留安全并发设置。
- Console 文本框改为合并刷新，降低多线程分析/修复时由日志重绘造成的 Tk 主线程压力；本轮未改变分析算法、相似图判断规则或修复风格。

## 1.1.4 Similar Images Addendum

- 修复相似组复核窗口布局：滚动列表独占可扩展区域，底部按钮固定，卡片按内容自适应高度；筛选增加低置信候选。
- 相似检测增强为多尺度、旋转与裁切鲁棒方案，加入场景/中心主体/边缘摘要、文件编号连续性和可靠时间辅助，可将 `DSC_2621.JPG`、`DSC_2622.JPG`、`DSC_2623.JPG` 归为中等相似复核组。
- 新增相似图片自动检测与复核删除：分析完成后生成批次级 similar groups，列表窗口支持滚动、筛选、多选，组内对比窗口支持网格/分页复核，并通过全局安全删除逻辑移入回收站或 `_cleanup_candidates`。本次仍归入 1.1.4，不提升版本号。

## 1.1.4 - 2026-05-05

- 分析器已模块化为 `analysis/` 包，按核心编排、人像验证、清理候选与公共工具拆分，`analyzer.py` 保留原兼容入口。
- 人像识别升级为 `raw_face_candidates` 与 `validated_face_boxes` 双层结构，可区分真实正面人脸、背身/侧背身、画作/海报中的脸与纹理误检；低置信度候选不再进入 portrait policy、discard candidate 和多人像评分。
- `AnalysisResult` 新增 `scene_type`、`portrait_type`、`exposure_type`、`highlight_recovery_type`、`color_type`、`rejected_face_count` 等字段，并输出更完整的诊断说明与拒绝理由。
- “不适合保留”机制升级为通用 cleanup candidate：本轮接入真实正面人像严重虚焦、严重全图糊片与极端不可恢复曝光问题；支持主菜单再次打开、状态刷新、从候选定位回主缩略图与安全清理。
- 自动修复改为单图单策略、单图单力度：每张图先生成独立 `RepairPlan`，再做候选评分、风险限制、回退与 no-op 决策；同批图片不再共用固定算法链和统一强度。
- 目录扫描新增“忽略目录前缀”设置，默认至少包含 `_repair`；任何以 `_repair` 开头的目录都会在任意层级被整体跳过，避免 `_repair`、`_repair_old`、`_repaired` 等输出目录被递归重新导入。
- 目录扫描新增四种范围选择：扫描全部并包含子目录、只扫描当前目录、只扫描所有子目录、取消扫描；扫描摘要会写入扫描模式、跳过目录数量和导入图片数量，拖拽文件夹入口也统一复用这套规则。
- 修复准备窗口新增“强制修复不值得保留的图片”，默认关闭；开启后允许 cleanup candidate 进入统一 repair planner / repair engine，但修复后仍需通过候选评分、安全检查和可保留性判断，失败时继续回退或跳过保存。
- 去噪已并入统一分析与修复链：分析阶段新增 `noise_score`、`noise_level`、`denoise_profile` 与 `denoise_recommended`，修复阶段根据人像、夜景暗部、纯净天空、建筑纹理等场景采用差异化降噪与细节保护。
- 主界面已移除独立“单图模式”入口和相关窗口代码；单张图片仍通过主列表正常导入、分析和修复。
- 高反差窗景、剪影与低调氛围场景默认不再按普通欠曝强修；不可恢复天空/白墙高光改为保亮度优先，避免统一压灰。
- 色彩修复从更激进的全局饱和度调整改为更保守的 scene-aware vibrance，并增加对天空、肤色、木色、灰墙、白墙和自然高饱和场景的保护与回退。
- 批量分析与批量修复接入受控线程池，目录扫描、分析、修复和日志刷新都避免阻塞 Tk 主线程；输出路径生成增加锁保护，降低并发写入冲突。
- 主缩略图列表与 cleanup 候选列表均支持多选；批量修复完成提示改为可滚动自定义对话框，完整显示跳过、no-op、回退与失败原因。

 - 顶部“设置”菜单已整理为统一“应用设置”面板，集中管理扫描忽略目录前缀、默认扫描模式与修复完成详情默认筛选；`app_settings.json` 缺失时会自动创建，损坏时会备份坏文件并回退默认值。
 - 扫描摘要新增按忽略前缀分组的跳过统计，并提供“最近扫描摘要”滚动明细窗口，可查看被跳过目录路径、命中前缀、跳过原因以及位于根目录还是子目录。
 - 修复完成详情窗口升级为带筛选的可滚动结果视图，支持单独筛出“失败”“已跳过”“强制尝试但未保存”“强制尝试后保存”“不适合保留相关”“候选回退 / no-op”等类别，并可复制当前筛选结果。
- 分析进度窗口新增“取消分析”，窗口关闭叉号等同于取消；取消会清空本轮目标已写入的分析结果、失败状态、推荐修复和 cleanup candidates，保留文件列表并阻止已取消后台任务继续写回。
- 分析与修复进度窗口新增耗时显示和面向用户的阶段提示；目录扫描四选项窗口改为受屏幕高度限制的可滚动布局，避免小屏或缩放环境遮住“取消扫描”。
## 1.1.3 - 2026-05-05

- 新增 portrait-aware 区域分析，为 AnalysisResult 增加 face/subject/background/highlight 区域、场景类型、曝光状态和修复策略字段。
- 修复闪光灯人像与暗背景毕业照被误判为欠曝的问题，主体曝光正常时不再默认强行全局提亮。
- 新增高调背景与亮背景人像识别，高亮白墙或浅色建筑场景不再默认走强全局压高光。
- 增加局部人像增强、主体中间调增强、深色服装细节增强和高调背景保护等轻量局部修复方法。
- 新增人像候选修复的评分与回退机制，并补上所有跳过场景的显式跳过理由与结果提示展示。
- 进一步收紧 portrait-aware 分析：新增 `face_candidates` 明细，记录 raw candidate 到 validated face 的拒绝原因，降低椅背文字、绿植纹理、手部、衣物边缘误识别进入 portrait policy 的概率。
- 新增 `portrait_out_of_focus` 问题标签，以 validated face / subject 为核心判断人像主体虚焦；当背景或周边结构明显比脸更清楚时，可直接标记为高风险清理候选。
- 新增通用 `cleanup_candidates` 结构，用于承载“不适合保留 / 建议删除”原因，而不再把清理逻辑写死在人像虚焦里。
- UI 新增独立的“不适合保留候选”框体，默认不勾选，支持单个勾选、批量切换、全选、取消全选，并要求二次确认后才执行安全清理。
- 清理动作改为优先移入系统回收站；若系统不支持，则退回到项目内 `_cleanup_candidates` 隔离目录，避免永久删除。
- 修复少量分析结果文案显示为乱码的问题，并增加问题文案兜底回退机制，确保异常文本不会直接展示给用户。
- 修复输出方向归一问题：当原图依赖 EXIF 方向标签显示时，保存后的 JPEG / WebP 现在会把 Orientation 归一为 `1`，避免查看器再次旋转。
## 1.1.2 - 2026-05-02

- 调整饱和度相关分析算法，降低自然绿植、花丛和阴影高纯度颜色场景的误判概率。
- 将“饱和度偏高”的修复策略改为优先压制中高亮区域的极端颜色，减少整图发灰现象。
- 修复竖图在连续修复后发生 90 度旋转的问题，输出 EXIF 方向统一归一。
- 在 `docs/` 下新增 `technical/` 与 `updates/` 子目录，用于分别存放技术文档和按版本号归档的更新文档。
- 整理版本记录，补齐饱和度算法、文档体系和调试模式相关更新说明。

## 1.1.1 - 2026-04-30

- 恢复快速启动入口，移除日常启动时的依赖检查，双击启动不再额外执行 `pip install`。
- 修复图片导入与目录扫描主流程，确保单图、多图和文件夹入口能正常入列并完成扫描。
- 修复全局拖拽导入，支持把资源管理器中的单张或多张图片拖入缩略图结果列表或主窗口区域。
- 右侧预览区改为 HUD 加指标条图布局，移除图片预览，并让条图在较窄区域自动缩小字号以尽量显示更多指标。
- 优化条图区域高度与二级弹窗尺寸，确保修复方案窗口底部“开始修复”按钮完整可见。
- 分析任务进度改为按单张图片内部阶段累计推进，保留真实进度和多节点更新。
- 修复完成后自动取消已处理图片的勾选，减少重复修复。
- 新增调试模式：修复完成后可按本轮成功结果选择打开原图和修复图进行快速对比。
- 更新历史已补齐至 `1.1.1`，并保留旧版本记录。

## 1.1.0 - 2026-04-30

- 主界面重构为稳定的左右分栏和右侧四区布局，避免顶部进度区被遮挡。
- 新增原生 Windows 拖入支持，可同时拖入多张图片或整个目录。
- 新增只读 Console 面板，用于显示扫描、分析、修复和清理过程日志。
- 修复对话框支持关闭后缀和覆盖原文件，默认仍为安全输出到新目录。
- 修复输出保留 EXIF、DPI、ICC Profile 和可用的 XMP 元数据，并写入修改来源信息。
- 移除默认可见水印接入，保留独立签名叠加模块但默认不启用。
- 增强高饱和 HDR 场景和人像低饱和场景的误判抑制，降低运动图与人像样片的误报概率。
- 完善模块文档、维护说明和数字签名能力边界说明。

## 1.0.0 - 2026-04-30

- 列表管理改进：新导入图片默认标记为已选，分析选中优先处理所有已选项。
- 修复输出保留原始 EXIF 与 DPI，并写入软件、作者和修改标记。
- 新增累计统计、报表导出和问题检出率变化曲线。

## 0.9.0 - 2026-04-30

- 列表支持右键移出当前图片，新增内容改为追加到现有列表。
- 处理状态改为标签式显示，支持单击处理状态列切换。
- 分析进度增加单张图片内部阶段提示。
- 补充色彩寡淡与饱和度偏高的修复方法。
- 新增模块维护文档。

## 0.8.0 - 2026-04-30

- 进度模块独立为统一控制器，目录读取、分析和修复共用同一套状态更新逻辑。
- 恢复导入、分析、修复三类任务的真实进度显示，并补回独立进度弹窗。
- 分析维度新增色彩寡淡与饱和度偏高。
## 1.1.5 Analysis Cancel Addendum - 2026-05-07

- Tightened batch-analysis cancel state consistency: cancel keeps the file list, clears partial results/errors/cleanup flags/similar groups for the canceled run, and allows immediate re-analysis.
- Added Console cancel summaries with elapsed time, cleared/canceled counts, and a later worker shutdown confirmation.
- Kept stale background result protection based on run id; no analysis algorithm or threshold changes.

## 1.1.5 Real-Image Performance Addendum - 2026-05-07

- Added `/test` local real-photo benchmark workflow and `benchmark_test_images.py`; `/test` image files stay ignored by git, with only README/.gitkeep allowed.
- Corrected batch analysis timing terminology: Console now leads with real wall time and labels worker cumulative time as cumulative worker effort, not user wait time.
- Centralized analysis worker planning so low/medium/high/custom settings affect the actual executor and report requested vs actual worker counts.
- Added conservative working-image analysis for large photos, scaled result regions back to original coordinates, and kept noise conclusions stable with pixel-scale correction.
- Used Pillow JPEG `draft()` in similar feature extraction to avoid unnecessary full-size decode for hash/vector stages.
- `/test` real 16-photo benchmark: high mode improved from 53.29s wall time to 23.92s; quality spot check stayed at 6 issue images, 3 cleanup candidates, and 4 similar groups.
