# Cleanup Candidates

## 定位

cleanup candidate 表示“不适合保留 / 建议人工复核删除”的候选，不是自动删除指令。它用于降低明显失败照片进入修复和留存的概率，同时保护用户数据安全。

## 生成

- 分析阶段先生成 `Issue`。
- 如果 issue meta 中包含 cleanup candidate 标记，`src/analysis/discard.py` 会生成 `CleanupCandidate`。
- 当前高风险来源包括真实正面人像严重虚焦、严重全图糊片和极端不可恢复曝光。

## UI

- 主界面左侧有 cleanup candidate 面板。
- 本轮分析后可弹出 `cleanup_review_dialog.py`。
- 候选默认不勾选。
- 用户可单选、多选、全选或取消全选。
- 主菜单可重新打开候选复核。

## 修复关系

cleanup candidate 默认不进入修复。只有用户在 `repair_dialog.py` 勾选“强制修复不值得保留的图片”后，候选才允许进入 repair planner / repair engine。

即使强制尝试，也仍需通过：

- 单图 repair plan。
- 候选评分。
- 安全检查。
- 可保留性判断。
- 回退/no-op/跳过保存。

## 删除

删除必须走 `file_actions.safe_cleanup_paths()`：

1. 优先系统回收站。
2. 回收站不可用时移入 `_cleanup_candidates`。
3. 清理失败时向用户展示原因。

禁止直接 `unlink()` 或绕过确认永久删除。

## 与相似图关系

同一张图可以同时是 cleanup candidate 和 similar group 成员。UI 只显示标记，不自动删除，也不把相似组写入 cleanup candidate。
