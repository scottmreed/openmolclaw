---
name: rdkit-structure-builder
description: 'Programmatically build, modify, and manipulate chemical structures using
  RDKit without requiring LLM API calls. Use when you need to: (1) Retrieve common
  chemical scaffolds (benzene, pyridine, amino acids, etc.), (2) Build molecules from
  building blocks (chains, rings, functional groups), (3) Manipulate fragments (replace
  substructures, find disconnections, extract MCS), (4) Validate or canonicalize SMILES
  strings, (5) Generate molecular series or variants (homologous series, isomers,
  functional group scans), or (6) Perform any routine structure manipulation for local
  chat or workspace workflows.'
---
<!--
SYNCED FILE: Generated from the private ChemIllusion repo.
Source key: rdkit-structure-builder
Do not edit directly unless submitting a patch proposal.
Public edits may be overwritten by the next export.
-->

# RDKit Structure Builder

Programmatic molecule creation and manipulation using RDKit. Provides instant, deterministic access to structure building operations without LLM overhead.

## Quick start

```bash
# Get common scaffold
scaffold = get_scaffold("benzene")  # Returns: "c1ccccc1"

# Build alkyl chain
chain = build_chain(carbons=8)  # Returns: "CCCCCCCC"

# Attach functional group
modified = attach_group("c1ccccc1", group="hydroxyl", position="para")

# Generate homologous series
series = generate_series("CCO", extend_by="CH2", count=5)
```

## Core capabilities

### 1. Scaffold Library

Pre-built common structures for instant retrieval. Located in `backend/app/services/rdkit_builder_service.py`.

**Common rings:**

```python
from app.services.rdkit_builder_service import ScaffoldLibrary

scaffold = ScaffoldLibrary()

# Aromatic rings
scaffold.get("benzene")        # "c1ccccc1"
scaffold.get("naphthalene")    # "c1ccc2ccccc2c1"
scaffold.get("anthracene")     # "c1ccc2cc3ccccc3cc2c1"

# Heterocycles
scaffold.get("pyridine")       # "c1ccncc1"
scaffold.get("imidazole")      # "c1cnc[nH]1"
scaffold.get("furan")          # "c1ccoc1"
scaffold.get("piperidine")     # "C1CCNCC1"

# Aliphatic rings
scaffold.get("cyclohexane")    # "C1CCCCC1"
scaffold.get("cyclopentane")   # "C1CCCC1"
```

**Amino acids:**

```python
scaffold.get("alanine")        # "CC(N)C(=O)O"
scaffold.get("phenylalanine")  # "NC(Cc1ccccc1)C(=O)O"
scaffold.get("glycine")        # "NCC(=O)O"
```

**Functional group carriers:**

```python
scaffold.get("ethanol")        # "CCO"
scaffold.get("acetone")        # "CC(=O)C"
scaffold.get("acetic_acid")    # "CC(=O)O"
```

Returns: SMILES string ready for workspace placement or further manipulation.

### 2. Structure Building

Programmatic molecule construction from building blocks.

```python
from app.services.rdkit_builder_service import StructureBuilder

builder = StructureBuilder()

# Build alkyl chains
builder.build_chain(carbons=8)                    # "CCCCCCCC"
builder.build_chain(carbons=12, chain_type="alkoxy")  # "CCCCCCCCCCCCCO"

# Build rings
builder.build_ring(size=6, ring_type="aromatic")  # "c1ccccc1"
builder.build_ring(size=5, heteroatoms=["N", "O"])  # Heterocycle variants

# Attach functional groups
builder.attach_group(
    smiles="c1ccccc1",
    group="hydroxyl",
    position="para"
)  # Returns: "Oc1ccc(O)cc1" (para-hydroxybenzene)

builder.attach_group(
    smiles="CCCC",
    group="amine",
    position="terminal"
)  # Returns: "NCCCC"

# Link fragments
builder.link_fragments(
    fragment1="c1ccccc1",
    fragment2="CCCC",
    bond_type="single"
)  # Returns phenylbutane SMILES
```

Returns: SMILES string + description of what was built.

### 3. Fragment Operations

Advanced manipulation and retrosynthesis analysis.

