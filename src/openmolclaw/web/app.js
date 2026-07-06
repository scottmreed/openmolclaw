/*
 * OpenMolClaw local web bridge.
 *
 * Clean-room glue written fresh against the public Ketcher standalone API and
 * the local Flask endpoints in openmolclaw/app.py. It is NOT derived from any
 * hosted product's editor components.
 *
 * Ketcher standalone exposes `window.ketcher` inside its iframe once loaded:
 *   - ketcher.setMolecule(molblockOrSmiles)
 *   - ketcher.getMolfile() -> Promise<string> (Molblock)
 * We do SMILES<->Molblock conversion server-side (RDKit) so pasted SMILES load
 * reliably and read-back is canonicalized.
 */
"use strict";

const $ = (id) => document.getElementById(id);

function setStatus(msg, isError) {
  const el = $("status");
  el.textContent = msg;
  el.classList.toggle("status--error", Boolean(isError));
}

function ketcher() {
  const frame = $("ketcher-frame");
  try {
    return frame && frame.contentWindow ? frame.contentWindow.ketcher : null;
  } catch (_e) {
    return null; // cross-origin or not loaded
  }
}

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok || data.ok === false) {
    throw new Error(data.error || `request failed (${resp.status})`);
  }
  return data;
}

async function loadModelOptions() {
  try {
    const resp = await fetch("/api/model-options");
    const data = await resp.json();
    const select = $("model-select");
    select.innerHTML = "";
    (data.options || []).forEach((option) => {
      const el = document.createElement("option");
      el.value = JSON.stringify(option);
      el.textContent = option.label || `${option.provider}: ${option.model}`;
      select.appendChild(el);
    });
    $("model-note").textContent = data.privacy_note || "";
  } catch (err) {
    $("model-note").textContent = "Model options unavailable.";
  }
}

$("model-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const raw = $("model-select").value;
  if (!raw) return;
  try {
    const selected = JSON.parse(raw);
    const result = await postJSON("/api/model-options", selected);
    setStatus(`Selected ${result.provider.provider}: ${result.provider.model}`);
  } catch (err) {
    setStatus(err.message, true);
  }
});

// --- load SMILES into the editor -------------------------------------------
$("smiles-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const smiles = $("smiles-input").value.trim();
  if (!smiles) return;
  setStatus("Converting SMILES…");
  try {
    const { molblock } = await postJSON("/api/smiles-to-molblock", { smiles });
    const k = ketcher();
    if (k && k.setMolecule) {
      await k.setMolecule(molblock);
      setStatus("Loaded into editor.");
    } else {
      setStatus("Converted, but Ketcher is not available (see vendor note).", true);
    }
  } catch (err) {
    setStatus(err.message, true);
  }
});

// --- read the current structure back ---------------------------------------
$("read-structure").addEventListener("click", async () => {
  const k = ketcher();
  if (!k || !k.getMolfile) {
    setStatus("Ketcher is not available.", true);
    return;
  }
  setStatus("Reading structure…");
  try {
    const molblock = await k.getMolfile();
    const { smiles } = await postJSON("/api/molblock-to-smiles", { molblock });
    $("smiles-input").value = smiles;
    setStatus(`Structure: ${smiles}`);
  } catch (err) {
    setStatus(err.message, true);
  }
});

// --- render the current structure into the workspace -----------------------
$("render-structure").addEventListener("click", async () => {
  const k = ketcher();
  let smiles = $("smiles-input").value.trim();
  try {
    if (k && k.getMolfile) {
      const molblock = await k.getMolfile();
      const r = await postJSON("/api/molblock-to-smiles", { molblock });
      smiles = r.smiles || smiles;
      $("smiles-input").value = smiles;
    }
    if (!smiles) {
      setStatus("Nothing to render.", true);
      return;
    }
    setStatus("Rendering…");
    const { alias, svg } = await postJSON("/api/render", { smiles });
    $("preview").innerHTML = svg;
    addTrace(`render_molecule → ${alias} (${smiles})`);
    await refreshWorkspace();
    setStatus(`Rendered as ${alias}.`);
  } catch (err) {
    setStatus(err.message, true);
  }
});

// --- privacy posture --------------------------------------------------------
//
// These strings are the strongest claims OpenMolClaw can make honestly — see
// docs/zdr.md "Claims to avoid". `local` truly never leaves the machine; a
// custom (non-local, non-openrouter) endpoint is NOT covered by ZDR routing,
// so it must not be described as "local" or otherwise implied to be private.
function formatPrivacySummary(data) {
  const provider = data.provider || "unknown";
  if (provider === "local") {
    return (
      `Provider: local — requests stay on this machine; no OpenRouter or other ` +
      `hosted endpoint is used. Workspace: ${data.workspace_save_mode}.`
    );
  }
  if (provider !== "openrouter") {
    return (
      `Provider: ${provider} (custom endpoint) — OpenRouter ZDR does not apply; ` +
      `requests go to your configured endpoint, whose own data-retention policy ` +
      `governs them. Workspace: ${data.workspace_save_mode}.`
    );
  }
  const zdr = data.openrouter_zdr ? "ON" : "OFF";
  const dc = data.deny_data_collection ? "denied" : "allowed";
  const fb = data.allow_fallbacks ? "enabled" : "disabled";
  return (
    `OpenRouter ZDR (Zero Data Retention): ${zdr} · provider data collection ${dc} ` +
    `· fallbacks ${fb} · workspace: ${data.workspace_save_mode}`
  );
}

