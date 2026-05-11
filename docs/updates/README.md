# Update Docs

`docs/updates/` 存放按版本归档的更新记录。旧版本记录不得删除；如果旧记录与当前行为冲突，以最新版本文档、当前 `docs/technical/` 专题和代码为准。

从 1.1.8 起，新增版本记录默认使用中文，并与根 `CHANGELOG.md`、`src/app_metadata.py` 内置 `CHANGELOG` 保持同一事实口径。文件名、模块名、函数名、环境变量、协议字段、内部 code/enum/storage value 等技术标识保留英文原文。

## 规则

1. 每一轮正式版本升级都新增一份 `<version>.md`。
2. 更新文档应说明改了什么、为什么改、涉及文件和验证方式。
3. 旧版本文档保留历史上下文，可追加勘误或维护说明。
4. 不得用临时 handover 或聊天摘要替代版本文档。

## 版本示例说明

历史文档中的 `1.1.9` 多数是当时发布流程示例，不要在历史记录里机械替换。当前 updater 基线版本是 `1.2.0`；下一次真实更新测试目标是 `1.2.1`，也就是验证 `1.2.0 -> 1.2.1`。

1.2.5 调整了源码包启动方式和根目录布局。更早版本文档中的根级 Python 文件链接、`setup_deps.bat` / `start_app.bat` 启动说明只代表历史上下文；当前路径以 1.2.5、`MODULES.md` 和 `docs/MODULE_REFERENCE.md` 为准。

## 当前版本更新文档

- [1.2.5](/E:/aitools/shapeyourphoto/docs/updates/1.2.5.md)
- [1.2.4](/E:/aitools/shapeyourphoto/docs/updates/1.2.4.md)
- [1.2.3](/E:/aitools/shapeyourphoto/docs/updates/1.2.3.md)
- [1.2.2](/E:/aitools/shapeyourphoto/docs/updates/1.2.2.md)
- [1.2.1](/E:/aitools/shapeyourphoto/docs/updates/1.2.1.md)
- [1.2.0](/E:/aitools/shapeyourphoto/docs/updates/1.2.0.md)
- [1.1.9](/E:/aitools/shapeyourphoto/docs/updates/1.1.9.md)
- [1.1.8](/E:/aitools/shapeyourphoto/docs/updates/1.1.8.md)
- [1.1.7](/E:/aitools/shapeyourphoto/docs/updates/1.1.7.md)
- [1.1.6](/E:/aitools/shapeyourphoto/docs/updates/1.1.6.md)
- [1.1.5](/E:/aitools/shapeyourphoto/docs/updates/1.1.5.md)
- [1.1.4](/E:/aitools/shapeyourphoto/docs/updates/1.1.4.md)
- [1.1.3](/E:/aitools/shapeyourphoto/docs/updates/1.1.3.md)
- [1.1.2](/E:/aitools/shapeyourphoto/docs/updates/1.1.2.md)
- [1.1.1](/E:/aitools/shapeyourphoto/docs/updates/1.1.1.md)
