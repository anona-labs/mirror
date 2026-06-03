# Pane - Roadmap

> Working title: **Pane** (a window pane for your AI conversations). Placeholder, rename later.

A live, nicely-styled HTML mirror of your coding-agent session. You keep chatting in the
terminal; Pane prints a link, and that link shows the conversation as an evolving, readable
document instead of scrollback. No paid API calls. It renders the transcript your agent
already writes, so it rides on your existing Claude Code / Codex subscription.

---

## Guiding principles

These constrain every version. When a feature violates one, it does not ship.

1. **No paid API calls.** Pane never calls an LLM API itself. Rendering is local code over the
   transcript the agent already produces. Any model output (e.g. structured artifacts) comes
   from the user's existing subscription session, never a separate billed key.
2. **Local-first, privacy-first.** Transcripts contain secrets, file contents, and tool output.
   The server binds to `127.0.0.1` only. Nothing leaves the machine until the user explicitly
   publishes, and publishing is snapshot-based and redactable, never a raw live leak.
3. **Low install friction.** Clone and go. Minimal or zero runtime dependencies. Prefer a single
   self-contained script over a package tree.
4. **Open core.** The local engine is free and open source forever (drives adoption). The paid
   layer is hosted convenience: public sharing, team workspaces, storage, custom domains.
5. **Tool-agnostic core, thin adapters.** The renderer speaks one internal conversation format.
   Each agent (Claude Code, Codex, others) gets a small adapter that maps its transcript into
   that format. The core does not care which tool produced the session.
6. **Dumb server, smart client.** The server watches files and serves structured JSON plus a
   live-update stream. The browser client renders. This separation is what makes artifacts,
   sharing, and multi-tool support cheap to add later.

---

## Architecture (the spine across all versions)

```
agent session (Claude Code / Codex)
        |
        v  writes transcript JSONL (free, no tokens)
   [ adapter ]  parses transcript -> internal conversation model
        |
        v
   [ local server ]  127.0.0.1:<port>
     - serves conversation JSON
     - serves static client assets
     - SSE/websocket: pushes "updated" when the transcript changes
        |
        v
   [ browser client ]  renders markdown, code, tool calls, artifacts
     - listens for updates, re-renders, preserves scroll
```

- **Trigger:** a `Stop` hook (fires after each turn) hands the server the `transcript_path`. The
  server watches that file's mtime and pushes an update on change. A `SessionStart` hook starts
  the server if not already running and surfaces the link.
- **The link:** server binds a stable port (per project or per session), prints
  `Live view: http://localhost:<port>` to the terminal.
- **Why this is free:** the hook scripts and renderer are plain code. The only thing that costs
  subscription tokens is the normal conversation you were already having.

---

## v1 - Local live view (free, open source)

**Goal:** terminal stays exactly as it is, plus a localhost link that shows the conversation as a
clean, live-updating document.

**Features**
- Claude Code plugin packaging (hooks + scripts), one-command install.
- `SessionStart` hook starts the local server and prints the link.
- `Stop` hook reports the transcript path; server watches it and pushes updates.
- Transcript parser handling the core block types: user message, assistant text, tool call,
  tool result, thinking, images.
- Browser client: markdown rendering, syntax-highlighted code, collapsible tool calls and
  thinking blocks, auto-scroll, dark/light theme.
- Live reload via SSE (no flicker, scroll preserved). Falls back to meta-refresh if SSE fails.
- Single active session.

**Non-goals (explicitly out)**
- No auth, no public URL, no accounts.
- No structured artifacts beyond what the transcript already contains.
- No multi-session switching (note as v1.x).
- No persistence or export.

**Edge cases to handle**
- Port already in use: pick a stable free port and reuse it across restarts.
- Large transcripts: lazy-render or cap rendered history, load older on scroll.
- Server lifecycle: idempotent start, bound to localhost only, easy to kill.
- Secrets in transcript: localhost-only is the v1 mitigation. Document it clearly.

**Done when:** a new user installs the plugin, runs Claude Code as normal, sees a localhost link,
opens it, and watches the conversation update each turn with no extra cost and no config.

---

## v2 - Artifacts and sharing (commercial)

**Goal:** richer output than raw chat, and the ability to share a conversation or artifact at a
public link. This is the first version worth paying for. Open-core line: the local engine and the
artifact renderer stay open source; hosted sharing is the paid service.

### Structured artifacts
- A documented block protocol the model emits inside its normal (subscription) output, for
  example a fenced `artifact` block with a type and JSON payload, or an MCP tool the model calls.
- A plugin skill / instructions teach the model the format. Still zero API spend; it uses the
  session you already pay for.
- Practical artifact types people actually want: tables, charts (bar / line / pie), mermaid
  diagrams, code diffs, callout cards, checklists, image galleries, math.
