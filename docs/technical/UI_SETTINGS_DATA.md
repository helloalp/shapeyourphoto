# UI Settings Data

本专题记录 1.1.7 新增的 UI 基础设施、设置扩展、用户数据存储和 EXIF 安全编辑边界。

## UI 包

`ui/` 是新的 UI 基础设施包：

- `ui/window_titles.py`：二级窗口标题统一格式。
- `ui/display_names.py`：内部英文值到 UI 中文显示名的映射层。
- `ui/themes.py`：外观风格 token 和预置主题。
- `ui/hidpi.py`：Windows DPI awareness、Tk scaling 和系统字体配置。
- `ui/splash.py`：Python GUI 启动阶段 Splash。
- `ui/metadata_editor.py`：属性 / EXIF 安全文本字段编辑。

根级 `ui_*` mixin 仍作为兼容层保留，继续承载主窗口扫描、分析、修复、列表、Console 和复核逻辑。新增 UI 基础能力优先放入 `ui/`，不要继续堆进 `ui_app.py`。

## Console 设置

Console 时间模式由 `app_settings.py` 管理：

- `24h`：`[20:28:14]`
- `12h`：`[08:28:14 PM]`
- `24h_tz`：`[20:28:14 UTC+09:00]`
- `elapsed`：`[T+00:20:28]`

`AppConsole` 负责格式化时间戳。设置变更只影响新日志，不重写旧日志。后台线程仍只排队日志，Text 控件刷新由主线程合并执行。

## 外观主题

主题存储为 `theme_id`，通过 `ui/themes.py` 解析 token。当前预置：

- `classic_green`：经典清绿，默认主题，接近旧视觉。
- `graphite`：石墨灰。
- `studio_blue`：影像蓝。
- `warm_paper`：暖白纸。
- `high_contrast`：高对比。

每个主题至少定义主色、强调色、背景、面板、按钮、文字、选中和字体/间距微调。主题不得绕开 HiDPI 字体配置。1.1.9 起，用户设置页只显示配色名称，不公开具体颜色 token。

## 更新与公告设置

1.1.9 起，客户端更新和公告地址由程序内部固定：

- manifest：`https://helloalp.top/shapeyourphoto/updates/manifest.json`
- messages：`https://helloalp.top/shapeyourphoto/updates/messages.json`

这两个地址不在设置页显示，不允许用户修改，也不写入普通 `app_settings.json`。设置页“更新”页面只显示当前版本名称、version_id、build_id 和“检查更新”按钮。

## 用户数据与统计

统计 UI 文案从“累计统计”改为“统计”。`stats_store.py` 将持久化从明文 `usage_stats.json` 迁移到 `data/usage_stats.dpapi`。

- Windows 使用用户级 DPAPI 加密，常规编辑器不能直接读取。
- `data/` 已加入 `.gitignore`。
- 旧 `usage_stats.json` 存在时会先读旧数据，写入新 store，再复制为 `usage_stats.migrated-*.json` 备份标记；不会直接删除旧文件。
- 当前统计只保存聚合数据：分析/修复数量、跳过/no-op/回退、cleanup candidate、相似组、平均 wall time、最近运行时间、按天和按版本聚合计数。

如果 DPAPI 不可用，代码会明确抛出不可加密错误；不得改成 base64 或简单编码。

## EXIF 安全编辑

属性 / EXIF 页面默认只读。点击“编辑”后只允许写入安全文本字段：

- 标题 / 描述
- 作者
- 版权
- 关键词 / 备注

禁止修改：

- 相机型号
- 镜头型号
- 拍摄时间
- EXIF Orientation
- ICC Profile
- 软件内部标记
- 任何会破坏显示方向、元数据保留或修复链路的字段

保存前创建同目录 `.metadata-bak*` 备份；写入失败会尽量恢复原文件并提示。当前仅支持 JPEG / TIFF 的安全文本 EXIF 字段写入，其他格式 UI 显示只读或不支持。
