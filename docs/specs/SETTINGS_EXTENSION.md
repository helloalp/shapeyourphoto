# 设置项与 UI 页面扩展规范

- 所有设置必须通过 `app_settings.py` 的默认值、schema version、normalize、validate、migrate、load/save 统一读写。
- 新设置必须同时有 UI 页面或清晰文档入口，不能散落成独立菜单项。
- 设置变化后应尽量立即影响新任务或新日志；无法立即重绘旧内容时要在 UI 或文档说明。
- 设置页按主题分区：扫描、行为偏好、性能、Console、外观/风格。后续页面优先放入既有 Notebook。
- 新主题必须补齐 token，不得导致对比度过低、按钮不可见、字体模糊或最小尺寸失效。
