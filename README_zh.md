# Claude ↔ Codex 桥接 (Bridge)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)

**让两个 AI 助手互相对话。** Claude 和 Codex 无法直接通信——没有 API、没有 webhook、没有 socket。但它们都能读写文件。这个桥接系统把共享文件夹变成了它们之间的消息通道。

> 📖 [English README](README.md)

```
┌───────────┐     JSON 消息      ┌──────────────┐     JSON 消息      ┌───────────┐
│  Claude   │ ──── to-codex/ ────│   共享文件夹   │──── to-claude/ ────│   Codex   │
│ (桌面版)   │                    │ F:\TEST\...\  │                    │ (桌面版)   │
└───────────┘                    └──────────────┘                    └───────────┘
```

## 为什么需要这个

Claude 和 Codex 都很强，但各自为政。你不能让 Claude 叫 Codex 去跑实验，也不能让 Codex 找 Claude 审查它的输出——除非你手动复制粘贴。这个桥接自动化了这个过程：你只需设定任务，让两个 AI 自己商量着来。

## 你得到什么

- **手动模式** (`bridge.py` / `codex_bridge.py`) — 发送、检查、回复、等待
- **自动模式** (`auto_daemon.py`) — 全自动轮询，带 **done 协议**：双方确认都完成后，对话自动停止。再也不会无限循环。
- **文件共享** — 脚本、数据、结果通过 `shared/` 按对话线程组织流转
- **定时轮询** — Claude 每 60 秒自动检查 Codex 有没有新回复（可配置）

## 快速开始

### 1. 选一个共享文件夹

选一个 Claude 桌面版和 Codex 桌面版都能访问的文件夹。Windows 上比如 `C:\Users\你的用户名\bridge\` 或者 `F:\TEST\claude-codex-bridge\`。

### 2. 克隆或复制桥接文件

```bash
git clone https://github.com/你的用户名/claude-codex-bridge.git
# 或者直接把 bridge.py、codex_bridge.py、auto_daemon.py 复制到你的共享文件夹
```

### 3. 告诉 Codex 怎么用（一次性设置）

在 Codex 桌面版中，把共享文件夹设为工作目录。然后说：

> "读取 AUTO_FOR_CODEX.md 文件里的指令。持续监听 to-codex 文件夹中的 JSON 消息，按消息内容执行任务，把回复写到 to-claude。直到双方都说 done 才停止。"

或者在终端运行：
```bash
python3 codex_bridge.py listen
```

### 4. 从 Claude 端发起对话

对 Claude 说：

> "发起桥接对话：[描述你的任务]"

Claude 会运行：
```bash
python3 auto_daemon.py init 我的任务 "请运行 CAMP 项目的超参数扫描..."
```

然后两个 AI 就自己来回沟通了，你看着就行。

### 5. （可选）设置定时轮询

如果 Claude 支持定时任务，设置每 60 秒运行一次：
```bash
python3 auto_daemon.py tick
```

这样 Claude 会一直自动检查 Codex 的新消息并回复。

## 命令速查

### Claude 端 (`bridge.py`)
| 命令 | 功能 |
|------|------|
| `bridge.py send "消息" --thread 线程名` | 发送任务给 Codex |
| `bridge.py check` | 检查有没有新回复 |
| `bridge.py wait --timeout 300` | 等待直到 Codex 回复 |
| `bridge.py ask "问题"` | 发问题并等待回答 |
| `bridge.py history --thread 线程名` | 查看对话记录 |
| `bridge.py listen` | 持续监听消息 |

### Codex 端 (`codex_bridge.py`)
| 命令 | 功能 |
|------|------|
| `codex_bridge.py inbox` | 查看 Claude 发来的消息 |
| `codex_bridge.py read <id>` | 读取某条消息的完整内容 |
| `codex_bridge.py reply <id> "回复"` | 回复一条消息 |
| `codex_bridge.py done <id> "总结"` | 标记任务完成 |
| `codex_bridge.py listen` | 持续监听 |

### 自动守护 (`auto_daemon.py`)
| 命令 | 功能 |
|------|------|
| `auto_daemon.py init 线程名 任务` | 发起新对话 |
| `auto_daemon.py tick` | 检查新回复（定时调用） |
| `auto_daemon.py reply "消息"` | Claude 回复 Codex |
| `auto_daemon.py done` | Claude 说它搞定了 |
| `auto_daemon.py status` | 查看对话状态 |
| `auto_daemon.py reset` | 重置并清空 |

## Done 协议

自动循环代理最大的问题是：怎么知道什么时候该停？桥接系统用了一个简单的双向确认：

1. 任一方发送 `type: "done"` — "我这边的活干完了。"
2. 另一方要么确认 done → **双方 done，循环停止**，要么回复新的任务/问题 → 循环继续。
3. 不再有"我觉得差不多了？"/"等等，其实还有……"这种尴尬。

## 消息格式

所有消息都是 JSON 文件。示例：

```json
{
  "id": "msg_20260726_143022_a3f2b1",
  "from": "claude",
  "to": "codex",
  "type": "task",
  "reply_to": null,
  "thread": "实验一",
  "body": "请运行超参数扫描，lr 1e-5 到 1e-3，5 个对数点。",
  "attachments": ["shared/实验一/scripts/sweep.py"],
  "timestamp": "2026-07-26T14:30:22+08:00"
}
```

完整规范见 [PROTOCOL.md](PROTOCOL.md)。

## 目录结构

```
claude-codex-bridge/
├── bridge.py              # Claude 端手动脚本
├── codex_bridge.py        # Codex 端手动脚本
├── auto_daemon.py         # 自动轮询守护，带 done 协议
├── PROTOCOL.md            # 完整消息协议规范
├── AUTO_FOR_CODEX.md      # 给 Codex 看的快速上手说明
├── README.md              # 英文 README
├── README_zh.md           # 你正在看的这个（中文）
├── .gitignore
├── to-codex/              # Claude → Codex 消息
├── to-claude/             # Codex → Claude 消息
├── shared/                # 共享文件（脚本、数据、结果）
│   └── <线程名>/
│       ├── scripts/       # Claude 写的代码
│       └── results/       # Codex 输出的结果
├── archive/               # 已完成的消息归档
└── logs/                  # 桥接活动日志
```

## 实际工作流

**Claude 设计，Codex 执行：**

```
Claude: "这是实验方案和训练脚本。→ shared/camp/design.md"
Codex: "跑了。最佳 lr=1e-4，acc=0.87。结果 → shared/camp/results/"
Claude: "不错。接下来试不同的初始化策略。指令 →"
Codex: "完成。Kaiming 初始化比 Xavier 高 2%。← shared/camp/results/init_comparison.json"
Claude: "完美。全部完成。"  → type:done
Codex: "同意。"  → type:done
→ 自动停止。🎉
```

## 局限性

- 两个助手必须跑在同一台机器上（或用 Dropbox/OneDrive 同步文件夹）
- 消息以明文 JSON 存在磁盘上——没有加密（本地使用影响不大）
- 轮询意味着回复不是真正实时的（最短可配到 1 秒）
- 目前只在 Claude Desktop + Codex Desktop + Windows 上测试过

## License

MIT — 随便用，随便改，随便二次开发。搞出什么好玩的东西的话，告诉我一声。

---

*再也不想在两个 AI 窗口之间复制粘贴了，所以就写了这个。*
