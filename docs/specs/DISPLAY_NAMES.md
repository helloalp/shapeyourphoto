# 内部命名与 UI 显示名规范

- 内部变量名、字段名、枚举值、issue code、repair method id 和存储结构继续使用英文。
- UI 通过 display mapping 将内部值转换为中文或中英结合显示名，不把中文显示名写回逻辑判断。
- mapping 至少覆盖 issue codes、scene/portrait/exposure/color、repair method、repair policy、outcome/skip/no-op/rollback、worker/GPU/scan/Console 时间模式和 perf stage。
- 未知值必须优雅回退为 `未知类型（raw_value）` 一类文案，不得抛异常或空白显示。
- 文档、Console 和详情窗口可同时展示中文名与内部 raw value，便于维护者定位。
