---
name: workspace-json
description: 'The local workspace JSON format and semantic-alias system ([m1], [r1],
  [label1]): how molecules, reactions, labels, and rendered assets are stored, referenced,
  and round-tripped to a single local JSON file with no database. Use when building
  or reasoning about local workspace state and object references.'
---
<!--
SYNCED FILE: Generated from the private ChemIllusion repo.
Source key: workspace-json
Do not edit directly unless submitting a patch proposal.
Public edits may be overwritten by the next export.
-->

# Workspace JSON

The local harness keeps all state in a single JSON document — no account, no
project database, no server persistence. Objects are addressed by short
**semantic aliases** (`[m1]`, `[r1]`, `[label1]`) so the model and the user can
refer to them stably across a session.

## Design goals

- **Local-first.** Everything round-trips to one JSON file you can commit, diff,
  or hand to a colleague.
- **Stable handles.** Aliases don't change when objects are reordered or
  re-rendered.
- **Tool-friendly.** A tool can accept `[m1]` and resolve it to a molecule's
  current SMILES/Molblock without the caller tracking internal IDs.

## Semantic aliases

Each object gets a type-prefixed alias, assigned in creation order per type:

| Prefix | Type | Example |
|---|---|---|
| `m` | molecule | `[m1]`, `[m2]` |
| `r` | reaction | `[r1]` |
| `label` | text label | `[label1]` |
| `arrow` | arrow/annotation | `[arrow1]` |

Aliases are opaque handles: `[m1]` always means the same molecule for the life of
the workspace, even after edits or re-renders.

## Workspace document shape

```json
{
  "version": 1,
  "objects": [
    {
      "id": "b1c2d3e4",
      "alias": "m1",
      "type": "molecule",
      "source": "ketcher",
      "smiles": "c1ccccc1",
      "molblock": "…",
      "assets": { "svg": "workspace/assets/m1.svg" },
      "meta": { "name": "benzene", "created": "2026-07-05T00:00:00Z" }
    },
    {
      "id": "f5a6b7c8",
      "alias": "r1",
      "type": "reaction",
      "source": "tool:build_reaction",
      "rxn": "CCO.CC(=O)O>>CC(=O)OCC.O",
      "meta": { "name": "Fischer esterification" }
    }
  ],
  "trace": []
}
```

- `id` — internal, stable, never shown to the user.
- `alias` — the short handle used in chat and tool arguments.
- `source` — provenance: `ketcher`, `tool:<name>`, `paste`, `import`.
- `assets` — paths to rendered files under the local workspace dir.
- `trace` — the execution trace (see the `router-first-tool-calls` skill).

## Alias registry

```python
class Aliases:
    def __init__(self):
        self._counts = {}          # type -> last index used

    def new(self, obj_type: str) -> str:
        prefix = {"molecule": "m", "reaction": "r", "label": "label",
                  "arrow": "arrow"}[obj_type]
        n = self._counts.get(prefix, 0) + 1
        self._counts[prefix] = n
        return f"{prefix}{n}"

    def resolve(self, alias: str, objects: list) -> dict | None:
        alias = alias.strip("[]")
        return next((o for o in objects if o["alias"] == alias), None)
```

## Round-tripping

```python
import json
from pathlib import Path

def save_workspace(ws: dict, path: str) -> None:
    Path(path).write_text(json.dumps(ws, indent=2), encoding="utf-8")

def load_workspace(path: str) -> dict:
    ws = json.loads(Path(path).read_text(encoding="utf-8"))
    assert ws.get("version") == 1, "unsupported workspace version"
    return ws
```

## Resolving aliases in tool arguments

Tools accept aliases and resolve them against the current workspace, so a model
can say "canonicalize `[m1]`" without knowing internal IDs:

```python
def tool_canonicalize(alias: str, ws: dict) -> dict:
    obj = Aliases().resolve(alias, ws["objects"])
    if obj is None:
        return {"ok": False, "error": f"unknown object {alias}"}
    from rdkit import Chem
    mol = Chem.MolFromSmiles(obj["smiles"])
    return {"ok": True, "smiles": Chem.MolToSmiles(mol)}
```

## Constraints

- No database and no remote persistence: the JSON file *is* the workspace.
- Rendered assets are stored as local files referenced by relative path.
- Keep the format forward-compatible: bump `version` and migrate on load rather
  than breaking old files.

---
*Maintained by the [ChemIllusion](https://chemillusion.com) team as part of OpenMolClaw.*
