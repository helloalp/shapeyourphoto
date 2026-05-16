# Settings And Scan

## 设置来源

[src/app_settings.py](/E:/aitools/shapeyourphoto/src/app_settings.py) 是应用设置的唯一数据入口，负责：

- `settings_schema_version`。
- 默认值。
- 读写 `app_settings.json`。
- 缺失自动创建。
- 损坏备份和回退默认值。
- 所有字段规范化。
- `migrate_settings(old_version, data)` 迁移入口。

[src/settings_dialog.py](/E:/aitools/shapeyourphoto/src/settings_dialog.py) 是统一 UI 入口。不要新增零散设置菜单项。

## 当前设置

- `settings_schema_version`：当前为 `6`，保存时自动写入。
- 扫描忽略目录前缀、后缀、包含规则。
- 默认扫描模式。
- 修复完成详情默认筛选。
- 分析并发模式。
- 自定义 worker 数。
- GPU 加速模式。
- Console 时间模式：24 小时制、12 小时制、启动后经过时间。
- 外观主题：经典清绿、石墨灰、影像蓝、暖白纸、高对比。
- 界面清晰度 / 密度。
- 语言偏好：简体中文、English、日本語。

旧设置缺少 schema version、缺字段、字段类型错误或含未知字段时，应由 `validate_settings_payload()` 和 `migrate_settings()` 规范化。UI 不直接处理 JSON 细节。

## 扫描模式

- `ask`：每次询问。
- `all`：扫描全部，包含子目录。
- `current_only`：只扫描当前目录。
- `subdirs_only`：只扫描所有子目录。

扫描范围选择窗口必须适配小屏和系统缩放，底部取消按钮可达。

## 忽略规则

默认至少包含 `_repair`。任何以 `_repair` 开头的目录都会在根目录和任意子目录层级整体跳过，例如：

- `_repair`
- `_repair_old`
- `_repair_2026`
- `_repaired`

用户可补充其他前缀，但规范化后仍必须保留 `_repair`。

1.2.6 起扫描规则扩展为三类，均只作用于文件夹名称，不作用于图片文件名：

- 前缀：文件夹名称以规则开头时跳过。
- 后缀：文件夹名称以规则结尾时跳过。
- 包含：文件夹名称中包含规则文字时跳过。

设置页列表显示序号，并支持 Ctrl / Shift 多选后一次删除。默认后缀和包含规则为空，避免误伤用户相册；迁移旧设置时会保留旧前缀并补齐新字段。

## 扫描摘要

`file_actions.ScanSummary` 记录：

- root
- mode
- imported_count
- visited_files
- ignored_prefixes
- ignored_suffixes
- ignored_contains
- skipped_details

Console 只输出摘要；完整跳过路径、命中规则、原因和层级位置由 `scan_summary_dialog.py` 展示。1.1.7 不再把前几条跳过目录刷入 Console，避免大目录扫描时日志噪声过高。

## 扫描与加载进度

选择目录、拖入目录和分析前补扫描都必须在主界面任务进度区显示状态，不再为扫描单独弹出进度窗口。扫描阶段显示正在扫描目录、已处理文件数、已发现图片数、当前路径和 elapsed time；扫描完成后进入“正在加载图片”阶段，说明正在把发现的图片导入结果列表。

无法预知总数时不造假进度，只显示已处理数量。扫描取消通过 cancel_event 表达；取消后已找到的图片可以保留在列表中，迟到扫描结果不得写回新任务。

拖入图片时必须先过滤支持的图片格式；拖入文件夹按当前扫描模式处理。无效文件只给出简短状态和 Console 摘要，不弹长错误。

## 回归入口

修改扫描逻辑时至少检查：

- 按钮选择目录。
- 拖拽文件夹。
- 批量分析前补扫。
- 默认扫描模式。
- 自定义忽略前缀、后缀、包含规则。
- `_repair*` 任意层级跳过。
