# Product And UI Specs

`docs/specs/` 记录未来新增功能必须遵守的产品、视觉和信息呈现规范。它不替代 `docs/technical/`；技术实现、模块边界和数据结构仍写入 technical 文档。

当前专题：

- [图形设计与视觉风格规范](VISUAL_STYLE.md)
- [弹窗与框体大小规范](WINDOW_SIZING.md)
- [信息可视化与 HUD/条图规范](HUD_AND_CHARTS.md)
- [用户可见语言规范](USER_FACING_LANGUAGE.md)
- [Console 可读性规范](CONSOLE_READABILITY.md)
- [内部命名与 UI 显示名规范](DISPLAY_NAMES.md)
- [用户数据目录与加密存储规范](USER_DATA_AND_ENCRYPTION.md)
- [设置项与 UI 页面扩展规范](SETTINGS_EXTENSION.md)

# 1.2.5 产品与 UI 补充说明

- 1.2.5 中将所有涉及暴露内部字段（如 code, enum, `version_id`, `build_id`, `no-op` 等）的界面区域全部进行了中文化。
- 所有 UI 的警告和提示弹窗应继续遵循 `USER_FACING_LANGUAGE.md` 的规范，不可展示英文日志信息。
- 设置窗口剥离了任何开发向配置（如下载包 URL），仅面向终端用户暴露其关心的配置。

---
> 下方内容为旧版本的维护规范英文历史记录，供追溯使用。

# 1.1.8 Spec Addendum

See `EXIF_AND_DEVELOPER_MODE.md` for the new metadata/developer-mode boundary, and `HUD_AND_CHARTS.md` for the updated non-overlap rule.
