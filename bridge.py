"""
Claude ↔ Codex Bridge
=====================
File-based message bridge between Claude (running in Claude Desktop)
and Codex (running in Codex Desktop / CLI).

How it works:
  - Claude writes task messages to   F:\TEST\claude-codex-bridge\to-codex\
  - Codex reads from there, works, writes results to to-claude\
  - Claude polls to-claude\ for replies

This script runs INSIDE Claude's bash sandbox. The shared folder is
mounted at /sessions/modest-loving-ride/mnt/TEST/claude-codex-bridge/

Usage (from Claude's side):
  python3 bridge.py send     "Please run the experiments for the CAMP project"
  python3 bridge.py check            # see if Codex replied
  python3 bridge.py wait             # wait (polling) until Codex replies
  python3 bridge.py ask "What hyperparams should I use?"  # send + wait
  python3 bridge.py history          # show conversation history
  python3 bridge.py archive <msg_id> # move a message pair to archive

Message format:
  {
    "id": "msg_20260726_143022",
    "from": "claude",
    "to": "codex",
    "type": "task",          // task | question | clarification | result | done
    "reply_to": null,        // id of the message this replies to
    "thread": "camp_exp_1",  // conversation thread
    "body": "...",
    "attachments": [],       // list of file paths (relative to shared/)
    "timestamp": "2026-07-26T14:30:22+08:00"
  }
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta

# ── Config ──────────────────────────────────────────────────────────
BASE_DIR = "/sessions/modest-loving-ride/mnt/TEST/claude-codex-bridge"
TO_CODEX = os.path.join(BASE_DIR, "to-codex")
TO_CLAUDE = os.path.join(BASE_DIR, "to-claude")
SHARED = os.path.join(BASE_DIR, "shared")
ARCHIVE = os.path.join(BASE_DIR, "archive")
LOGS = os.path.join(BASE_DIR, "logs")

HKT = timezone(timedelta(hours=8))


def now_iso():
    return datetime.now(HKT).isoformat()


def make_id():
    return f"msg_{datetime.now(HKT).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def ensure_dirs():
    for d in [TO_CODEX, TO_CLAUDE, SHARED, ARCHIVE, LOGS]:
        os.makedirs(d, exist_ok=True)


# ── Read / Write messages ───────────────────────────────────────────

def list_messages(folder):
    """Return sorted list of message JSON files in a folder."""
    if not os.path.isdir(folder):
        return []
    files = [f for f in os.listdir(folder) if f.endswith(".json")]
    files.sort()
    return [os.path.join(folder, f) for f in files]


def read_message(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_message(folder, msg):
    ensure_dirs()
    path = os.path.join(folder, f"{msg['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    return path


def move_to_archive(path):
    ensure_dirs()
    fname = os.path.basename(path)
    dest = os.path.join(ARCHIVE, fname)
    os.rename(path, dest)
    return dest


# ── Core commands ───────────────────────────────────────────────────

def cmd_send(body, thread="default", msg_type="task", reply_to=None, attachments=None):
    """Send a message from Claude to Codex."""
    msg = {
        "id": make_id(),
        "from": "claude",
        "to": "codex",
        "type": msg_type,
        "reply_to": reply_to,
        "thread": thread,
        "body": body,
        "attachments": attachments or [],
        "timestamp": now_iso()
    }
    path = write_message(TO_CODEX, msg)
    _log("sent", msg)
    print(f"✅ Sent to Codex: {msg['id']}")
    print(f"   Thread: {thread}")
    print(f"   Type:   {msg_type}")
    print(f"   Body:   {body[:120]}{'...' if len(body) > 120 else ''}")
    if attachments:
        print(f"   Files:  {', '.join(attachments)}")
    print(f"   File:   {path}")
    return msg


def cmd_check(thread=None, remove_after_read=False):
    """Check for new messages from Codex. Returns list of unread messages."""
    files = list_messages(TO_CLAUDE)
    if not files:
        print("📭 No new messages from Codex.")
        return []

    messages = []
    for f in files:
        msg = read_message(f)
        if thread and msg.get("thread") != thread:
            continue
        messages.append((f, msg))

    if not messages:
        print(f"📭 No new messages from Codex (thread filter: {thread}).")
        return []

    print(f"📬 {len(messages)} new message(s) from Codex:\n")
    for fpath, msg in messages:
        _print_message(msg)
        if remove_after_read:
            move_to_archive(fpath)
            print(f"   → archived\n")

    return messages


def cmd_wait(thread=None, timeout=300, poll_interval=3):
    """Wait (polling) for a reply from Codex. Returns when a message arrives."""
    print(f"⏳ Waiting for Codex reply (timeout={timeout}s, poll={poll_interval}s)...")
    print(f"   (Codex should be reading from: {TO_CODEX})")
    print()
    if thread:
        print(f"   Thread filter: {thread}")

    start = time.time()
    last_count = len(list_messages(TO_CLAUDE))

    while time.time() - start < timeout:
        files = list_messages(TO_CLAUDE)
        new_count = len(files)
        if new_count > last_count:
            # New messages arrived
            for f in files[last_count:]:
                msg = read_message(f)
                if thread and msg.get("thread") != thread:
                    continue
                print(f"\n📬 Reply received from Codex (waited {time.time()-start:.0f}s):")
                _print_message(msg)
                # Archive it
                move_to_archive(f)
                _log("received", msg)
                return msg
            last_count = new_count

        elapsed = time.time() - start
        print(f"   ... waiting ({elapsed:.0f}s elapsed)", end="\r")
        time.sleep(poll_interval)

    print(f"\n⏰ Timeout after {timeout}s. No reply from Codex.")
    print(f"   Make sure Codex is checking: {TO_CODEX}")
    print(f"   And writing replies to:   {TO_CLAUDE}")
    return None


def cmd_ask(body, thread="default"):
    """Send a message and wait for reply (convenience)."""
    sent = cmd_send(body, thread=thread, msg_type="question")
    print()
    reply = cmd_wait(thread=thread)
    return reply


def cmd_history(thread=None, limit=20):
    """Show conversation history (sent + received)."""
    sent = []
    for f in list_messages(TO_CODEX):
        msg = read_message(f)
        if thread and msg.get("thread") != thread:
            continue
        sent.append(("→ Codex", msg))

    received = []
    for f in list_messages(TO_CLAUDE):
        msg = read_message(f)
        if thread and msg.get("thread") != thread:
            continue
        received.append(("← Codex", msg))

    # Also check archive
    archived = []
    for f in list_messages(ARCHIVE):
        msg = read_message(f)
        if thread and msg.get("thread") != thread:
            continue
        direction = "→ Codex" if msg["from"] == "claude" else "← Codex"
        archived.append(("📁 " + direction, msg))

    all_msgs = sent + received + archived
    all_msgs.sort(key=lambda x: x[1]["timestamp"])

    if not all_msgs:
        print("📭 No messages yet.")
        return

    shown = all_msgs[-limit:]
    print(f"📋 Conversation history ({len(shown)} of {len(all_msgs)} messages):\n")
    for direction, msg in shown:
        print(f"  [{msg['timestamp'][:19]}] {direction} ({msg['type']})")
        print(f"   ID: {msg['id']}  Thread: {msg.get('thread','-')}")
        body = msg['body'][:150]
        print(f"   {body}{'...' if len(msg['body']) > 150 else ''}")
        if msg.get("reply_to"):
            print(f"   ↩ reply to: {msg['reply_to']}")
        print()


def cmd_archive(msg_id):
    """Move a message (and its reply) to archive."""
    found = False
    for folder in [TO_CODEX, TO_CLAUDE]:
        for f in list_messages(folder):
            msg = read_message(f)
            if msg["id"] == msg_id:
                move_to_archive(f)
                print(f"📁 Archived: {msg_id}")
                found = True
            if msg.get("reply_to") == msg_id:
                move_to_archive(f)
                print(f"📁 Archived reply: {msg['id']}")
    if not found:
        print(f"❌ Message not found: {msg_id}")


def cmd_claude_listen(thread=None, poll_interval=3):
    """Long-running listener mode: check for Codex messages and print them.
    Press Ctrl+C to stop."""
    print(f"👂 Claude is listening for Codex messages...")
    print(f"   Inbox:  {TO_CLAUDE}")
    print(f"   Outbox: {TO_CODEX}")
    print(f"   Press Ctrl+C to stop.\n")

    seen = set()
    for f in list_messages(TO_CLAUDE):
        seen.add(os.path.basename(f))

    try:
        while True:
            files = list_messages(TO_CLAUDE)
            for f in files:
                fname = os.path.basename(f)
                if fname not in seen:
                    msg = read_message(f)
                    if thread and msg.get("thread") != thread:
                        seen.add(fname)
                        continue
                    print(f"\n📬 [{msg['timestamp'][:19]}] Codex → Claude")
                    _print_message(msg)
                    seen.add(fname)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n👋 Stopped listening.")


# ── Helpers ─────────────────────────────────────────────────────────

def _print_message(msg):
    """Pretty-print a message."""
    print(f"   From:    {msg['from']}")
    print(f"   Type:    {msg['type']}")
    print(f"   Thread:  {msg.get('thread', '-')}")
    print(f"   ID:      {msg['id']}")
    if msg.get("reply_to"):
        print(f"   ReplyTo: {msg['reply_to']}")
    print(f"   Body:")
    for line in msg["body"].strip().split("\n"):
        print(f"     {line}")
    if msg.get("attachments"):
        print(f"   Attachments: {', '.join(msg['attachments'])}")
    print()


def _log(action, msg):
    """Append a log entry."""
    ensure_dirs()
    log_path = os.path.join(LOGS, "bridge.log")
    entry = {
        "action": action,
        "msg_id": msg["id"],
        "thread": msg.get("thread", ""),
        "type": msg.get("type", ""),
        "timestamp": now_iso()
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── CLI ─────────────────────────────────────────────────────────────

def print_usage():
    print("""
