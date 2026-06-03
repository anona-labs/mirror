"""Parse a Claude Code transcript .jsonl into a render-ready conversation model.

The on-disk transcript is line-delimited JSON. Each line has a top-level ``type``.
Only ``user`` and ``assistant`` lines carry conversation content; everything else
(attachments, snapshots, mode changes, ai-title, etc.) is ignored.

The real message lives under ``line["message"]`` with ``role`` and ``content``.
See state-learnings.md for the format details this relies on.
"""

import json

# Cap any single rendered block payload so the JSON we ship to the browser stays
# small even when a tool dumps a huge result. Full fidelity is a non-goal for v1.
MAX_BLOCK_CHARS = 10000


def _truncate(text):
    if text is None:
        return ""
    if len(text) <= MAX_BLOCK_CHARS:
        return text
    omitted = len(text) - MAX_BLOCK_CHARS
    return text[:MAX_BLOCK_CHARS] + "\n... [truncated %d chars]" % omitted


def _iter_lines(source):
    """Accept a file path (str) or an iterable of raw JSON line strings."""
    if isinstance(source, str):
        with open(source, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                yield line
    else:
        for line in source:
            yield line


def _parse_line(line):
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except (ValueError, TypeError):
        # Defensive: a single corrupt/partial line must never break the view.
        return None


def _result_to_text(content):
    """A tool_result's ``content`` is a string or a list of sub-blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for sub in content:
            if not isinstance(sub, dict):
                continue
            if isinstance(sub.get("text"), str):
                parts.append(sub["text"])
            elif sub.get("type") == "tool_reference" and sub.get("tool_name"):
                parts.append("[tool: %s]" % sub["tool_name"])
        return "\n".join(parts)
    return ""


def _command_name(text):
    """Extract the slash command from a ``<command-name>...`` wrapped string."""
    open_tag = "<command-name>"
    close_tag = "</command-name>"
    start = text.find(open_tag)
    if start == -1:
        return None
    start += len(open_tag)
    end = text.find(close_tag, start)
    if end == -1:
        return None
    return text[start:end].strip()


def parse_transcript(source):
    """Return ``{"items": [...]}`` where each item is one user or assistant turn.

    Assistant turns are reconstructed by grouping consecutive assistant lines that
    share the same ``message.id`` (streaming splits one turn across several lines).
    tool_result lines are folded onto the matching tool_use block rather than
    becoming their own item.
    """
    items = []
    tool_uses_by_id = {}

    pending = None  # in-progress assistant item being assembled
    pending_id = None

    def flush():
        nonlocal pending, pending_id
        if pending is not None:
            if pending["blocks"]:
                items.append(pending)
            pending = None
            pending_id = None

    for raw in _iter_lines(source):
        obj = _parse_line(raw)
        if obj is None:
            continue

        ltype = obj.get("type")
        if ltype not in ("user", "assistant"):
            continue
        if obj.get("isSidechain") or obj.get("isMeta"):
            continue

        message = obj.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")

        if ltype == "assistant":
            msg_id = message.get("id")
            if pending is not None and msg_id != pending_id:
                flush()
            if pending is None:
                pending = {"role": "assistant", "blocks": []}
                pending_id = msg_id
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "thinking":
                        text = block.get("thinking", "")
                        if text and text.strip():
                            pending["blocks"].append(
                                {"type": "thinking", "text": _truncate(text)}
                            )
                    elif btype == "text":
                        text = block.get("text", "")
                        if text and text.strip():
                            pending["blocks"].append(
                                {"type": "text", "text": _truncate(text)}
                            )
                    elif btype == "tool_use":
                        tb = {
                            "type": "tool_use",
                            "id": block.get("id"),
                            "name": block.get("name", "tool"),
                            "input": block.get("input", {}),
                            "result": None,
                        }
                        pending["blocks"].append(tb)
                        if tb["id"]:
                            tool_uses_by_id[tb["id"]] = tb
            continue

        # ltype == "user": flush any pending assistant turn first.
        flush()

        if isinstance(content, str):
            cmd = _command_name(content)
            if cmd:
                items.append({"role": "user", "kind": "command", "command": cmd})
            else:
                items.append(
                    {"role": "user", "kind": "text", "text": _truncate(content)}
                )
        elif isinstance(content, list):
            # Resolve tool_result blocks onto their originating tool_use.
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    tid = block.get("tool_use_id")
                    text = _truncate(_result_to_text(block.get("content")))
                    tb = tool_uses_by_id.get(tid)
                    if tb is not None:
                        tb["result"] = text

    flush()
    return {"items": items}
