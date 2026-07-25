# Claude ↔ Codex 桥接使用指南

## 原理

Claude 和 Codex 无法直接通信，但它们都能读写文件。这个桥接系统让它们通过 `F:\TEST\claude-codex-bridge\` 共享文件夹交换 JSON 消息。

```
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────────┐
│    Claude        │         │   F:\TEST\claude-     │         │    Codex         │
│  (ClaudeDesktop) │         │   codex-bridge\       │         │  (CodexDesktop)  │
│                  │         │                      │         │                  │
│  bridge.py ──────┼───写──→ │  to-codex/  ───读──→ │         │                  │
│                  │         │                      │         │                  │
│  bridge.py ←──读─┼─────── │  to-claude/ ←───写─── │  codex_bridge.py │
└─────────────────┘         └──────────────────────┘         └─────────────────┘
```

## 第一步：让两个软件都能访问 `F:\TEST`

### Claude 端（已就绪）

我已连接到 `F:\TEST`，可以直接通过 bash 运行 bridge.py。

### Codex 端（需要你做）

1. 在 Codex Desktop 中，把工作目录设置为 `F:\TEST\claude-codex-bridge`
2. 或者在 Codex 中打开该文件夹

## 第二步：典型工作流

### 场景 A：Claude 分配任务，Codex 执行

**Claude 端（我帮你运行）：**
```bash
# Claude 向 Codex 发送任务
python3 /sessions/modest-loving-ride/mnt/TEST/claude-codex-bridge/bridge.py send "请运行 shared/camp_exp/scripts/train.py 超参数扫描，learning rate 范围 1e-5 ~ 1e-3，5个点" --thread camp_exp
```

**Codex 端（你对 Codex 说）：**
> 检查 F:\TEST\claude-codex-bridge\to-codex 里的消息，按消息内容工作。完成后把结果写成 JSON 放到 to-claude 文件夹，reply_to 设为原消息的 id。

或者手动：
```bash
python3 codex_bridge.py inbox                          # 查看消息
python3 codex_bridge.py read msg_20260726_143022_xxx  # 读取完整内容
# ... 执行任务 ...
python3 codex_bridge.py reply msg_20260726_143022_xxx "训练完成。最佳 lr=1e-4，acc=0.87"
```

**Claude 端（我帮你检查）：**
```bash
python3 bridge.py check --thread camp_exp    # 查看回复
```

### 场景 B：一问一答

**Claude 端：**
```bash
# 发送问题并等待回答（自动轮询，最长等5分钟）
python3 bridge.py ask "你觉得 CAMP 项目的 MoE projector 应该用什么初始化策略？" --thread camp_design
```

**Codex 端：** 读取消息 → 思考 → 回复。

### 场景 C：Codex 跑完实验，Claude 分析

1. Codex 跑实验，把结果数据写进 `shared/camp_exp/results/metrics.json`
2. Codex 通过 bridge 通知 Claude：
   ```bash
   python3 codex_bridge.py reply msg_xxx "实验结果在 shared/camp_exp/results/"
   ```
3. Claude 读取结果文件，分析并反馈：
   ```bash
   # 我读取结果，然后回复 Codex 下一步指令
   ```

## 消息类型速查

| 类型 | 谁发谁收 | 含义 |
|------|----------|------|
| `task` | Claude→Codex | 分配任务 |
| `question` | 双向 | 提问 |
| `clarification` | 双向 | 澄清/追问 |
| `result` | Codex→Claude | 返回结果 |
| `done` | Codex→Claude | 任务完成 |
| `error` | 双向 | 报错 |

## 高级用法

### 长时间监听模式

Codex 端持续监听 Claude 的消息：
```bash
python3 codex_bridge.py listen
```

Claude 端持续监听 Codex 的回复：
```bash
python3 bridge.py listen
```

两边同时开监听 + 共享文件传递脚本和结果 = 近似实时协作。

### 传递文件

两种方式：
1. **附件字段**：消息里的 `attachments` 指向 `shared/` 下的路径
2. **直接在 shared/ 中交换**：Claude 把脚本写到 `shared/<thread>/scripts/`，Codex 读取

### 查看对话历史

```bash
python3 bridge.py history --thread camp_exp
```

## 注意事项

- 消息文件不会被自动删掉，需要手动 `--remove` 或定期清理
- 目前没有加密，所有消息以明文 JSON 存储（本地文件，安全风险低）
- 桥接只支持同一台机器上的两个 AI 协作
- 如果两边同时写文件，后写入的会覆盖（但 ID 是唯一的，不会冲突）
