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
- `src/updater.py`：独立 GUI updater，负责下载、sha256 校验、安全解压、替换、隔离删除项和失败回滚。

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
- zip 解压会拒绝 zip-slip 路径。
- updater 只写入应用目录下的受管理路径。
- `deleted_paths` 只做隔离，不直接永久删除。
- `data/`、`private_docs/`、`test/`、`benchmark_reports/`、`tmp/` 等本地目录不得被更新包覆盖或删除。

## 版本示例说明

历史文档中出现的 `1.1.9` 是历史示例，不应机械替换。当前 updater 基线版本是 `1.2.0`；第一次真实更新链路测试目标是 `1.2.1`，也就是用本地 `1.2.0` 检查并更新到服务器上的 `1.2.1`。
