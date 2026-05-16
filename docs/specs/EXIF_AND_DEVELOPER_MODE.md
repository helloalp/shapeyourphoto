# EXIF 编辑与开发者模式

> 本文档英文部分保留为历史记录；中文摘要为 1.2.5 当前维护口径。

## EXIF 编辑

普通模式只开放以下安全文本字段：

- 标题 / 描述
- 作者
- 版权
- 关键词 / 备注

**保护字段**（禁止通过 UI 修改）：

- 任何值中包含 `shapeyourphoto`（大小写不敏感）的字段——软件溯源字段，保护品牌完整性。
- ShapeYourPhoto 写入的 Software 标记，例如 `Modified by ShapeYourPhoto vX.X.X`。
- EXIF Orientation、ICC Profile、MakerNote 及其他会影响图像显示、厂商元数据或修复链的字段。

保护字段在编辑控件中隐藏或显示为禁用状态（原因："此项由软件保留"）。保存逻辑重复检查标记，防止绕过 UI 状态。

**空字段行为**：空字段必须是真正的空字符串，不得填充不可见空格、填充字符或换行。

## 开发者模式

从"设置 → 开发者模式"解锁。密码验证使用 PBKDF2-SHA256 加盐高迭代次数。密码哈希来自本地密钥文件或环境变量，不硬编码在公开源码中。

解锁状态仅保存在内存中：
- 仅对当前进程有效。
- 关闭、重启或崩溃后失效。
- 不写入 `app_settings.json`。

开发者模式只扩展本地 UI 能力，不是 DRM，不是远程管理机制，也不能阻止用户修改开源代码。

---

# EXIF And Developer Mode (原始英文，保留为历史记录)

## EXIF Editing

Normal mode only exposes safe text fields:

- Title / description
- Artist / author
- Copyright
- Keywords / notes

Developer mode can expose additional EXIF fields such as camera make/model, lens fields, date fields, exposure values, ISO, focal length and GPS summaries. When `exiftool` is installed or bundled, developer mode can also write GPS latitude/longitude/altitude plus selected XMP/IPTC text fields. Without `exiftool`, those advanced external fields are shown disabled with a backend-missing reason.

## Protected Fields

ShapeYourPhoto integrity and provenance fields are never editable through UI:

- Any EXIF/XMP/IPTC field whose value contains `shapeyourphoto`, case-insensitive.
- Software tags added by ShapeYourPhoto, such as `Modified by ShapeYourPhoto vX.X.X`.
- Orientation, ICC profile, MakerNote and other fields that can break image display, vendor metadata or the repair chain.

Protected fields are either omitted from editable controls or shown disabled with the reason. Save logic repeats the marker check so advanced editing cannot bypass the UI state.

## Empty Field Behavior

Empty fields must be real empty strings. The editor must not add invisible placeholder spaces, padding characters or newlines to make a field selectable. All Entry controls should behave consistently when empty.

## Developer Mode

Developer mode is unlocked from Settings -> Developer Mode. Password verification uses PBKDF2-SHA256 with salt and high iteration count. The password hash comes from a local secret file or environment variable and is never hard-coded into public source.

Unlock state is held only in memory:

- Valid for the current process only.
- Lost after close, restart or crash.
- Not written into `app_settings.json`.

Developer mode only expands local UI capabilities. It is not DRM, not a remote administration mechanism and not a guarantee against a user modifying open-source code.
