/*
 * OpenMolClaw local chat panel.
 *
 * Clean-room glue for the /api/chat endpoint in openmolclaw/app.py. Holds the
 * conversation history client-side (so a memory-only session keeps nothing on
 * the server), renders each turn, shows which local tools ran, renders any
 * structures the tools produced, and offers to load a structure back into the
 * Ketcher editor. It is NOT derived from any hosted product's chat UI.
 */
"use strict";

(function () {
  const byId = (id) => document.getElementById(id);
  const log = byId("chat-log");
  const form = byId("chat-form");
  const input = byId("chat-input");
  const sendBtn = byId("chat-send");
  const clearBtn = byId("chat-clear");
  const statusEl = byId("chat-status");

  if (!form || !log || !input) return; // panel not present

  // Provider-neutral conversation history: [{role, content}, ...].
  let history = [];
  const MAX_HISTORY = 20;

  function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("status--error", Boolean(isError));
  }

  function ketcher() {
    const frame = byId("ketcher-frame");
    try {
      return frame && frame.contentWindow ? frame.contentWindow.ketcher : null;
    } catch (_e) {
      return null;
    }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function addBubble(role, text) {
    const li = el("li", `chat-msg chat-msg--${role}`);
    const who = el("span", "chat-role", role === "user" ? "You" : "Assistant");
    const body = el("div", "chat-body", text);
    li.appendChild(who);
    li.appendChild(body);
    log.appendChild(li);
    log.scrollTop = log.scrollHeight;
    return li;
  }

  // Render tool trace (which local tools ran) as a compact, collapsible list.
  function addTrace(steps) {
    if (!steps || !steps.length) return;
    const details = el("details", "chat-trace");
    const summary = el(
      "summary",
      null,
      `Tools used (${steps.length}): ${steps.map((s) => s.tool_name).join(", ")}`
    );
    details.appendChild(summary);
    const ul = el("ul", "chat-trace-list");
    steps.forEach((s) => {
      const li = el("li");
      const status = s.ok ? "ok" : `error: ${s.error || s.error_type || "failed"}`;
      li.textContent = `${s.tool_name} — ${status}`;
      ul.appendChild(li);
    });
    details.appendChild(ul);
    log.appendChild(details);
    log.scrollTop = log.scrollHeight;
  }

  // Render any structures the tools produced, with a "Load into editor" action.
  function addStructures(deltas) {
    if (!deltas || !deltas.length) return;
    deltas.forEach((d) => {
      const wrap = el("div", "chat-structure");
      const head = el("div", "chat-structure-head");
      head.appendChild(el("span", "alias", d.alias || "structure"));
      if (d.smiles) head.appendChild(el("span", "smiles", d.smiles));
      wrap.appendChild(head);
      if (d.svg) {
        const svgWrap = el("div", "chat-structure-svg");
        svgWrap.innerHTML = d.svg; // server-produced RDKit SVG (local, trusted)
        wrap.appendChild(svgWrap);
      }
      if (d.smiles) {
        const loadBtn = el("button", "btn-secondary", "Load into editor");
        loadBtn.type = "button";
        loadBtn.addEventListener("click", () => loadIntoEditor(d.smiles));
        wrap.appendChild(loadBtn);
      }
      log.appendChild(wrap);
    });
    log.scrollTop = log.scrollHeight;
  }

  // Render deferred rdkit-agent tool results (execution_status ===
  // "deferred_external_tool") as an explicit card so the user can see
  // OpenMolClaw prepared, but did not run, the external command.
  function addDeferredCards(steps) {
    if (!steps || !steps.length) return;
    steps
      .filter((s) => s.ok && s.result && s.result.execution_status === "deferred_external_tool")
      .forEach((s) => {
        const r = s.result;
        const card = el("div", "chat-deferred-card");
        card.appendChild(
          el("div", "chat-deferred-head", `Deferred rdkit-agent request: ${r.external_command}`)
        );
        const cli = el("pre", "chat-deferred-cli", r.recommended_cli);
        card.appendChild(cli);
        if (r.provider_repo) {
          const link = document.createElement("a");
          link.href = r.provider_repo;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "rdkit-agent on GitHub";
          card.appendChild(link);
        }
        if (Array.isArray(r.notes) && r.notes.length) {
          card.appendChild(el("p", "chat-deferred-notes", r.notes.join(" ")));
        }
        log.appendChild(card);
      });
    log.scrollTop = log.scrollHeight;
  }

  async function loadIntoEditor(smiles) {
    setStatus("Loading structure into editor…");
    try {
      const resp = await fetch("/api/smiles-to-molblock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ smiles }),
      });
      const data = await resp.json();
      if (!resp.ok || data.ok === false) throw new Error(data.error || "conversion failed");
      const k = ketcher();
      if (k && k.setMolecule) {
        await k.setMolecule(data.molblock);
        setStatus("Loaded into editor.");
      } else {
        setStatus("Converted, but the Ketcher editor is not available.", true);
      }
    } catch (err) {
      setStatus(err.message, true);
    }
  }

  function setBusy(busy) {
    sendBtn.disabled = busy;
    input.disabled = busy;
    setStatus(busy ? "Thinking…" : "");
  }

  async function sendMessage(message) {
    addBubble("user", message);
    history.push({ role: "user", content: message });
    setBusy(true);
    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history: history.slice(0, -1) }),
      });
      const data = await resp.json();
      const reply = data.reply || data.error || "No reply.";
      addBubble("assistant", reply);
      if (data.ok) {
        addTrace(data.steps);
        addDeferredCards(data.steps);
        addStructures(data.workspace);
        // Trust the server's reconciled history so both sides stay in sync.
        if (Array.isArray(data.messages)) {
          history = data.messages.slice(-MAX_HISTORY);
        } else {
          history.push({ role: "assistant", content: reply });
        }
        setStatus("");
      } else {
        // Keep the user turn in history; drop nothing, but surface the issue.
        setStatus(data.error_type ? `Model unavailable (${data.error_type}).` : "Something went wrong.", true);
      }
    } catch (err) {
      addBubble("assistant", "Network error contacting the local server.");
      setStatus(err.message, true);
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    sendMessage(message);
  });

  // Enter sends; Shift+Enter inserts a newline.
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      history = [];
      log.innerHTML = "";
      setStatus("Conversation cleared.");
      input.focus();
    });
  }
})();
