# Adding skills

A **skill** is a Markdown playbook under `openmolclaw/skills/<name>/SKILL.md`
describing how to use the harness for a task (structure building, SVG drawing,
router-first tool calls, workspace JSON, local model setup). Skills are
documentation the model and the developer read; they are not executable plugins.

## Layout

```text
openmolclaw/skills/
  rdkit-structure-builder/SKILL.md
  molecule-svg-drawing/SKILL.md
  ketcher-local-harness/SKILL.md
  router-first-tool-calls/SKILL.md
  workspace-json/SKILL.md
  local-model-provider/SKILL.md
```

## Write one

1. Create `openmolclaw/skills/<name>/SKILL.md`.
2. Lead with *when to use it*, then a short worked example that calls the public
   API (`openmolclaw.chemistry`, `openmolclaw.harness`, `openmolclaw.workspace`).
3. Keep it generic and local-first: name no proprietary model vendor and no
   commercial feature (see [`sync_policy.md`](sync_policy.md)).

`tests/test_skill_registry.py` checks that the core skills are present.

## Adding a callable tool

To register a new *tool* the router can pick, add a handler and schema to a
`ToolRegistry` (see `openmolclaw/builtin_tools.py`). The registry advertises the
schema to the model; the executor dispatches the handler by name.