╔══════════════════════════════════════════════════════╗
║        Claude ↔ Codex  File Bridge                   ║
╚══════════════════════════════════════════════════════╝

Commands:
  send <body>                  Send a task/message to Codex
  check                        Check for new replies from Codex
  wait                         Wait (poll) until Codex replies
  ask <body>                   Send + wait for reply (one-shot)
  history                      Show recent conversation
  listen                       Keep listening for Codex messages
  archive <msg_id>             Archive a message

Options:
  --thread <name>              Conversation thread (default: "default")
  --type <type>                Message type (default: "task")
                                  task | question | clarification | done
  --reply-to <msg_id>          Reply to a specific message
  --attach <file1,file2>       Attach shared files
  --timeout <seconds>          Wait timeout (default: 300)
  --remove                     Remove messages from inbox after reading

Examples:
  python3 bridge.py send "Run the hyperparameter sweep" --thread camp_exp
  python3 bridge.py wait --thread camp_exp --timeout 600
  python3 bridge.py ask "Which optimizer should I use?" --thread camp_exp
  python3 bridge.py check --remove
  python3 bridge.py listen --thread camp_exp
  python3 bridge.py history --thread camp_exp
""")


def parse_args(argv):
    """Simple arg parser (no external deps needed)."""
    args = {"thread": "default", "type": "task", "timeout": 300,
            "reply_to": None, "attachments": None, "remove": False}
    cmd = None
    body_parts = []

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("send", "check", "wait", "ask", "history", "listen", "archive", "help"):
            cmd = a
        elif a == "--thread" and i + 1 < len(argv):
            i += 1
            args["thread"] = argv[i]
        elif a == "--type" and i + 1 < len(argv):
            i += 1
            args["type"] = argv[i]
        elif a == "--reply-to" and i + 1 < len(argv):
            i += 1
            args["reply_to"] = argv[i]
        elif a == "--attach" and i + 1 < len(argv):
            i += 1
            args["attachments"] = argv[i].split(",")
        elif a == "--timeout" and i + 1 < len(argv):
            i += 1
            args["timeout"] = int(argv[i])
        elif a == "--remove":
            args["remove"] = True
        elif not a.startswith("--"):
            body_parts.append(a)
        i += 1

    body = " ".join(body_parts)
    return cmd, body, args


def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        print_usage()
        return

    cmd, body, opts = parse_args(sys.argv[1:])

    if cmd == "send":
        cmd_send(body, thread=opts["thread"], msg_type=opts["type"],
                 reply_to=opts["reply_to"], attachments=opts["attachments"])

    elif cmd == "check":
        cmd_check(thread=opts["thread"], remove_after_read=opts["remove"])

    elif cmd == "wait":
        cmd_wait(thread=opts["thread"], timeout=opts["timeout"])

    elif cmd == "ask":
        cmd_ask(body, thread=opts["thread"])

    elif cmd == "history":
        cmd_history(thread=opts["thread"])

    elif cmd == "listen":
        cmd_claude_listen(thread=opts["thread"])

    elif cmd == "archive":
        cmd_archive(body)

    elif cmd == "help":
        print_usage()

    else:
        print(f"❌ Unknown command: {cmd}")
        print_usage()


if __name__ == "__main__":
    main()
