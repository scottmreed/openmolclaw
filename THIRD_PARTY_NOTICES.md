# Third-Party Notices

OpenMolClaw is licensed under the Apache License, Version 2.0 (see
[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE)). This document lists the
third-party open-source components it depends on or embeds, and points to
the full upstream license text for each, kept locally under
[`licenses/`](licenses/).

This file is shipped in every source checkout and PyPI distribution so the
provenance of bundled and dependency code is discoverable without having to
chase it down per-release. Not every dependency listed here is physically
bundled inside the wheel — see the "Redistributed?" column — but all are
either required to run OpenMolClaw or reachable via its documented vendor
path, so their license terms are documented up front rather than only at the
point a build happens to include them.

| Component | License | Redistributed? | Full text |
|---|---|---|---|
| [RDKit](https://github.com/rdkit/rdkit) | BSD 3-Clause | No — pip runtime dependency, installed separately from its own PyPI wheel | [`licenses/RDKit-BSD-3-Clause.txt`](licenses/RDKit-BSD-3-Clause.txt) |
| [Flask](https://github.com/pallets/flask) | BSD 3-Clause | No — pip runtime dependency, installed separately from its own PyPI wheel | [`licenses/Flask-BSD-3-Clause.txt`](licenses/Flask-BSD-3-Clause.txt) |
| [Ketcher](https://github.com/epam/ketcher) | Apache License 2.0 | Not committed to this repo or the published wheel today; fetched as a static build via `openmolclaw install-ketcher` into `src/openmolclaw/web/vendor/ketcher/` (see [`ketcher-vendoring`](.claude/skills/ketcher-vendoring/SKILL.md)). Listed here because the vendor path ships it into every local install and any build that bundles the vendored assets. | [`licenses/Ketcher-Apache-2.0.txt`](licenses/Ketcher-Apache-2.0.txt), [`licenses/Ketcher-NOTICE.txt`](licenses/Ketcher-NOTICE.txt) |

## Why this file exists

OpenMolClaw is marketed as a local RDKit/Ketcher harness, ships static web
assets, has a documented vendor path for Ketcher, and may be used to produce
source, binary, or public static exports. Rather than deciding per-release
whether a given build happens to bundle Ketcher, this notices file and the
`licenses/` directory are kept up to date unconditionally: every checkout and
distribution carries the notice text, and any component that is redistributed
or is likely to be vendored also has its upstream license text bundled
verbatim.

## Other runtime dependencies

`pydantic`, `pyyaml`, and `requests` are also runtime dependencies (see
`pyproject.toml`), each under a permissive open-source license (MIT/BSD-style
or Apache-2.0 respectively) and installed from their own PyPI distributions,
which carry their own license files. They are not bundled into the
OpenMolClaw wheel and are omitted from the table above because they are
ordinary pip dependencies with no vendor/static-asset path into this repo.