- **Sandboxing:** once the page can render model-generated HTML/JS, isolate it. Start with an
  `iframe sandbox` (no same-origin, no top navigation). Only reach for a heavier sandbox
  (container / microVM such as smolvm) if you ever execute artifact code server-side. For
  client-rendered artifacts, the iframe is enough.

### Public sharing
- "Publish" takes a **snapshot** (or a single artifact), not the raw live session by default.
- **Redaction first:** secret scanning before publish, an allowlist of what gets shared, options
  to strip tool outputs and thinking. This must be solid before charging, since a leaked key in a
  public share is a reputational failure.
- Two paths:
  - DIY: self-host plus a tunnel (`cloudflared` / `ngrok`) for users who want zero dependence.
  - Hosted (the paid part): a relay that stores the snapshot and returns `share.pane.app/<id>`,
    with link expiry, password protection, and optional live-share (stream updates to viewers).

**Monetization (open core)**
- Free: local view (v1) plus a small number of public snapshots per month.
- Pro (monthly): unlimited shares, custom domain, password and expiry, premium themes and
  artifact types, live-share.

**Done when:** a user can turn a session into a clean shareable page in one action, with secrets
scrubbed, and pay for hosted sharing without ever touching an API key.

---

## v3 - The workspace (vision, grounded)

By now Pane is a universal, shareable viewer. v3 makes it a place you return to, not just a view
of the current session. Build these in the order users ask for them, not all at once.

- **Multi-session / project dashboard:** list all sessions, pin and organize, jump between them.
- **Tool-agnostic adapters in earnest:** Codex, Cursor, Aider, Gemini CLI, generic JSONL. Pane
  becomes the one viewer for any coding agent. This is the main differentiator if Anthropic ships
  its own first-party viewer.
- **Full-text search across history:** "did we solve this before?" across every past session.
- **Export:** PDF, Markdown, gist, blog-ready writeup. Turn a good session into something you can
  hand to a colleague.
- **Annotations and comments:** viewers comment on a shared conversation. First real
  collaboration surface, and the bridge to a team product.
- **Live co-watch:** teammates watch an agent work in real time. Useful for pairing, demos,
  teaching.

**What to validate before building all of it:** do users want a library (return-to value), or
just good one-off shares? Search and export are cheap to test demand for. Co-watch is expensive;
gate it on real pull.

---

## v4 - Team and interactive (vision, further out)

Still grounded in real demand, but bigger bets. Each needs validation, not faith.

- **Team workspaces:** org accounts, shared library, roles and permissions, SSO, retention
  policies, audit log. The enterprise tier.
- **Usage analytics:** cost and token trends, which tools and agents, where sessions fail. Teams
  managing agent spend will want this dashboard.
- **Templates and playbooks:** turn a strong conversation into a reusable, parameterized prompt
  others can run.
- **Interactive control (the big one):** the web view becomes an input surface. Approve tool
  calls, answer the agent's questions, send follow-ups from the browser or phone. "Drive your
  agent from the shared link." Real demand exists for remote approvals and mobile control, and it
  is the strongest moat here. Also the hardest to do safely; it crosses from viewer to controller,
  so security and auth must be mature first.
- **Knowledge base over your sessions:** ask questions across your whole agent history. Ties into
  search and export. Only worth it once there is a real corpus to query.
- **Integrations:** post a session summary to a GitHub PR, a Slack channel, or CI.

---

## Cross-cutting concerns (every version)

- **Security and privacy:** localhost-only until explicit publish; redaction before any share;
  bind and auth correctly the moment anything leaves the machine.
- **Performance:** large transcripts must not freeze the page. Lazy rendering, virtualization,
  bounded history.
- **Cross-platform:** macOS and Linux from v1.
- **Adapter resilience:** transcript formats and hook APIs will change. Keep the adapter layer
  thin and versioned so a format change does not break the core.

---

## Honest risks

- **Anthropic ships a native web view.** They already have a web app. Differentiation must be
  tool-agnostic support, sharing, artifacts, and team features, not "pretty viewer" alone.
- **Hook / transcript instability.** Mitigate with a thin, versioned adapter layer.
- **Secret leakage in public shares.** The single most damaging failure mode. Redaction must be
  proven before v2 charges anyone.
- **Scope creep in v3 and v4.** The local viewer is the wedge. Do not let workspace and team
  features delay a great, free, reliable v1.

---

## Sequence summary

| Version | Theme | Cost to user | Open / paid |
|---|---|---|---|
| v1 | Local live view | Free | Open source |
| v2 | Artifacts + public sharing | Free local, paid hosting | Open core |
| v3 | Workspace, search, multi-tool, export | Free + paid tiers | Open core |
| v4 | Team, analytics, interactive control | Paid (enterprise) | Open core + hosted |
