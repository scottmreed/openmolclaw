# Sync policy (synced vs public-owned)

Some files in this repository are **synced from a private upstream source** at
ChemIllusion and carry a generated header. Contributions to synced files are
welcome as **patch proposals**, but accepted changes are imported upstream and
re-exported, so a direct edit may be overwritten by the next export.

**Public-owned** files (no generated header) can be edited directly through
normal pull requests. As the project matures, more of the core moves to
public-first ownership.

Files here fall into two classes:

## synced-from-private

Generated from the private ChemIllusion repo by the export pipeline. They carry a
header:

```md
<!--
SYNCED FILE: Generated from the private ChemIllusion repo.
Source key: <key>
Do not edit directly unless submitting a patch proposal.
Public edits may be overwritten by the next export.
-->
```

Public PRs to these files are treated as **patch proposals** upstream, not direct
merges. The exported skill docs under `openmolclaw/skills/` are synced.

## public-owned

Native to OpenMolClaw. No generated header. Public PRs can be merged directly.
This includes the package code (`openmolclaw/*.py`), the local app and web bridge
(`web/`), `examples/`, `tests/`, and these docs.

## Contract tests

`tests/contract/` is byte-identical with the private repo except for its
`binding.py`. It pins the behavior both repos must agree on; divergence surfaces
in the weekly drift report.

## Local agent files (not versioned)

These paths are gitignored and stay on your machine only — they are for
HyperAgent / Claude Code integration with the private product repo, not for
the public package:

- `hyperagent/` — GitHub MCP write setup for agent-driven PRs
- `.claude/skills/` — local Claude skills (including chem-art-generator integration)
- `CLAUDE.md` — Claude Code project guide for this checkout
