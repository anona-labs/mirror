// Mirror client: fetch the parsed conversation, render it, live-update on SSE.
// All content here is the user's own local transcript, served from localhost.

const conversation = document.getElementById("conversation");
const statusText = document.getElementById("status-text");
const dot = document.getElementById("dot");

let lastVersion = null;

function setStatus(state, text) {
  dot.className = "dot " + state;
  statusText.textContent = text;
}

function nearBottom() {
  const slack = 120;
  return window.innerHeight + window.scrollY >= document.body.scrollHeight - slack;
}

function md(text) {
  try {
    return marked.parse(text || "");
  } catch (e) {
    const pre = document.createElement("pre");
    pre.textContent = text || "";
    return pre.outerHTML;
  }
}

function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function renderUser(item, showRole) {
  const wrap = el("article", "msg user" + (showRole ? "" : " cont"));
  if (item.kind === "command") {
    wrap.appendChild(el("div", "command-chip", "&#47;" + escapeText(item.command.replace(/^\//, ""))));
  } else {
    if (showRole) wrap.appendChild(el("div", "role", "You"));
    wrap.appendChild(el("div", "bubble", md(item.text)));
  }
  return wrap;
}

function renderToolUse(block) {
  const details = el("details", "tool");
  const summary = el("summary", "tool-summary");
  summary.innerHTML =
    '<span class="tool-name">' + escapeText(block.name) + "</span>";
  details.appendChild(summary);

  const body = el("div", "tool-body");
  const input = el("div", "tool-input");
  input.appendChild(el("div", "tool-label", "input"));
  const pre = el("pre");
  const code = el("code");
  code.textContent = safeJson(block.input);
  pre.appendChild(code);
  input.appendChild(pre);
  body.appendChild(input);

  if (block.result !== null && block.result !== undefined && block.result !== "") {
    const out = el("div", "tool-result");
    out.appendChild(el("div", "tool-label", "result"));
    const rpre = el("pre");
    const rcode = el("code");
    rcode.textContent = block.result;
    rpre.appendChild(rcode);
    out.appendChild(rpre);
    body.appendChild(out);
  }
  details.appendChild(body);
  return details;
}

function renderAssistant(item, showRole) {
  const wrap = el("article", "msg assistant" + (showRole ? "" : " cont"));
  if (showRole) wrap.appendChild(el("div", "role", "Claude"));
  item.blocks.forEach((block) => {
    if (block.type === "text") {
      wrap.appendChild(el("div", "bubble", md(block.text)));
    } else if (block.type === "thinking") {
      const d = el("details", "thinking");
      d.appendChild(el("summary", "thinking-summary", "thinking"));
      d.appendChild(el("div", "thinking-body", md(block.text)));
      wrap.appendChild(d);
    } else if (block.type === "tool_use") {
      wrap.appendChild(renderToolUse(block));
    }
  });
  return wrap;
}

function render(data) {
  const items = data.items || [];
  conversation.innerHTML = "";
  if (items.length === 0) {
    conversation.appendChild(el("div", "empty", "Waiting for the conversation&hellip;"));
    return;
  }
  let prevRole = null;
  items.forEach((item) => {
    const showRole = item.role !== prevRole;
    conversation.appendChild(
      item.role === "user" ? renderUser(item, showRole) : renderAssistant(item, showRole)
    );
    prevRole = item.role;
  });
  conversation.querySelectorAll("pre code").forEach((node) => {
    try {
      hljs.highlightElement(node);
    } catch (e) {
      /* ignore highlight failures */
    }
  });
}

async function load(force) {
  try {
    const resp = await fetch("/api/conversation", { cache: "no-store" });
    const data = await resp.json();
    if (!force && data.version === lastVersion) return;
    const stick = nearBottom();
    lastVersion = data.version;
    render(data);
    if (stick) window.scrollTo(0, document.body.scrollHeight);
    setStatus("live", "live");
  } catch (e) {
    setStatus("off", "disconnected");
  }
}

function connect() {
  const es = new EventSource("/events");
  es.onopen = () => setStatus("live", "live");
  es.onmessage = () => load(false);
  es.onerror = () => {
    setStatus("off", "reconnecting&hellip;");
  };
}

function safeJson(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch (e) {
    return String(value);
  }
}

function escapeText(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

load(true);
connect();
