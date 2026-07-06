# Example prompts

These show the router-first loop: the router picks one tool, the executor runs
it, and the result lands in the local workspace. Wire a model via a config in
this folder (`--config examples/config.local.olmo.yaml`).

## Validate a structure
> Is `CC(=O)Oc1ccccc1C(=O)O` a valid molecule?

Router → `validate_smiles` → `{ "valid": true }`.

## Render into the workspace
> Draw benzene.

Router → `render_molecule` with `{"smiles": "c1ccccc1"}` → SVG stored as `[m1]`.

## Convert / sanitize
> Clean up this SMILES: `OCC`

Router → `convert_smiles` → `{ "sanitized_smiles": "CCO", "valid": true }`.

## Look up a compound by name
> What's the SMILES for caffeine?

Router → `lookup_compound` with `{"name": "caffeine"}` → PubChem SMILES.

## Just chatting (no tool)
> Thanks!

Router → conversational; no tool runs.
