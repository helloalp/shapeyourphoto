# 信息可视化与 HUD/条图规范

- 主界面右侧是分析结果仪表盘，优先展示 HUD、问题强度条图、关键诊断和 EXIF/属性。
- 文件名、尺寸、识别结果、推荐修复、风险值应压缩为摘要，不得挤占条图高度。
- 条图必须有稳定高度和可读标签；窗口缩小时可以滚动或缩短文字，但不能遮挡滚动条或底部按钮。
- 批量统计适合放在列表标题区、底部状态或详情弹窗，不应长期占据主界面顶部。
- 信息图只展示用户能理解的结果，不暴露过细阈值和内部评分公式。
# 1.1.8 HUD Layout Addendum

HUD text, chart bars, percentages and numeric values must never share the same uncontrolled horizontal space. The chart reserves a right-aligned percentage column and a separate right-aligned value column. HUD labels wrap, risk values keep a minimum width, and the right-side stack must scroll or resize instead of overlapping when the window reaches its minimum size.
