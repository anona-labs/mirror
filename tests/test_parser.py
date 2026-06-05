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


class TestImages(unittest.TestCase):
    def _line(self, obj):
        import json
        return json.dumps(obj)

    def test_user_pasted_image_with_text(self):
        line = self._line({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "text", "text": "look at this"},
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": "aGVsbG8="}},
            ]},
        })
        items = parse_transcript([line])["items"]
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["role"], "user")
        self.assertIn("look at this", it["text"])
        self.assertEqual(len(it["images"]), 1)
        self.assertEqual(it["images"][0]["media_type"], "image/png")
        self.assertEqual(it["images"][0]["data"], "aGVsbG8=")

    def test_user_image_only(self):
        line = self._line({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg", "data": "Zm9v"}},
            ]},
        })
        items = parse_transcript([line])["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["images"][0]["media_type"], "image/jpeg")
        self.assertEqual(items[0]["text"], "")

    def test_tool_result_image_attached_to_tool_use(self):
        a = self._line({
            "type": "assistant",
            "message": {"id": "m1", "role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Screenshot", "input": {}},
            ]},
        })
        u = self._line({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": [
                    {"type": "text", "text": "captured"},
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": "aGVsbG8="}},
                ]},
            ]},
        })
        items = parse_transcript([a, u])["items"]
        self.assertEqual(len(items), 1)
        block = items[0]["blocks"][0]
        self.assertEqual(block["type"], "tool_use")
        self.assertIn("captured", block["result"])
        self.assertEqual(len(block["result_images"]), 1)
        self.assertEqual(block["result_images"][0]["data"], "aGVsbG8=")

    def test_oversized_image_becomes_placeholder(self):
        big = "A" * 2_000_001
        line = self._line({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": big}},
            ]},
        })
        items = parse_transcript([line])["items"]
        img = items[0]["images"][0]
        self.assertTrue(img.get("omitted"))
        self.assertNotIn("data", img)

    def test_text_only_user_list_still_emits_item(self):
        # A user message that arrives as a list with only text (no tool_result)
        # must still produce a user item (previously dropped).
        line = self._line({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "text", "text": "just text in a list"},
            ]},
        })
        items = parse_transcript([line])["items"]
        self.assertEqual(len(items), 1)
        self.assertIn("just text in a list", items[0]["text"])
        self.assertNotIn("images", items[0])


if __name__ == "__main__":
    unittest.main()