```python
from app.services.rdkit_builder_service import FragmentOperations

frag = FragmentOperations()

# Replace substructures (scaffold hopping)
frag.replace_substructure(
    smiles="CCCCNCCCC",
    query="[NH2]",           # SMARTS pattern
    replacement="O"
)  # Replace amine with hydroxyl

# Find disconnection points (retrosynthesis)
frag.find_disconnections(
    smiles="c1ccc(C(=O)Nc2ccccc2)cc1",
    max_cuts=2
)  # Returns potential synthetic cuts

# Extract maximum common substructure
frag.find_mcs(
    smiles1="c1ccccc1CCO",
    smiles2="c1ccccc1CCC"
)  # Returns benzene + ethyl scaffold

# Enumerate functional group positions
frag.enumerate_variants(
    scaffold="c1ccccc1",
    groups=["OH", "NH2", "F"],
    max_variants=5
)  # Returns up to 5 substituted benzenes
```

Returns: SMILES variants with descriptions.

### 4. SMILES Utilities

Validation, canonicalization, and property calculation.

```python
from app.services.rdkit_builder_service import SMILESUtilities

utils = SMILESUtilities()

# Validate SMILES
utils.validate("CCO")  # True
utils.validate("INVALID")  # False

# Canonicalize (normalize)
utils.canonicalize("C1=CC=CC=C1")  # "c1ccccc1"

# Check pattern matching
utils.matches_pattern(
    smiles="c1ccccc1CCO",
    pattern="[OH]"  # SMARTS
)  # True

# Calculate properties
utils.calculate_properties(
    smiles="CCO",
    properties=["MW", "LogP", "HBA", "HBD"]
)  # Returns dict: {"MW": 46.07, "LogP": -0.07, ...}

# Convert formats
utils.convert_format(
    input_data="CCO",
    from_format="smiles",
    to_format="molfile"
)  # Returns MOL file string
```

Returns: Validated/transformed SMILES + metadata.

### 5. Batch Operations

Generate multiple structures for workspace placement or library generation.

```python
from app.services.rdkit_builder_service import BatchOperations

batch = BatchOperations()

# Generate homologous series
batch.generate_series(
    base="CCO",
    extend_by="CH2",
    count=5
)  # ["CCO", "CCCO", "CCCCO", "CCCCCO", "CCCCCCO"]

# Create isomer library
batch.generate_isomers(
    formula="C4H10O",
    max_count=10
)  # Returns constitutional isomers

# Functional group scan (combinatorial)
batch.functional_group_scan(
    scaffold="c1ccccc1",
    positions=["ortho", "meta", "para"],
    groups=["OH", "NH2", "NO2"]
)  # Returns 9 variants (3 positions × 3 groups)
```

Returns: List of SMILES strings with descriptions.

## Integration with existing services

Leverage existing backend services for additional capabilities:

```python
# Molecule visualization and manipulation
from app.services.molecule_service import MoleculeService
mol_service = MoleculeService()
mol_service.rotate_molecule(smiles, angle=90)
mol_service.highlight_substructure(smiles, pattern)

# Functional group detection
from app.services.molecule_analysis_service import MoleculeAnalysisService
analysis = MoleculeAnalysisService()
analysis.detect_functional_groups(smiles)
analysis.analyze_rings(smiles)

# Maximum common substructure
from app.services.molecule_highlighting_service import MoleculeHighlightingService
highlight = MoleculeHighlightingService()
highlight.find_common_substructure([smiles1, smiles2, smiles3])
```

## Example workflows

### Workflow 1: Build alcohol series for local chat

```python
# User asks: "Show me the first 10 alcohols"
from app.services.rdkit_builder_service import BatchOperations

batch = BatchOperations()
alcohols = batch.generate_series(
    base="CO",           # Methanol
    extend_by="CH2",     # Add methylene
    count=10
)

# Returns: ["CO", "CCO", "CCCO", "CCCCO", ...]
# Names: ["methanol", "ethanol", "propanol", "butanol", ...]
```

### Workflow 2: Create substituted benzenes for local workspace

```python
# User asks: "Create a grid of para-substituted benzenes"
from app.services.rdkit_builder_service import BatchOperations

batch = BatchOperations()
variants = batch.functional_group_scan(
    scaffold="c1ccccc1",
    positions=["para"],
    groups=["OH", "NH2", "NO2", "F", "Cl", "Br", "CHO", "COOH"]
)

# Returns 8 SMILES ready for workspace placement
```

### Workflow 3: Retrosynthesis analysis

