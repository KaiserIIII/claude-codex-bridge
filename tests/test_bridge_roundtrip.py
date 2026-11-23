"""Portable bridge regression tests: all files stay in a temporary directory."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import auto_daemon
import bridge
import codex_bridge


class BridgeRoundTripTests(unittest.TestCase):
    def test_all_entry_points_use_the_same_checkout_by_default(self):
        root = Path(__file__).resolve().parents[1]
        for module in (bridge, codex_bridge, auto_daemon):
            with self.subTest(module=module.__name__):
                self.assertEqual(Path(module.BASE_DIR).resolve(), root)

    def test_utf8_message_reply_preserves_thread_and_archives_on_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = {
                "TO_CODEX": str(root / "to-codex"),
                "TO_CLAUDE": str(root / "to-claude"),
                "SHARED": str(root / "shared"),
            }
            claude_dirs = {
                **dirs,
                "BASE_DIR": str(root),
                "ARCHIVE": str(root / "archive"),
                "LOGS": str(root / "logs"),
            }
            codex_dirs = {"BASE_DIR": str(root), **dirs}
            with patch.multiple(bridge, **claude_dirs), patch.multiple(codex_bridge, **codex_dirs):
                with contextlib.redirect_stdout(io.StringIO()):
                    sent = bridge.cmd_send("检查工程量计算", thread="cost-review")
                self.assertEqual(sent["from"], "claude")
                self.assertEqual(sent["thread"], "cost-review")
                self.assertEqual(len(codex_bridge.list_inbox()), 1)

                reply, reply_path = codex_bridge.write_reply(
                    sent["id"], "结果已验证", msg_type="result"
                )
                self.assertEqual(reply["reply_to"], sent["id"])
                self.assertEqual(reply["thread"], "cost-review")
                self.assertTrue(Path(reply_path).exists())

                with contextlib.redirect_stdout(io.StringIO()):
                    received = bridge.cmd_check(thread="cost-review", remove_after_read=True)
                self.assertEqual(len(received), 1)
                self.assertEqual(received[0][1]["body"], "结果已验证")
                self.assertFalse(Path(reply_path).exists())
                self.assertTrue((root / "archive" / f"{reply['id']}.json").exists())
                self.assertTrue((root / "logs" / "bridge.log").exists())

    def test_thread_filter_does_not_archive_unrelated_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = {
                "TO_CODEX": str(root / "to-codex"),
                "TO_CLAUDE": str(root / "to-claude"),
                "SHARED": str(root / "shared"),
            }
            with patch.multiple(
                bridge, BASE_DIR=str(root), ARCHIVE=str(root / "archive"),
                LOGS=str(root / "logs"), **dirs
            ), patch.multiple(codex_bridge, BASE_DIR=str(root), **dirs):
                with contextlib.redirect_stdout(io.StringIO()):
                    a = bridge.cmd_send("Task A", thread="a")
                    b = bridge.cmd_send("Task B", thread="b")
                reply_a, path_a = codex_bridge.write_reply(a["id"], "A result")
                reply_b, path_b = codex_bridge.write_reply(b["id"], "B result")
                with contextlib.redirect_stdout(io.StringIO()):
                    received = bridge.cmd_check(thread="a", remove_after_read=True)
                self.assertEqual([item[1]["id"] for item in received], [reply_a["id"]])
                self.assertFalse(Path(path_a).exists())
                self.assertTrue(Path(path_b).exists())
                self.assertEqual(reply_b["thread"], "b")


if __name__ == "__main__":
    unittest.main()
