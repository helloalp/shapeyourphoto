# 更新与云端通信

ShapeYourPhoto 具备一套支持断点重试和全链路回滚的安全更新器。本篇文档简要介绍更新机制在公开视角下的边界。

> [!NOTE]
> 完整的云端协议结构、JSON 数据格式、Ed25519 加密验签细节以及完整的发布节点链说明属于核心业务资产，已归档于私有技术百科 (`private_docs/`) 中，本文档不展示服务端代码与协议明文。

## 客户端模块职能

- `src/cloud_client.py`：发起通信，处理拉取。
- `src/cloud_security.py`：负责防篡改检测，运用 Ed25519 进行签名校验。
- `src/integrity_guard.py`：本地更新文件存在的保护。
- `src/ui/cloud_actions.py` 与 `cloud_dialogs.py`：构建界面的更新和公告检查弹窗。
- `src/updater_v2.py` / `updater_bootstrap.py`：隔离启动的独立更新器进程。

## 网络隔离与容错

应用的网络请求主要发生在**启动检查**与**手动更新**环节：
1. **静默失败**：由于网络原因（如 DNS 污染、握手超时、证书拦截等）导致的拉取失败，不会阻塞用户的主流程体验。
2. **安全身份**：所有的云端通信采用应用专门的标识符（User-Agent 携带当前主版本号及运行系统信息），绝不在网络请求中暴露任何本机用户的敏感路径或本地设置。

## 更新安全边界

在进行包解压、文件移动替换之前，系统需要通过以下防御：
- 更新主进程与解析进程权限隔离。
- 只有通过非对称加密鉴权的合法包，其下载体才会被接纳。
- 下载完成后进行包大小验证和 Hash 验证。
- 安装过程对解压路径进行安全扫描，防止覆盖系统核心目录或项目内包含用户历史记录的特定隐私目录。

*如需对 Updater 内部的 `managed_files`、`deferred_deleted_paths` 等参数或测试脚本逻辑进行审计或开发介入，请查阅私有知识库 `06_UPDATER_AND_RELEASE_CHAIN.md`。*

## 旧版本文件整理

1.2.6 起，源码包启动准备阶段会扫描旧版布局可能遗留在根目录的旧模块、旧启动入口和旧运行缓存。命中项不会永久删除，而是移入 `data/update_quarantine/legacy_cleanup/<timestamp>/`，并生成 `legacy_cleanup_report.json` 方便核对。

整理策略只处理明确属于旧布局的根目录项目，例如与 `src/` 同名的旧 `.py` 模块、旧 `start_app.*` / `setup_deps.bat` 入口和根目录 `__pycache__`。以下位置必须保留：`.git`、`.github`、`assets`、`build`、`data`、`docs`、`private_docs`、`src`、`test`、`tmp`、`tools`、`_repair`、`_cleanup_candidates` 和更新隔离目录。

正式更新器的 `deleted_paths` / `deferred_deleted_paths` 仍走隔离目录，不做永久删除；受保护顶层路径会被跳过。
