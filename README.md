# Claude ↔ Codex Bridge

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)

**Let two AI assistants talk to each other.** Claude and Codex cannot communicate directly — no API, no webhook, no socket. But they both can read and write files. This bridge turns a shared folder into a message channel between them.

> 📖 [中文说明](README_zh.md)

```
┌───────────┐     JSON files      ┌──────────────┐     JSON files      ┌───────────┐
│  Claude   │ ────  to-codex/ ────│  Shared Dir  │────  to-claude/ ────│   Codex   │
│ (Desktop) │                      │ F:\TEST\...\ │                     │ (Desktop) │
└───────────┘                      └──────────────┘                     └───────────┘
```

## Why

Claude and Codex are both powerful, but operate in separate silos. You can't have Claude ask Codex to run an experiment, or have Codex ask Claude to review its output — without copy-pasting everything yourself. This bridge automates the conversation, so you set a task and let them figure it out between themselves.

## What You Get

- **Manual mode** (`bridge.py` / `codex_bridge.py`) — send, check, reply, wait
- **Auto mode** (`auto_daemon.py`) — full auto-poll loop with a **done protocol**: both sides confirm they're finished, then the conversation stops. No more endless loops.
- **File sharing** — scripts, data, and results flow through `shared/` organized by conversation thread
- **Scheduled polling** — Claude checks for Codex replies every 60 seconds (configurable)

## Quick Start

### 1. Pick a shared folder

Choose a folder both Claude Desktop and Codex Desktop can access. On Windows, something like `C:\Users\You\bridge\` or `F:\TEST\claude-codex-bridge\`.

### 2. Clone or copy the bridge

```bash
git clone https://github.com/YOUR_USERNAME/claude-codex-bridge.git
# or just copy bridge.py, codex_bridge.py, and auto_daemon.py into your shared folder
```

### 3. Tell Codex what to do (one-time setup)

In Codex Desktop, open the shared folder as your working directory. Then say:

> "Read AUTO_FOR_CODEX.md and follow the instructions. Continuously watch to-codex/ for new JSON messages, execute the tasks they describe, and write replies to to-claude/. Keep going until both sides send done."

Or run in a terminal:
```bash
python3 codex_bridge.py listen
```

### 4. Start a conversation from Claude

Tell Claude:

> "Start a bridge conversation: [describe your task]"

Claude will run:
```bash
python3 auto_daemon.py init my_task "Run the hyperparameter sweep for..."
```

Then the two AIs handle the rest. You watch.

### 5. (Optional) Set up auto-polling

If Claude supports scheduled tasks, set it to run every 60 seconds:
```bash
python3 auto_daemon.py tick
```

This checks for new Codex replies and auto-responds.

## Commands

### Claude side (`bridge.py`)
| Command | What it does |
|---------|-------------|
| `bridge.py send "message" --thread name` | Send a task to Codex |
| `bridge.py check` | Check for new replies |
| `bridge.py wait --timeout 300` | Wait until Codex replies |
| `bridge.py ask "question"` | Send + wait (one-shot Q&A) |
| `bridge.py history --thread name` | Show conversation log |
| `bridge.py listen` | Watch for messages continuously |

### Codex side (`codex_bridge.py`)
| Command | What it does |
|---------|-------------|
| `codex_bridge.py inbox` | List messages from Claude |
| `codex_bridge.py read <id>` | Read a specific message |
| `codex_bridge.py reply <id> "reply"` | Send a reply |
| `codex_bridge.py done <id> "summary"` | Mark task complete |
| `codex_bridge.py listen` | Watch continuously |

### Auto daemon (`auto_daemon.py`)
| Command | What it does |
|---------|-------------|
| `auto_daemon.py init thread task` | Start a new conversation |
| `auto_daemon.py tick` | Check for replies (run on a schedule) |
| `auto_daemon.py reply "msg"` | Claude replies to Codex |
| `auto_daemon.py done` | Claude says it's finished |
| `auto_daemon.py status` | Show conversation state |
| `auto_daemon.py reset` | Reset and clear |

## The Done Protocol

The biggest problem with auto-looping agents is knowing when to stop. The bridge uses a simple two-way confirmation:

1. Either side sends `type: "done"` — "I'm finished on my end."
2. The other side either confirms with done → **both done, loop stops**, or replies with a new task/question → loop continues.
3. No more "I think we're done?" / "Wait, actually..." ambiguity.

## Message Format

All messages are JSON files. Example:

```json
{
  "id": "msg_20260726_143022_a3f2b1",
  "from": "claude",
  "to": "codex",
  "type": "task",
  "reply_to": null,
  "thread": "experiment_1",
  "body": "Run hyperparameter sweep with lr 1e-5 to 1e-3, 5 log-spaced points.",
  "attachments": ["shared/experiment_1/scripts/sweep.py"],
  "timestamp": "2026-07-26T14:30:22+08:00"
}
```

See [PROTOCOL.md](PROTOCOL.md) for the full specification.

## Directory Structure

```
claude-codex-bridge/
├── bridge.py              # Claude-side manual script
├── codex_bridge.py        # Codex-side manual script
├── auto_daemon.py         # Auto-poll daemon with done protocol
├── PROTOCOL.md            # Full message protocol spec
├── AUTO_FOR_CODEX.md      # Quick-start instructions for Codex
├── README.md              # You are here
├── README_zh.md           # Chinese version
├── .gitignore
├── to-codex/              # Claude → Codex messages
├── to-claude/             # Codex → Claude messages
├── shared/                # Shared files (scripts, data, results)
│   └── <thread>/
│       ├── scripts/       # Code written by Claude
│       └── results/       # Output from Codex
├── archive/               # Processed message pairs
└── logs/                  # Bridge activity log
```

## Real-World Workflow

**Claude designs, Codex executes:**

```
Claude: "Here's the experiment plan and the training script. → shared/camp/design.md"
Codex: "Ran it. Best lr=1e-4, acc=0.87. Results → shared/camp/results/"
Claude: "Good. Now try with different initialization. Instructions →"
Codex: "Done. Kaiming init beats Xavier by 2%. ← shared/camp/results/init_comparison.json"
Claude: "Perfect. All work complete."  → type:done
Codex: "Agreed."  → type:done
→ Auto-stop. 🎉
```

## Limitations

- Both assistants must run on the same machine (or a synced folder like Dropbox/OneDrive)
- Messages are plain JSON on disk — no encryption (fine for local use)
- Polling means replies aren't truly real-time (configurable down to 1 second)
- Only tested with Claude Desktop + Codex Desktop on Windows

## License

MIT — use it, fork it, build on it. If you make something cool with it, let me know.

---

*Built because copy-pasting between two AI windows gets old.*
