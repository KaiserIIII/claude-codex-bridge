"""
Codex Bridge Agent — 给 Codex 端用的桥接脚本
=============================================

这个脚本是给 Codex 那边运行的。把它复制到 Codex 能访问的地方，
在 Codex 的终端中运行。它会：
  1. 监听 to-codex/ 目录，发现 Claude 发来的消息
  2. 处理任务（用户告诉 Codex "处理 bridge 消息"）
  3. 把结果写回 to-claude/ 目录

这个脚本不自动执行AI任务——它只是帮 Codex 读消息、展示消息、
和写回复。实际工作由用户告诉 Codex 来做。

推荐工作流：
  在 Codex 中打开 F:\TEST\claude-codex-bridge\ 作为工作目录，
  然后对 Codex 说：
    "检查 to-codex 文件夹里的 JSON 消息，按消息内容工作，
     把结果写成 JSON 回复放到 to-claude 文件夹。

使用方式：
  python3 codex_bridge.py inbox     ← 查看 Codex 收到的消息
  python3 codex_bridge.py read <id> ← 读取某条消息的完整内容
  python3 codex_bridge.py reply <id> "做了..." ← 回复一条消息
  python3 codex_bridge.py result <id> <result_file> "实验结果在..." ← 带附件的回复
  python3 codex_bridge.py done <id> "已完成" ← 标记任务完成
  python3 codex_bridge.py listen     ← 持续监听新消息
  python3 codex_bridge.py ask <body> ← 主动向 Claude 提问
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


def now_iso():
    return datetime.now(HKT).isoformat()


def make_id():
    return f"msg_{datetime.now(HKT).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def list_inbox():
    files = sorted([f for f in os.listdir(TO_CODEX) if f.endswith(".json")])
    return [os.path.join(TO_CODEX, f) for f in files]


def read_msg(fpath):
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_reply(reply_to, body, msg_type="result", attachments=None):
    msg = {
        "id": make_id(),
        "from": "codex",
        "to": "claude",
        "type": msg_type,
        "reply_to": reply_to,
        "thread": "default",
        "body": body,
        "attachments": attachments or [],
        "timestamp": now_iso()
    }
    # Carry thread from original message
    if reply_to:
        for f in list_inbox():
            orig = read_msg(f)
            if orig["id"] == reply_to:
                msg["thread"] = orig.get("thread", "default")
                break
    path = os.path.join(TO_CLAUDE, f"{msg['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    return msg, path


def cmd_inbox():
    files = list_inbox()
    if not files:
        print("📭 No messages from Claude.")
        return
    print(f"📬 {len(files)} message(s) from Claude:\n")
    for fpath in files:
        msg = read_msg(fpath)
        body_preview = msg["body"][:120]
        print(f"  [{msg['id']}] {msg['type']}")
        print(f"    Thread: {msg.get('thread','-')}")
        print(f"    Body:   {body_preview}{'...' if len(msg['body'])>120 else ''}")
        print()


def cmd_read(msg_id):
    for f in list_inbox():
        msg = read_msg(f)
        if msg["id"] == msg_id:
            print(json.dumps(msg, ensure_ascii=False, indent=2))
            return msg
    print(f"❌ Message not found: {msg_id}")
    return None


def cmd_reply(reply_to, body, msg_type="result"):
    msg, path = write_reply(reply_to, body, msg_type)
    print(f"✅ Reply sent to Claude:")
    print(f"   ID:      {msg['id']}")
    print(f"   Type:    {msg_type}")
    print(f"   ReplyTo: {reply_to}")
    print(f"   Body:    {body[:120]}{'...' if len(body)>120 else ''}")
    print(f"   File:    {path}")


def cmd_listen(poll_interval=3):
    print(f"👂 Codex is listening for Claude messages...")
    print(f"   Inbox:  {TO_CODEX}")
    print(f"   Outbox: {TO_CLAUDE}")
    print(f"   Press Ctrl+C to stop.\n")

    seen = set()
    for f in list_inbox():
        seen.add(os.path.basename(f))

    try:
        while True:
            files = list_inbox()
            for f in files:
                fname = os.path.basename(f)
                if fname not in seen:
                    msg = read_msg(f)
                    seen.add(fname)
                    print(f"\n{'='*60}")
                    print(f"📬 New message from Claude!")
                    print(f"   ID:      {msg['id']}")
                    print(f"   Type:    {msg['type']}")
                    print(f"   Thread:  {msg.get('thread','-')}")
                    if msg.get("reply_to"):
                        print(f"   ReplyTo: {msg['reply_to']}")
                    print(f"   Attachments: {msg.get('attachments', [])}")
                    print(f"{'='*60}")
                    print(msg["body"])
                    print(f"{'='*60}\n")
                    print(f"   → Reply with: python3 codex_bridge.py reply {msg['id']} \"your response\"")
                    print()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n👋 Stopped listening.")


def cmd_ask(body, thread="default"):
    msg = {
        "id": make_id(),
        "from": "codex",
        "to": "claude",
        "type": "question",
        "reply_to": None,
        "thread": thread,
        "body": body,
        "attachments": [],
        "timestamp": now_iso()
    }
    path = os.path.join(TO_CLAUDE, f"{msg['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    print(f"✅ Question sent to Claude: {msg['id']}")


def main():
    if len(sys.argv) < 2:
        print("Codex Bridge Agent")
        print("  inbox                List messages from Claude")
        print("  read <id>            Read a specific message")
        print("  reply <id> <body>    Reply to Claude (result type)")
        print("  done <id> <body>     Mark task as done")
        print("  result <id> <file> <body>  Reply with file attachment")
        print("  listen               Watch for new messages")
        print("  ask <body>           Send question to Claude")
        return

    cmd = sys.argv[1]

    if cmd == "inbox":
        cmd_inbox()
    elif cmd == "read" and len(sys.argv) >= 3:
        cmd_read(sys.argv[2])
    elif cmd == "reply" and len(sys.argv) >= 4:
        cmd_reply(sys.argv[2], " ".join(sys.argv[3:]), "result")
    elif cmd == "done" and len(sys.argv) >= 4:
        cmd_reply(sys.argv[2], " ".join(sys.argv[3:]), "done")
    elif cmd == "result" and len(sys.argv) >= 5:
        cmd_reply(sys.argv[2], " ".join(sys.argv[4:]), "result",
                  attachments=[sys.argv[3]])
    elif cmd == "listen":
        cmd_listen()
    elif cmd == "ask" and len(sys.argv) >= 3:
        cmd_ask(" ".join(sys.argv[2:]))
    else:
        print(f"❌ Unknown command or missing arguments: {cmd}")


if __name__ == "__main__":
    main()
