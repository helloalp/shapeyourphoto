# Preservation Rules

这是 ShapeYourPhoto 的正式文档保留规则。它本身也属于不可删除文档。

## 强制要求

1. 不得删除 `docs/`。
2. 不得删除 `docs/technical/`。
3. 不得删除 `docs/updates/`。
4. 不得清空正式文档。
5. 不得用临时 handover、聊天摘录或一次性交接文字替代正式文档。
6. 不得在缺少代码核验的情况下，仅依据旧文档继续开发。
7. 不得把本地样张、调试输出、patch、`__pycache__` 或临时文件作为文档或版本记录提交。

## 允许的维护方式

- 修正文档中的过时或错误内容。
- 把重复内容迁移到更合适的专题文档。
- 在旧版本说明前补充"历史说明，以当前文档为准"。
- 新增技术专题文档。
- 在更新文档中追加补充记录。

## 当前权威顺序

当文档之间出现冲突时，按以下顺序判断：

1. 当前代码。
2. 1.2.5 的 `docs/` 和 `docs/technical/` 文档（本文档及 MAINTENANCE_GUIDE.md 等）。
3. [docs/updates/1.2.5.md](/E:/aitools/shapeyourphoto/docs/updates/1.2.5.md)。
4. 较早版本的 `docs/updates/` 历史说明。

旧版本文档应保留历史背景，但不应覆盖当前维护规则。

## 新增文档约定

- 模块职责变化：更新 [MODULE_REFERENCE.md](/E:/aitools/shapeyourphoto/docs/MODULE_REFERENCE.md)。
- UI 主流程变化：更新 [UI_AND_WORKFLOWS.md](/E:/aitools/shapeyourphoto/docs/UI_AND_WORKFLOWS.md)。
- 并发、性能、扫描、cleanup、相似图、分析链路变化：优先在 `docs/technical/` 新增或修订专题。
- 版本升级：更新 [CHANGELOG.md](/E:/aitools/shapeyourphoto/CHANGELOG.md)、[src/app_metadata.py](/E:/aitools/shapeyourphoto/src/app_metadata.py) 和 `docs/updates/<version>.md`。

## 版本记录语言规则

- `src/app_metadata.py` 的 `CHANGELOG` 属于应用内用户可见版本历史，默认必须使用中文。
- 根 `CHANGELOG.md` 与 `docs/updates/<version>.md` 默认必须使用中文，并与 `app_metadata.CHANGELOG` 同步同一批事实。
- 英文只用于技术标识原文，例如文件名、函数名、模块名、环境变量、协议字段、第三方库名、内部 code/enum/storage value。
- 不得把整条英文 release note 直接放进 `app_metadata.CHANGELOG` 作为正式版本记录。

# 1.1.8 Public / Private Documentation Rule

Starting with 1.1.8, public docs must remain useful but should not contain private server operation details, signing private-key handling, internal release scripts, commercial maintenance strategy or deep private AI-agent prompts. Those belong in ignored `private_docs/for_developer/` and `private_docs/for_developai/`.

`private_docs/` must stay in `.gitignore`.
