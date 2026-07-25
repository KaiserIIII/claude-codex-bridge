"""
Auto Bridge Daemon — 全自动轮询守护进程
=======================================

管理 Claude ↔ Codex 之间的自动对话循环。

工作原理：
  1. init     → 发送初始任务，开始对话
  2. tick     → 检查 Codex 是否有新回复，有则打印出来
  3. reply    → Claude 的回复发过去
  4. done     → Claude 说"我这边的活干完了"
  5. status   → 查看当前对话状态

停止协议：
  - 任一方发送 type="done"，表示自己这边的活干完了
  - 对方如果也回复 done，双方 done → 自动停止
  - 对方如果回复 task/question，对话继续（有后续工作）

状态文件 state.json（在 bridge 根目录）：
  {
    "active": true,
    "thread": "camp_exp",
    "phase": "waiting_for_codex",    // or "waiting_for_claude", "both_done"
    "claude_done": false,
    "codex_done": false,
    "last_msg_id": "msg_xxx",
    "message_count": 5,
    "started_at": "2026-07-26T...",
    "last_activity": "2026-07-26T..."
  }
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta

HKT = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TO_CODEX = os.path.join(BASE_DIR, "to-codex")
TO_CLAUDE = os.path.join(BASE_DIR, "to-claude")
SHARED = os.path.join(BASE_DIR, "shared")
STATE_FILE = os.path.join(BASE_DIR, "state.json")


def now_iso():
    return datetime.now(HKT).isoformat()


def make_id():
    return f"msg_{datetime.now(HKT).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


# ── State management ────────────────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def init_state(thread, initial_task):
    return {
        "active": True,
        "thread": thread,
        "phase": "waiting_for_codex",
        "claude_done": False,
        "codex_done": False,
        "last_msg_id": None,
        "message_count": 0,
        "started_at": now_iso(),
        "last_activity": now_iso(),
        "initial_task": initial_task[:200]
    }


# ── Message I/O ─────────────────────────────────────────────────────

def list_new_messages(folder, since_id=None):
    """Return messages newer than since_id (by file ordering)."""
    if not os.path.isdir(folder):
        return []
    files = sorted([f for f in os.listdir(folder) if f.endswith(".json")])
    msgs = []
    for fname in files:
        fpath = os.path.join(folder, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                msg = json.load(f)
        except json.JSONDecodeError:
            # Retry with BOM handling (files written from Windows)
            with open(fpath, "r", encoding="utf-8-sig") as f:
                msg = json.load(f)
        if since_id is None or msg["id"] > since_id:
            msgs.append((fpath, msg))
    return msgs


def send_message(to_folder, body, thread, msg_type="task", reply_to=None, attachments=None):
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
    path = os.path.join(to_folder, f"{msg['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    return msg, path


# ── Core loop logic ─────────────────────────────────────────────────

def cmd_init(thread, body):
    """Start a new conversation thread."""
    existing = load_state()
    if existing and existing.get("active"):
        print(f"⚠️  Already have an active conversation (thread: {existing['thread']}).")
        print(f"   Use 'reset' to clear or 'tick' to continue.")
        return

    msg, path = send_message(TO_CODEX, body, thread, msg_type="task")
    state = init_state(thread, body)
    state["last_msg_id"] = msg["id"]
    state["message_count"] = 1
    save_state(state)

    print(f"🚀 Auto bridge started!")
    print(f"   Thread:  {thread}")
    print(f"   Task:    {body[:150]}{'...' if len(body) > 150 else ''}")
    print(f"   Phase:   waiting_for_codex")
    print(f"   Message: {msg['id']}")
    print()
    print(f"   → Codex should now pick up the task from to-codex/")
    print(f"   → Run 'python3 auto_daemon.py tick' to check for replies")


def cmd_tick(quiet=False):
    """Check for new messages from Codex. Update state. Return what happened."""
    state = load_state()
    if not state or not state.get("active"):
        if not quiet:
            print("📭 No active conversation. Use 'init <thread> <task>' to start.")
        return {"action": "none", "state": state}

    # Check for new messages from Codex
    new_msgs = list_new_messages(TO_CLAUDE, since_id=state.get("last_codex_id"))
    # Also update our tracking of our own sent messages
    our_new = list_new_messages(TO_CODEX, since_id=state.get("last_msg_id"))
    if our_new:
        state["last_msg_id"] = our_new[-1][1]["id"]

    if not new_msgs:
        if not quiet:
            print(f"⏳ Waiting for Codex... (phase: {state['phase']}, msgs: {state['message_count']})")
            print(f"   Last activity: {state.get('last_activity', 'unknown')}")
        save_state(state)
        return {"action": "waiting", "state": state}

    # Process new messages
    results = []
    for fpath, msg in new_msgs:
        state["last_codex_id"] = msg["id"]
        state["message_count"] += 1
        state["last_activity"] = now_iso()

        if not quiet:
            print(f"\n{'='*60}")
            print(f"📬 Codex replied!")
            print(f"{'='*60}")
            print(f"   ID:       {msg['id']}")
            print(f"   Type:     {msg['type']}")
            print(f"   ReplyTo:  {msg.get('reply_to', '-')}")
            if msg.get("attachments"):
                print(f"   Files:    {', '.join(msg['attachments'])}")
            print(f"{'='*60}")
            print(msg["body"])
            print(f"{'='*60}")

        # Check done protocol
        if msg["type"] == "done":
            state["codex_done"] = True
            if not quiet:
                print(f"\n   ✅ Codex says DONE.")

        results.append(msg)

    # Determine new phase
    if state.get("claude_done") and state.get("codex_done"):
        state["phase"] = "both_done"
        state["active"] = False
        if not quiet:
            print(f"\n   🎉 Both sides agree: WORK COMPLETE!")
            print(f"   Total messages: {state['message_count']}")
            print(f"   Started: {state['started_at']}")
            print(f"   Ended:   {now_iso()}")
    elif state.get("codex_done"):
        state["phase"] = "waiting_for_claude"
        if not quiet:
            print(f"\n   💡 Codex is done. Claude, your turn to confirm or continue.")
            print(f"   → 'python3 auto_daemon.py done' to confirm finish")
            print(f"   → 'python3 auto_daemon.py reply \"...\"' to continue")
    else:
        state["phase"] = "waiting_for_claude"
        if not quiet:
            print(f"\n   💡 Your turn to reply.")
            print(f"   → 'python3 auto_daemon.py reply \"...\"' ")
            print(f"   → 'python3 auto_daemon.py done' if no more work needed")

    save_state(state)
    return {"action": "got_reply", "state": state, "messages": results}


def cmd_reply(body, msg_type="task"):
    """Claude sends a reply to Codex."""
    state = load_state()
    if not state:
        print("❌ No active conversation. Use 'init' first.")
        return

    reply_to = state.get("last_codex_id")
    msg, path = send_message(TO_CODEX, body, state["thread"], msg_type=msg_type,
                             reply_to=reply_to)
    state["last_msg_id"] = msg["id"]
    state["message_count"] += 1
    state["phase"] = "waiting_for_codex"
    state["last_activity"] = now_iso()
    # Sending a non-done message resets the done flags
    if msg_type != "done":
        state["claude_done"] = False
        state["codex_done"] = False
    save_state(state)

    print(f"✅ Reply sent to Codex: {msg['id']}")
    print(f"   Type:  {msg_type}")
    print(f"   Phase: waiting_for_codex")
    if msg_type == "done":
        print(f"   → Waiting for Codex to also say done...")


def cmd_claude_done():
    """Claude says it's done with its part."""
    state = load_state()
    if not state:
        print("❌ No active conversation.")
        return
    cmd_reply("Claude has completed its work. Confirming done.", msg_type="done")
    state["claude_done"] = True
    save_state(state)
    print(f"   Claude marked as done. Waiting for Codex confirmation...")