function renderPrivacy(data) {
  $("privacy-summary").textContent = formatPrivacySummary(data);
  $("privacy-warning").textContent = (data.warnings || []).join(" ");
  const zdrToggle = $("zdr-toggle");
  if (zdrToggle) zdrToggle.checked = Boolean(data.openrouter_zdr);
  const memToggle = $("memory-only-toggle");
  if (memToggle) memToggle.checked = data.workspace_save_mode === "memory_only";
  const psmToggle = $("private-structure-mode-toggle");
  if (psmToggle) psmToggle.checked = Boolean(data.private_structure_mode);
  const claimEl = $("private-structure-mode-claim");
  if (claimEl) {
    if (data.private_structure_mode_claim) {
      claimEl.textContent = data.private_structure_mode_claim;
      claimEl.hidden = false;
    } else {
      claimEl.textContent = "";
      claimEl.hidden = true;
    }
  }
}

async function refreshPrivacy() {
  try {
    const resp = await fetch("/api/privacy");
    renderPrivacy(await resp.json());
  } catch (_e) {
    $("privacy-summary").textContent = "Privacy status unavailable.";
  }
}

async function updatePrivacySession(patch) {
  try {
    const data = await postJSON("/api/privacy/session", patch);
    renderPrivacy(data);
    setStatus("Privacy settings updated for this session.");
  } catch (err) {
    setStatus(err.message, true);
    await refreshPrivacy();
  }
}

function addTrace(text) {
  const li = document.createElement("li");
  li.textContent = text;
  $("trace").appendChild(li);
}

async function refreshWorkspace() {
  try {
    const resp = await fetch("/api/workspace");
    const data = await resp.json();
    const list = $("object-list");
    list.innerHTML = "";
    Object.entries(data.objects || {}).forEach(([alias, obj]) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="alias">${alias}</span> <span class="smiles">${obj.smiles || obj.type || ""}</span>`;
      list.appendChild(li);
    });
  } catch (_e) {
    /* workspace endpoint optional */
  }
}

// Detect whether Ketcher loaded; show a friendly note if not.
const zdrToggleEl = $("zdr-toggle");
if (zdrToggleEl) {
  zdrToggleEl.addEventListener("change", (e) => {
    updatePrivacySession({ openrouter_zdr: e.target.checked });
  });
}
const memToggleEl = $("memory-only-toggle");
if (memToggleEl) {
  memToggleEl.addEventListener("change", (e) => {
    updatePrivacySession({
      workspace_save_mode: e.target.checked ? "memory_only" : "local_json",
    });
  });
}
const psmToggleEl = $("private-structure-mode-toggle");
if (psmToggleEl) {
  psmToggleEl.addEventListener("change", (e) => {
    // Turning this on forces ZDR (for OpenRouter), blocks external lookups,
    // and forces memory-only workspace server-side — no silent weakening.
    updatePrivacySession({ private_structure_mode: e.target.checked });
  });
}

// --- optional rdkit-agent deferred workflows -------------------------------
//
// These do not call /api/execute directly. They build a chat prompt naming
// the matching rdkit_agent_* tool and submit it through the normal chat form,
// so the LLM (not this script) decides whether/how to call the tool. See
// docs/rdkit_agent_deferred_tools.md.
function rdkitAgentPrompt(workflow, input) {
  const prompts = {
    similarity:
      `Use the rdkit_agent_similarity_search tool to prepare a deferred rdkit-agent similarity search.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain how to run it outside OpenMolClaw.`,
    "atom-map":
      `Use the rdkit_agent_atom_map tool to prepare a deferred rdkit-agent atom-map operation.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain what the result would be used for.`,
    balance:
      `Use the rdkit_agent_reaction_balance_check tool to prepare a deferred rdkit-agent reaction balance check.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain what balance issues the external tool should detect.`,
    fingerprint:
      `Use the rdkit_agent_fingerprint tool to prepare a deferred rdkit-agent fingerprint request.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain how fingerprints can be used downstream.`,
  };
  return prompts[workflow] || input;
}

const rdkitAgentForm = $("rdkit-agent-form");
if (rdkitAgentForm) {
  rdkitAgentForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const workflow = $("rdkit-agent-workflow").value;
    const input = $("rdkit-agent-input").value.trim();
    if (!input) {
      setStatus("Enter input for the rdkit-agent workflow.", true);
      return;
    }
    const chatInput = document.getElementById("chat-input");
    const chatForm = document.getElementById("chat-form");
    if (!chatInput || !chatForm) {
      setStatus("Chat panel is not available.", true);
      return;
    }
    chatInput.value = rdkitAgentPrompt(workflow, input);
    chatForm.requestSubmit();
    setStatus(`Asked the AI to prepare a ${workflow} request.`);
  });
}

window.addEventListener("load", () => {
  loadModelOptions();
  refreshWorkspace();
  refreshPrivacy();
  setTimeout(() => {
    if (!ketcher()) $("ketcher-missing").hidden = false;
  }, 2500);
});
