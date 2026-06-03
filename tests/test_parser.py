import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from parser import parse_transcript  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.jsonl")


class TestParseTranscript(unittest.TestCase):
    def setUp(self):
        self.result = parse_transcript(FIXTURE)
        self.items = self.result["items"]

    def test_returns_dict_with_items(self):
        self.assertIsInstance(self.result, dict)
        self.assertIn("items", self.result)
        self.assertIsInstance(self.items, list)

    def test_item_count_skips_noise(self):
        # user text, user command, assistant A, assistant B = 4.
        # sidechain, meta, attachment, malformed line, and the empty-thinking
        # assistant (msg_C) all produce no items.
        self.assertEqual(len(self.items), 4)

    def test_first_item_user_text(self):
        it = self.items[0]
        self.assertEqual(it["role"], "user")
        self.assertEqual(it["kind"], "text")
        self.assertIn("Look at this file", it["text"])

    def test_second_item_user_command(self):
        it = self.items[1]
        self.assertEqual(it["role"], "user")
        self.assertEqual(it["kind"], "command")
        self.assertEqual(it["command"], "/deploy")

    def test_assistant_blocks_grouped_by_message_id(self):
        it = self.items[2]
        self.assertEqual(it["role"], "assistant")
        types = [b["type"] for b in it["blocks"]]
        self.assertEqual(types, ["thinking", "text", "tool_use"])

    def test_thinking_text_preserved(self):
        block = self.items[2]["blocks"][0]
        self.assertEqual(block["type"], "thinking")
        self.assertEqual(block["text"].strip(), "Let me think.")

    def test_assistant_text_preserved(self):
        block = self.items[2]["blocks"][1]
        self.assertEqual(block["type"], "text")
        self.assertEqual(block["text"], "Hello **world**")

    def test_tool_use_resolved_with_result(self):
        block = self.items[2]["blocks"][2]
        self.assertEqual(block["type"], "tool_use")
        self.assertEqual(block["name"], "Read")
        self.assertEqual(block["input"]["file_path"], "/x")
        self.assertIn("file contents here", block["result"])

    def test_empty_thinking_message_dropped(self):
        # msg_C had only a whitespace thinking block -> no item emitted.
        for it in self.items:
            if it["role"] == "assistant":
                for b in it["blocks"]:
                    self.assertNotEqual(b.get("text", "x").strip(), "")

    def test_last_item_assistant_done(self):
        it = self.items[3]
        self.assertEqual(it["role"], "assistant")
        self.assertEqual(it["blocks"][0]["type"], "text")
        self.assertEqual(it["blocks"][0]["text"], "Done.")

    def test_sidechain_excluded(self):
        joined = repr(self.items)
        self.assertNotIn("secret subagent", joined)

    def test_meta_excluded(self):
        joined = repr(self.items)
        self.assertNotIn("meta noise", joined)

    def test_malformed_line_does_not_crash(self):
        # If we got here with 4 items, the BROKEN line was skipped cleanly.
        self.assertEqual(len(self.items), 4)

    def test_accepts_list_of_lines(self):
        with open(FIXTURE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        result = parse_transcript(lines)
        self.assertEqual(len(result["items"]), 4)

    def test_large_block_truncated(self):
        big = "x" * 50000
        line = (
            '{"type":"assistant","message":{"id":"big","role":"assistant",'
            '"content":[{"type":"text","text":"' + big + '"}]}}'
        )
        result = parse_transcript([line])
        text = result["items"][0]["blocks"][0]["text"]
        self.assertLess(len(text), 20000)
        self.assertIn("truncated", text)


if __name__ == "__main__":
    unittest.main()