def cmd_status():
    """Show current conversation status."""
    state = load_state()
    if not state:
        print("📭 No active conversation.")
        return

    active_str = "🟢 ACTIVE" if state["active"] else "🔴 STOPPED"
    print(f"\n  Auto Bridge Status")
    print(f"  {'─'*40}")
    print(f"  Status:    {active_str}")
    print(f"  Thread:    {state['thread']}")
    print(f"  Phase:     {state['phase']}")
    print(f"  Messages:  {state['message_count']}")
    print(f"  Claude done: {'✅' if state.get('claude_done') else '⏳'}")
    print(f"  Codex done:  {'✅' if state.get('codex_done') else '⏳'}")
    print(f"  Started:   {state.get('started_at', '-')}")
    print(f"  Last act:  {state.get('last_activity', '-')}")
    print(f"  Task:      {state.get('initial_task', '-')[:100]}")
    print()

    # Show pending messages
    new = list_new_messages(TO_CLAUDE)
    if new:
        print(f"  📬 {len(new)} unread message(s) from Codex. Run 'tick' to process.")

    pending_codex = list_new_messages(TO_CODEX)
    if pending_codex:
        print(f"  📤 {len(pending_codex)} outgoing message(s) to Codex.")


def cmd_reset():
    """Reset the conversation state."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        print("🔄 Conversation reset.")
    else:
        print("📭 No active conversation.")


# ── CLI ─────────────────────────────────────────────────────────────

def print_usage():
    print("""
╔══════════════════════════════════════════════════════╗
║     Claude ↔ Codex  Auto Bridge Daemon               ║
╚══════════════════════════════════════════════════════╝

  init <thread> <task>        Start a new conversation
  tick                        Check for Codex replies
  reply "<message>"           Send reply to Codex
  done                        Claude says it's finished
  status                      Show conversation state
  reset                       Reset conversation

Done protocol:
  1. Either side sends type="done"
  2. Other side confirms with done → auto-stop
  3. If either sends non-done, conversation continues

Examples:
  python3 auto_daemon.py init camp_exp "Run hyperparameter sweep for CAMP MoE projector"
  python3 auto_daemon.py tick
  python3 auto_daemon.py reply "Good results. Now try with different initialization."
  python3 auto_daemon.py done
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        cmd_status()
        return

    cmd = sys.argv[1]

    if cmd == "init":
        if len(sys.argv) < 4:
            print("Usage: auto_daemon.py init <thread> <task>")
            return
        cmd_init(sys.argv[2], " ".join(sys.argv[3:]))

    elif cmd == "tick":
        cmd_tick()

    elif cmd == "reply":
        if len(sys.argv) < 3:
            print("Usage: auto_daemon.py reply \"<message>\"")
            return
        cmd_reply(" ".join(sys.argv[2:]))

    elif cmd == "done":
        cmd_claude_done()

    elif cmd == "status":
        cmd_status()

    elif cmd == "reset":
        cmd_reset()

    elif cmd == "help":
        print_usage()

    else:
        print(f"❌ Unknown command: {cmd}")
        print_usage()


if __name__ == "__main__":
    main()
