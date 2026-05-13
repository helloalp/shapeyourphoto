# 更新与云端公告

ShapeYourPhoto 从 1.1.8 开始加入签名更新、云端公告和独立 updater；1.1.9 将生产更新地址和公告地址固定在客户端内部；1.2.0 将 `cryptography` 依赖、公钥资产和真实 updater 测试流程整理为正式可用基础状态。

公开文档只说明客户端契约、安全边界和用户可见行为。服务器目录、发布脚本、私钥位置、手工签名步骤和真实发布操作只写在被 `.gitignore` 忽略的 `private_docs/` 中。

## 客户端模块

- `src/cloud_client.py`：读取签名更新 manifest 和云端公告。
- `src/cloud_security.py`：canonical JSON、sha256、Ed25519 签名验证和安全路径工具。
- `src/cloud_state.py`：带 HMAC 完整性保护的本地更新延后状态。
- `src/integrity_guard.py`：更新/公告关键模块存在性检查，以及可选的签名核心哈希 manifest 验证。
- `src/ui/cloud_actions.py`：启动检查、手动检查、公告弹窗和 updater 启动的 UI 编排。
- `src/ui/cloud_dialogs.py`：更新、检查中和云端公告弹窗。
- `src/updater.py`：兼容入口，继续服务旧版本和旧文档中的启动路径。
- `src/updater_bootstrap.py`：新版 updater 启动入口，主程序优先启动它；不存在时回退到 `src/updater.py`。
- `src/updater_v2.py`：新版独立 GUI updater 实现，负责下载、sha256 校验、安全解压、替换、隔离删除项和失败回滚。

## 请求标识与超时

- Manifest、公告和更新包下载请求都使用 ShapeYourPhoto 自有 User-Agent，例如 `ShapeYourPhotoUpdater/1.2.5 (version_id=9; Windows)`。
- User-Agent 可包含版本号、版本 ID 和平台名，不包含用户名、设备名、路径或其他隐私信息。
- 网络握手、读取或 TLS 超时不得卡住主界面或设置窗口；普通 UI 显示“暂时无法连接更新服务，请稍后再试。”，具体异常写入 Console。
- 启动自动检查失败只写 Console，不弹窗打断普通启动。

## 依赖与公钥

- 源码包依赖由 `requirements.txt` 统一声明，`start.bat` 通过 `tools/launcher/start_helper.py` 按需安装；`tools/legacy/setup_deps.bat` 仅作兼容入口。
- `cryptography>=42.0.0` 是正式依赖，用于 Ed25519 验签。
- 正式包应内置 `assets/update_public_key.pem`。
- `SHAPEYOURPHOTO_UPDATE_PUBLIC_KEY_FILE` 只作为开发测试覆盖方式，普通用户不需要设置。
- 私钥永远不能进入公开仓库、源码包或发布包。

缺少 `cryptography` 时，源码包启动 helper 应按需安装 `requirements.txt`；如果安装失败，应明确提示本地 Python 环境缺少依赖，并提示重新运行 `start.bat` 或手动执行 `python -m pip install -r requirements.txt`。这类问题不是服务器 manifest 签名失败，也不应显示成网络错误或服务器错误。

## Manifest 契约

签名对象示例：

```json
{
  "version": "1.2.1",
  "version_id": 5,
  "build_id": 5,
  "package_url": "https://helloalp.top/shapeyourphoto/updates/packages/shapeyourphoto-1.2.1.zip",
  "sha256": "...",
  "package_size": 123456,
  "release_notes": ["..."],
  "managed_files": ["app.py", "src/ui/cloud_actions.py"],
  "deleted_paths": [],
  "channel": "stable"
}
```

线上响应是签名 envelope：

```json
{
  "signed": { "...": "manifest or messages payload" },
  "signature": "base64-ed25519-signature"
}
```

`version_id` / `build_id` 单调递增，并与本地 `APP_VERSION_ID` / `APP_BUILD_ID` 比较。

客户端固定使用：

- Manifest: `https://helloalp.top/shapeyourphoto/updates/manifest.json`
- Messages: `https://helloalp.top/shapeyourphoto/updates/messages.json`

这两个 URL 不在设置页公开、不允许用户修改，也不写入普通 `app_settings.json`。

## 公告契约

公告同样使用签名 envelope。`signed` 内部结构示例：

```json
{
  "messages": [
    {
      "id": "notice-2026-05-10",
      "enabled": true,
      "min_version_id": 1,
      "max_version_id": 5,
      "title": "公告",
      "body": "可滚动正文",
      "countdown_enabled": true,
      "countdown_seconds": 5,
      "show_update_button": true
    }
  ]
}
```

