# ShapeYourPhoto 维护文档

`docs/` 是 ShapeYourPhoto 的正式维护文档目录。后续维护者应从这里理解项目，不要依赖临时 handover、聊天摘录或过时根文档。

## 目录分工

- 根 [README.md](/E:/aitools/shapeyourphoto/README.md)：用户入口、当前能力和维护文档入口。
- 根 [MODULES.md](/E:/aitools/shapeyourphoto/MODULES.md)：快速模块索引，便于先定位文件。
- `docs/`：当前维护规则、系统总览、模块参考和 UI 工作流，是日常维护的权威说明。
- `docs/technical/`：专题技术文档，记录分析链路、性能并发、相似图、cleanup、设置扫描等跨模块规则。
- `docs/specs/`：产品、界面、用户可见语言、信息呈现、Console、display mapping、用户数据和设置扩展规范；不替代 technical 文档。
- `docs/updates/`：按版本归档的更新记录。旧版本文档保留历史上下文；如与当前行为冲突，以 1.2.5 文档和代码为准。

## 建议阅读顺序

1. [PRESERVATION_RULES.md](/E:/aitools/shapeyourphoto/docs/PRESERVATION_RULES.md)
2. [SYSTEM_OVERVIEW.md](/E:/aitools/shapeyourphoto/docs/SYSTEM_OVERVIEW.md)
3. [MODULE_REFERENCE.md](/E:/aitools/shapeyourphoto/docs/MODULE_REFERENCE.md)
4. [UI_AND_WORKFLOWS.md](/E:/aitools/shapeyourphoto/docs/UI_AND_WORKFLOWS.md)
5. [MAINTENANCE_GUIDE.md](/E:/aitools/shapeyourphoto/docs/MAINTENANCE_GUIDE.md)
6. [technical/README.md](/E:/aitools/shapeyourphoto/docs/technical/README.md)
7. [specs/README.md](/E:/aitools/shapeyourphoto/docs/specs/README.md)
8. [updates/README.md](/E:/aitools/shapeyourphoto/docs/updates/README.md)

## 当前维护主题

1.2.5 的文档体系以这些当前事实为准：

- `src/analyzer.py` 是兼容入口，分析主逻辑在 `src/analysis/` 包。
- 主界面以主列表工作流为准；没有独立单图窗口主路径。
- 降噪并入统一分析和修复链；没有孤立"去噪当前"主入口。
- 不适合保留图片是安全复核机制，默认不修复、不删除，删除必须二次确认并走安全清理。
- 相似图是批次级附加结果，不写回单张 `AnalysisResult`。
- 性能计时统一用 `perf_timings` / `perf_notes`，Console 只做合并后的用户可读摘要。
- GPU 只是可选检测和 CPU 回退提示，不能成为必需依赖。
- 1.2.5 新增：UI mixin 已拆分到 `ui_*.py`；`src/ui/` 承接 UI 基础设施；`updater_v2.py` 是当前 updater 主实现；`cryptography` 是正式依赖；`start.bat` 支持按需安装依赖；内部 code/enum 通过 `ui/display_names.py` 映射为用户可读中文显示名。

## 文档维护规则

- 不得删除 `docs/`、`docs/technical/`、`docs/updates/`。
- 不得清空正式文档。
- 旧内容不适用时，应修订、迁移、标注历史上下文，或指向当前说明。
- 功能、模块、设置或版本变化时，同步更新 `CHANGELOG.md`、`src/app_metadata.py` 和对应 `docs/updates/<version>.md`。
- 版本记录默认使用中文：`app_metadata.CHANGELOG`、根 `CHANGELOG.md` 和 `docs/updates/<version>.md` 必须保持中文事实口径一致；英文仅保留在文件名、函数名、协议字段、环境变量和内部 code/enum 等技术标识中。

# 1.1.9 Documentation Note

Public `docs/` keeps user, contributor and module-boundary information. Private server deployment steps, signing-key handling, release operations, internal maintenance strategy and local AI-agent instructions live under ignored `private_docs/`.

See also `docs/updates/1.1.9.md`, `docs/technical/UPDATES_AND_CLOUD.md`, and `docs/technical/UI_SETTINGS_DATA.md`.

# 1.2.5 文档说明

公开的 `docs/` 保留面向用户、贡献者和模块边界的信息。服务器部署步骤、私钥操作、发布流程、内部维护策略和 AI 协作提示词存放于被 `.gitignore` 忽略的 `private_docs/` 中，不进入公开仓库。

参见 `docs/updates/1.2.5.md`、`docs/technical/UPDATES_AND_CLOUD.md` 和 `docs/technical/UI_SETTINGS_DATA.md`。
