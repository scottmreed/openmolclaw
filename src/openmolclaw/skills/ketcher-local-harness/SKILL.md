---
name: ketcher-local-harness
description: 'How to embed Ketcher in a local Flask + JavaScript page and bridge it
  to RDKit: read/write Molblock, convert pasted SMILES to Molblock server-side, and
  render validated structures into the local workspace. Use when building or extending
  the local structure-editor harness.'
---
<!--
SYNCED FILE: Generated from the private ChemIllusion repo.
Source key: ketcher-local-harness
Do not edit directly unless submitting a patch proposal.
Public edits may be overwritten by the next export.
-->

# Ketcher Local Harness

Notes for wiring [Ketcher](https://github.com/epam/ketcher) into a small local
Flask + JavaScript app and bridging it to RDKit. Ketcher is the *editor*, not the
whole workspace — keep it thin and let RDKit do the chemistry.

These notes are **clean-room**: they describe the public Ketcher API and the
server-side conversion path, and are written fresh against the Ketcher API rather
than copied from any product frontend.

## Architecture

```text
[ Ketcher iframe ]  --Molblock/SMILES-->  [ Flask endpoint ]  --> [ RDKit ]
        ^                                                             |
        |------------------ validated Molblock / SVG -----------------|
```

1. Ketcher edits structures in the browser.
2. The page reads the current structure from Ketcher and sends it to Flask.
3. Flask calls RDKit to validate/canonicalize/convert/render.
4. Validated Molblock or rendered SVG goes back to the page and into the local
   workspace.

## Embedding Ketcher

Serve Ketcher's static build from `web/vendor/ketcher/` and embed it in an
`<iframe>`. Wait for the editor to be ready before calling its API:

```js
const frame = document.getElementById("ketcher-frame");
function ketcher() {
  return frame.contentWindow.ketcher; // Ketcher attaches itself to window
}

async function whenReady() {
  // Ketcher exposes a readiness promise; poll defensively for older builds.
  for (let i = 0; i < 100; i++) {
    if (frame.contentWindow && frame.contentWindow.ketcher) return ketcher();
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("Ketcher did not become ready");
}
```

## Reading the current structure

```js
const k = await whenReady();

// Preferred: Molfile (Molblock) round-trips cleanly through RDKit.
const molblock = await k.getMolfile();

// SMILES is convenient but lossy for layout/stereo; prefer Molblock for tools.
const smiles = await k.getSmiles();
```

## Loading a structure into Ketcher

Ketcher loads Molblock/Rxnfile directly:

```js
const k = await whenReady();
await k.setMolecule(molblock); // Molblock or Rxnfile string
```

## The SMILES paste flow (server-side conversion)

Ketcher's own SMILES import can be unreliable for pasted strings. The robust path
is to **convert pasted SMILES to Molblock server-side with RDKit first**, then
load the Molblock:

```js
async function loadSmiles(smiles) {
  const res = await fetch("/api/convert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ smiles, to: "molblock" }),
  });
  const { molblock, ok, error } = await res.json();
  if (!ok) throw new Error(error);
  const k = await whenReady();
  await k.setMolecule(molblock);
}
```

Server side (Flask + RDKit):

```python
from flask import request, jsonify
from rdkit import Chem
from rdkit.Chem import AllChem

@app.post("/api/convert")
def convert():
    data = request.get_json(force=True)
    smiles = (data or {}).get("smiles", "")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return jsonify(ok=False, error="invalid SMILES")
    AllChem.Compute2DCoords(mol)          # give Ketcher a sane 2D layout
    return jsonify(ok=True, molblock=Chem.MolToMolBlock(mol))
```

## Rendering validated structures

Render server-side with RDKit and return SVG for the workspace preview:

```python
from rdkit.Chem.Draw import rdMolDraw2D

def render_svg(molblock: str) -> str:
    mol = Chem.MolFromMolBlock(molblock)
    d = rdMolDraw2D.MolDraw2DSVG(320, 240)
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
    d.FinishDrawing()
    return d.GetDrawingText()
```

## Scope constraints

- Keep Ketcher as the editor only. The object list, rendered previews, execution
  trace, and workspace state live outside Ketcher (see the `workspace-json`
  skill).
- Do not try to recreate a full production canvas UI. This is a small local
  harness: editor + tool/chat panel + object list + rendered preview + trace.
- All chemistry validation happens in RDKit on the server, never in the browser.

---
*Maintained by the [ChemIllusion](https://chemillusion.com) team as part of OpenMolClaw.*