启动时公告读取失败只写 Console 简短日志，不打断普通启动。

## Updater 安全边界

- 主程序只在 manifest 验签通过后，将 manifest 写入用户数据目录并启动 `src/updater.py`。
- updater 下载 package 后校验大小和 sha256。
- `package_size` 和 `sha256` 必须来自同一个最终 zip。覆盖服务器 zip 后必须重新生成 manifest 并重新签名；否则旧 updater 会直接报 `package size mismatch` 并中止。
- 新版 updater 遇到 `package_size` 不一致但 sha256 一致时会记录警告并继续；如果 sha256 也不一致，则显示 expected/actual/url 细节并允许关闭 updater 窗口。
- zip 解压会拒绝 zip-slip 路径。
- updater 只写入应用目录下的受管理路径。
- `deleted_paths` 只做隔离，不直接永久删除。
- `data/`、`private_docs/`、`test/`、`benchmark_reports/`、`tmp/` 等本地目录不得被更新包覆盖或删除。
- updater 窗口的取消按钮和关闭叉号都应立即关闭 updater，不再显示“下一个安全点退出”之类的等待提示。下载阶段会尽量停止；如果正在执行文件替换，用户应以重新启动后状态和隔离目录为准。
- 新版 updater 的 package 下载使用较长读取超时和多次重试；如果仍显示 `The read operation timed out`，优先检查服务器限速、中间层断连、包体过大或网络链路。
- 回滚过程有超时出口；回滚失败时显示中文简短提示，详细错误保留在 updater 窗口日志。
- 如果 `managed_files` 包含 updater 本身，新版 updater 不直接覆盖正在运行的 updater 文件，而是写入临时 stager；stager 等待当前 updater 退出后完成最后替换并重启主程序。
- stager 只复制 manifest 中已校验更新包内的延迟文件，目标仍必须位于应用目录内。
- 1.2.5 起，主程序优先启动 `src/updater_bootstrap.py`，再由它进入 `src/updater_v2.py`；如果 bootstrap 不存在，则回退到旧的 `src/updater.py`。
- 1.2.3/1.2.4 不再通过内置 updater 直升 1.2.5；本次采用签名 manifest 的 `release_notes` 提示用户手动下载完整 1.2.5。
- 新版客户端支持 `external_download_only` / `disable_in_app_update` / `manual_download_only` manifest 字段。命中后只显示更新说明，不启动内置 updater。
- 新版客户端预留 update manifest 目标范围判断：服务端可在单个 manifest 上添加 `target_min_version_id` / `target_max_version_id`，或在 `updates` 列表中放多个候选 manifest。客户端只选择适用于当前 `APP_VERSION_ID` / `APP_BUILD_ID` 的候选更新。
- 1.2.5 之后发布修复 updater 或清理旧入口的版本时，`managed_files` 可以包含 `src/updater.py`、`src/updater_v2.py` 和 `src/updater_bootstrap.py`；若必须替换或删除当前正在运行的 updater 入口，则由新版 stager 收尾。
- 新版 updater 支持 `moved_paths` / `move_paths` 做目录迁移，支持 `post_update_required_files` / `required_files` 做更新后文件存在性检查，支持 `deferred_deleted_paths` / `delete_after_restart` 在 updater 退出后隔离删除旧入口。

## 模拟验证

本地鲁棒性验证脚本：

```powershell
python tools\update_smoke\update_resilience_smoke.py
```

脚本只创建临时假应用目录和小型 zip，不访问真实服务器。当前覆盖：

- 本地旧版本号到服务器新版本、当前已是最新版本的比较。
- update manifest 目标版本范围筛选和 `updates` 多候选选择。
- Manifest/messages 共用的超时友好提示与 ShapeYourPhoto User-Agent。
- package 下载超时、下载前取消。
- package size 不匹配但 sha256 正确、package size 与 sha256 同时不匹配、单独 sha256 不匹配、zip-slip 恶意路径。
- `managed_files` 包含 updater 本身时生成 stager。
- 手动下载提示 manifest 可阻止新版客户端启动内置 updater。
- `deleted_paths` 包含不存在路径。
- 文件被占用或替换失败后的回滚成功。
- 回滚失败能抛出错误而不是无限等待。

## 版本示例说明

历史文档中出现的 `1.1.9` 是历史示例，不应机械替换。当前 updater 基线版本是 `1.2.0`；第一次真实更新链路测试目标是 `1.2.1`，也就是用本地 `1.2.0` 检查并更新到服务器上的 `1.2.1`。
