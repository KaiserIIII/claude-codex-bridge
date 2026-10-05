# Claude ↔ Codex Bridge

[English](README.md) · [MIT 许可证](LICENSE)

基于 Python 的命令行桥接工具，通过共享目录在 Claude 与 Codex 之间交换任务、回复和文件引用。消息采用可检查的 JSON 格式，使用线程标识和回复引用保留上下文。

## 设计

```text
Claude → to-codex/ → Codex
Claude ← to-claude/ ← Codex
         shared/
```

- `bridge.py`：Claude 侧的发送、检查、等待和历史查询。
- `codex_bridge.py`：Codex 侧的收件箱、读取、回复和完成通知。
- `auto_daemon.py`：轮询、会话状态及双方完成确认。
- `shared/<thread>/`：消息引用的脚本、文档与结果。

脚本负责传输和展示消息。执行任务需要用户授权的助手会话。

## 快速开始

使用 Python 3.10+，将仓库放在两个助手会话都能访问的工作目录中。脚本仅使用 Python 标准库。

```bash
git clone https://github.com/KaiserIIII/claude-codex-bridge.git
cd claude-codex-bridge
python bridge.py send "检查 README 中的失效链接" --thread docs
python codex_bridge.py inbox
```

读取消息，再使用消息 ID 回复：

```bash
python codex_bridge.py read <message_id>
python codex_bridge.py reply <message_id> "检查完成，结果见 shared/docs/review.md"
python bridge.py check
```

## 轮询与完成确认

```bash
python auto_daemon.py init docs "检查 README 中的失效链接"
python auto_daemon.py tick
python auto_daemon.py status
```

`tick` 检查新消息并更新状态文件，需要由宿主会话或调度器定期调用。一方发送 `done` 后记录该方完成状态；双方均确认后会话结束。新的任务或问题会重新开启交流。

## 使用限制

消息和附件均为本地明文文件。两个会话需要访问同一目录，轮询会带来响应延迟。执行前应审查收到的任务；能够读取消息目录不等于获得运行命令或披露文件的权限。原始工作流在 Windows 上开发。

## 文档

- [消息协议](PROTOCOL.md)
- [使用指南](HOW_TO_USE.md)
- [Codex 会话配置](AUTO_FOR_CODEX.md)
