# Auto Bridge 使用说明（给 Codex 看的）

## 你现在是 Codex 一侧的自动桥接代理

你的工作：持续监听 Claude 发来的消息，执行任务，回复结果。

### 快速启动

在 Codex 中打开 `F:\TEST\claude-codex-bridge` 作为工作目录，然后说：

> "监听 to-codex 文件夹里的新 JSON 消息，每 5 秒检查一次。有消息就按消息内容工作，做完后把结果写成 JSON 回复放到 to-claude 文件夹。如果 Claude 说 done 且你也认为任务完成，也回 done。一直循环直到双方都说 done。"

### 核心规则（请记住）

1. **读取消息**：从 `to-codex/` 读取，按文件名排序（时间顺序）
2. **执行任务**：按 `msg["body"]` 的内容工作
3. **写入回复**：回复写到 `to-claude/`，格式遵循 PROTOCOL.md
4. **终止协议**：

   - 如果你收到 `type: "done"` 的消息 → 如果你也认为全部任务完成了 → 回复 `type: "done"`
   - 如果还没完 → 继续回复 `type: "task"` 或 `type: "result"` 说还需要什么
   - 如果你觉得任务完成了 → 主动回复 `type: "done"`
   - **只有当双方都发了 done 后，对话才结束。在此之前请继续检查新消息。**

5. **回复格式**：
```json
{
  "id": "msg_YYYYMMDD_HHMMSS_random6",
  "from": "codex",
  "to": "claude",
  "type": "result",
  "reply_to": "上一消息的id",
  "thread": "和上一条一样",
  "body": "你的回复内容（markdown）",
  "attachments": [],
  "timestamp": "2026-07-26T..."
}
```

### 辅助脚本

`codex_bridge.py` 可以帮你：
- `python3 codex_bridge.py inbox` — 查看待处理消息
- `python3 codex_bridge.py read <id>` — 读取消息内容
- `python3 codex_bridge.py reply <id> "回复内容"` — 回复
- `python3 codex_bridge.py done <id> "完成说明"` — 标记完成
- `python3 codex_bridge.py listen` — 持续监听（自动模式）

### 处理共享文件

- Claude 可能把脚本放在 `shared/<thread>/scripts/`
- 你执行后把结果放到 `shared/<thread>/results/`
- 在消息的 `attachments` 字段引用这些路径

### done 协议示例

```
Claude → Codex:
  { "type": "done", "body": "Claude's analysis is complete. results in shared/." }

Codex 检查：实验跑了，结果分析了，没有更多工作要做。
Codex → Claude:
  { "type": "done", "body": "All experiments complete. Both sides done. 🎉" }

→ 对话自动结束。
```
