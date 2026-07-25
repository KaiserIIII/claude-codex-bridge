# Claude ↔ Codex 文件桥接协议

## 目录结构

```
F:\TEST\claude-codex-bridge\
├── bridge.py          ← Claude 端脚本（在 Claude 的 bash 沙箱中运行）
├── codex_bridge.py    ← Codex 端脚本（在 Codex 终端中运行）
├── PROTOCOL.md        ← 本文件（协议规范）
├── HOW_TO_USE.md      ← 使用指南
├── to-codex/          ← Claude 写消息到这里，Codex 从这里读
├── to-claude/         ← Codex 写消息到这里，Claude 从这里读
├── shared/            ← 共享文件（脚本、数据、输出等）
├── archive/           ← 已处理的消息归档
└── logs/              ← 日志
```

## 消息格式

所有消息都是 JSON 文件，存在对应方的 inbox 目录中。

```json
{
  "id": "msg_20260726_143022_a3f2b1",
  "from": "claude",
  "to": "codex",
  "type": "task",
  "reply_to": null,
  "thread": "camp_exp_1",
  "body": "请运行 cross_lingual_align.py 的超参数扫描",
  "attachments": ["scripts/cross_lingual_align.py"],
  "timestamp": "2026-07-26T14:30:22+08:00"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一消息ID，格式 msg_YYYYMMDD_HHMMSS_随机6位 |
| from | string | 发送方：claude 或 codex |
| to | string | 接收方：claude 或 codex |
| type | string | 消息类型：task / question / clarification / result / done / error |
| reply_to | string\|null | 回复哪条消息的ID |
| thread | string | 对话线程名（同一主题的消息用相同 thread） |
| body | string | 消息正文，markdown 格式 |
| attachments | string[] | 附件文件路径（相对于 shared/ 或绝对路径） |
| timestamp | string | ISO 8601 时间戳 |

### 消息类型

- **task** — 分配任务："请运行X实验" "请调优Y参数"
- **question** — 提问："你觉得用哪个优化器？"
- **clarification** — 澄清："你之前说的参数具体是哪个？"
- **result** — 返回结果："实验跑了，结果是..."
- **done** — 任务完成确认："你的请求已处理完毕"
- **error** — 报错："运行失败，因为..."

## 通信流程

### 标准任务流程

```
Claude                    Codex
  │                         │
  │── task ──────────────→  │  (写 to-codex/msg_xxx.json)
  │                         │  (读 to-codex/*.json)
  │                         │  (执行任务)
  │                         │  (写结果到 shared/result_xxx.txt)
  │  ←──── result ───────── │  (写 to-claude/msg_yyy.json, reply_to=msg_xxx)
  │  (读 to-claude/*.json)  │
  │                         │
  │── done ──────────────→  │  (确认收到，任务结束)
```

### 多轮对话流程

```
Claude                    Codex
  │                         │
  │── question ──────────→  │
  │  ←──── result ───────── │
  │                         │
  │── clarification ─────→  │
  │  ←──── result ───────── │
  │                         │
  │── task ──────────────→  │
  │  ←──── done ─────────── │
```

## 文件命名规则

消息文件命名为 `{id}.json`，其中 id 是消息的唯一标识。

共享文件放在 `shared/` 下，按线程组织：
```
shared/
└── camp_exp_1/
    ├── scripts/           ← Claude 写的脚本
    │   └── train.py
    └── results/           ← Codex 写的输出
        ├── metrics.json
        └── plot.png
```

## 冲突处理

由于是文件系统桥接，不存在真正的并发冲突。规则：
- 读取方只读取，不删除（除非带 `--remove` 或自动归档）
- 写入方写完后不修改
- 通过 `reply_to` 字段建立消息之间的关联
- 已完成的消息对归档到 `archive/`，而不是删除