```python
# User asks: "How would you synthesize benzanilide?"
from app.services.rdkit_builder_service import FragmentOperations

frag = FragmentOperations()
cuts = frag.find_disconnections(
    smiles="c1ccc(C(=O)Nc2ccccc2)cc1",  # Benzanilide
    max_cuts=2
)

# Returns suggested disconnections:
# Cut 1: "c1ccc(C(=O)O)cc1" + "Nc1ccccc1" (amide bond cleavage)
# Cut 2: "c1ccc(Br)cc1" + "C(=O)Nc1ccccc1" (C-C bond cleavage)
```

### Workflow 4: Scaffold hopping

```python
# User asks: "Replace the phenyl ring with pyridine"
from app.services.rdkit_builder_service import FragmentOperations

frag = FragmentOperations()
new_molecule = frag.replace_substructure(
    smiles="c1ccc(CCO)cc1",      # Phenylethanol
    query="c1ccccc1",            # Phenyl ring
    replacement="c1ccncc1"       # Pyridine ring
)

# Returns: "c1cc(CCO)ncc1" (4-pyridylethanol)
```

### Workflow 5: Batch property calculation

```python
# User asks: "Calculate MW and LogP for a library"
from app.services.rdkit_builder_service import BatchOperations, SMILESUtilities

batch = BatchOperations()
utils = SMILESUtilities()

# Generate library
library = batch.generate_series("CCO", "CH2", 10)

# Calculate properties for each
properties = [
    utils.calculate_properties(smi, ["MW", "LogP"])
    for smi in library
]

# Returns list of property dicts for analysis
```

## File locations

- **Main service**: `backend/app/services/rdkit_builder_service.py`
- **Scaffold library data**: `backend/app/services/rdkit_builder_service.py` (embedded)
- **Existing services**:
  - `backend/app/services/molecule_service.py` - Visualization, rotation
  - `backend/app/services/molecule_analysis_service.py` - Functional groups, rings
  - `backend/app/services/molecule_highlighting_service.py` - Substructure, MCS

## Key benefits

1. **No LLM overhead**: Instant structure generation (<100ms vs 1-3s)
2. **Deterministic**: Same input always produces same output
3. **Cost-free**: $0 per call vs $0.0001-0.001 per LLM call
4. **Composable**: Chain operations together
5. **Fast iteration**: Try multiple variants quickly

## When to use this skill vs LLM tools

**Use RDKit skill for:**

- Common scaffolds (benzene, pyridine, etc.)
- Systematic modifications (add OH, replace ring, etc.)
- Series generation (homologous series, isomers)
- SMILES validation/canonicalization
- Batch operations on known patterns

**Use LLM tools (`create_molecule`) for:**

- Complex natural products with ambiguous IUPAC names
- Structure interpretation from descriptions
- Novel molecule design with constraints
- When user input is ambiguous or requires reasoning

## Advanced RDKit capabilities

The skill leverages RDKit's comprehensive toolkit:

**Batch processing:**

- Supplier objects for efficient SDF/SMILES file reading
- Multithreaded processing for large datasets
- Compressed file support (gzip)

**Molecular validation:**

- Automatic sanitization (valence, aromaticity, chirality)
- Problem detection and error handling
- Partial sanitization options

**Analysis:**

- Molecular descriptors (MW, LogP, TPSA, HBD/HBA, rotatable bonds)
- Fingerprints (Morgan/ECFP, RDKit, MACCS, atom pairs)
- Similarity metrics (Tanimoto, Dice, Cosine)
- Chiral center detection
- Ring system analysis (SSSR)

**Reactions:**

- Reaction SMARTS for transformations
- Product generation from reaction templates
- Common reactions (esterification, amidation)

## Usage tips

1. **Start with scaffolds**: Check scaffold library before building from scratch
2. **Validate early**: Use `validate()` before expensive operations
3. **Canonicalize**: Always canonicalize SMILES for comparison
4. **Batch when possible**: Use batch operations for multiple structures
5. **Chain operations**: Combine scaffold → modify → validate workflows
6. **Leverage existing services**: Use `MoleculeService` for visualization after building

## Error handling

All methods return `None` or empty results on invalid input rather than raising exceptions. Always check return values:

```python
smiles = builder.build_chain(carbons=8)
if smiles:
    # Valid SMILES generated
    proceed_with_visualization(smiles)
else:
    # Invalid input or build failure
    fallback_to_llm_tool()
```

---
*Maintained by the [ChemIllusion](https://chemillusion.com) team as part of OpenMolClaw.*
