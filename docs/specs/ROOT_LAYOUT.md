# 根目录文件规范

根目录只保留用户入口和仓库基础文件，例如 `ShapeYourPhoto.exe`、`README.md`、`.gitignore`、`.git/`、`.github/`。

新增内容默认进入明确子目录：

- 随版本提交的配置与维护数据：`config/`（包括 `config/changelog/versions.json`）
- 应用代码：`src/`
- 图标和 UI 资源：`assets/`
- 文档：`docs/`
- 本地运行状态与用户数据：`data/`（整个目录不进入版本控制）
- 构建配置与安装器脚本：`build/`
- 开发、验证、发布辅助脚本：`tools/`
- 临时或验证产物：`tmp/`
- 私有说明或内部记录：`private/`

除非文件本身就是用户双击入口、仓库说明或版本控制基础文件，否则不得直接新增到根目录。
