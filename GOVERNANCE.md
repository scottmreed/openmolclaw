# Governance

OpenMolClaw is the open, local-first chemistry agent harness from the team
behind [ChemIllusion](https://chemillusion.com). This document describes how the
project is maintained and how it transitions to an **upstream-first** open-core
model (the Sentry/GitLab pattern) as it matures — Phase 5 of
`openmolclaw_private_public_split_prd.md` §16.

## Roles

| Role | Responsibility |
| ---- | -------------- |
| **Maintainer** | Reviews and merges PRs; owns the sync policy and the harness core. |
| **Release manager** | Tags releases, writes the [CHANGELOG](CHANGELOG.md), and enforces [semver](docs/versioning.md). Critical from Phase 3 on, because the private product depends on released versions. |
| **Contributor** | Adds public-owned features/skills or proposes patches to synced files (see [CONTRIBUTING.md](CONTRIBUTING.md)). |

One person may hold multiple roles while the project is small.

## Review & branch protection

Core harness paths carry required review via [`.github/CODEOWNERS`](.github/CODEOWNERS).
Recommended `main` branch protection (set in repo Settings → Branches, since it
can't be committed as a file):

- Require a pull request before merging, with at least one approving review.
- Require the `ci` status check (unit + contract + `doctor`) to pass.
- Require CODEOWNERS review for changes under `src/openmolclaw/**`.
- Require branches to be up to date before merging.

## Releases

Releases are **tag-driven** and publish to PyPI. See
[docs/versioning.md](docs/versioning.md) for the semver policy and the
step-by-step release checklist, and
[`scripts/install_release_workflow.sh`](scripts/install_release_workflow.sh) for
the automation. Because GitHub requires the `workflow` scope to add files under
`.github/workflows/`, the release workflow is installed by a maintainer running
that script locally (the same reason `ci.yml` ships via
`scripts/install_ci_workflow.sh`).

Publishing uses PyPI **Trusted Publishing** (OIDC) — no long-lived API token is
stored in the repo. Configure the trusted publisher for `openmolclaw` on PyPI to
point at this repository and the `release` workflow before the first tagged
release; see [docs/publishing.md](docs/publishing.md).

## Upstream-first transition (Phase 5)

The project moves from *private-canonical / public-export* to
*public-canonical / private-consumes-releases* only when the public repo shows
sustained external contribution, and only on an explicit decision by the project
owner (PRD Open Question 9). This file, the changelog, the semver policy, and
CODEOWNERS are the groundwork so that flip is smooth rather than a scramble.

When the flip happens:

1. Generic-core changes land as **public PRs first**; the private repo consumes
   them by bumping its pinned version.
2. Community skill contributions merge here; the private repo gains them by
   version bump.
3. The private→public **export pipeline for core code is retired** — only a
   lightweight skill-sync path remains for any skills that stay private-first,
   and the drift report narrows to skills. (Core code no longer flows through
   export because there is only one copy: this package.)
4. This document is promoted from "patch proposal" language to a normal OSS
   contribution flow.

Until then the project rests in the Phase 2–3 posture, which already delivers
the funnel and credibility benefits.

## Code of conduct & licensing

Contributions are licensed under [Apache-2.0](LICENSE). Be respectful in issues,
discussions, and reviews; assume good faith.
