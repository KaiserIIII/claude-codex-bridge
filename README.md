# Claude ↔ Codex Bridge

[简体中文](README_zh.md) · [MIT License](LICENSE)

A Python command-line bridge for exchanging tasks, replies, and file references between Claude and Codex through a shared local directory. JSON messages keep the exchange inspectable, while thread IDs and reply references preserve conversation context.

## Design

```text
Claude → to-codex/ → Codex
Claude ← to-claude/ ← Codex
         shared/
```

- `bridge.py`: Claude-side send, check, wait, and history commands.
- `codex_bridge.py`: Codex-side inbox, read, reply, and completion commands.
- `auto_daemon.py`: polling and conversation state, including a two-party completion handshake.
- `shared/<thread>/`: scripts, documents, and results referenced by messages.

The scripts transport and display messages. Task execution requires an assistant session authorized by the user.

## Quick start

Use Python 3.10+ and a working directory accessible to both assistant sessions. The scripts use the Python standard library.

```bash
git clone https://github.com/KaiserIIII/claude-codex-bridge.git
cd claude-codex-bridge
python bridge.py send "Review the README for broken links" --thread docs
python codex_bridge.py inbox
```

Read a message, then reply using its ID:

```bash
python codex_bridge.py read <message_id>
python codex_bridge.py reply <message_id> "Review completed; findings are in shared/docs/review.md"
python bridge.py check
```

## Polling and completion

```bash
python auto_daemon.py init docs "Review the README for broken links"
python auto_daemon.py tick
python auto_daemon.py status
```

`tick` checks incoming messages and updates the state file; call it periodically from the host session or a scheduler. A `done` message records one side's completion. The conversation stops when both sides confirm completion; a new task or question reopens the exchange.

## Constraints

Messages and shared files are plain local files. Both sessions need access to the directory, and polling introduces latency. Review inbound tasks before execution; access to the message folder does not grant permission to run commands or disclose files. The original workflow was developed on Windows.

## Reference

- [Message protocol](PROTOCOL.md)
- [Usage guide](HOW_TO_USE.md)
- [Codex session setup](AUTO_FOR_CODEX.md)
