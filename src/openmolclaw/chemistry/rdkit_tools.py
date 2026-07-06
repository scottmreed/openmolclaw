"""
RDKit Structure Builder Service

Comprehensive service for programmatic molecule creation and manipulation
using RDKit's advanced chemical informatics capabilities.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Draw, rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Geometry import rdGeometry

try:
    from rdkit.Chem import rdFMCS
    MCS_AVAILABLE = True
except ImportError:
    rdFMCS = None
    MCS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ScaffoldLibrary:
    """Library of common chemical scaffolds for rapid molecule building."""

    def __init__(self, scaffolds_file: Optional[str] = None):
        """Initialize scaffold library.

        Args:
            scaffolds_file: Path to scaffolds.json file. If None, uses default location.
        """
        if scaffolds_file is None:
            # Find scaffolds file relative to this module
            module_dir = Path(__file__).resolve().parents[3]
            scaffolds_file = module_dir / ".codex" / "skills" / "rdkit-structure-builder" / "scaffolds.json"

        self.scaffolds_file = Path(scaffolds_file)
        self._scaffolds = {}
        self._load_scaffolds()

    def _load_scaffolds(self) -> None:
        """Load scaffolds from JSON file."""
        try:
            if self.scaffolds_file.exists():
                with open(self.scaffolds_file, 'r') as f:
                    data = json.load(f)
                    self._scaffolds = data.get('scaffolds', {})
                logger.info(f"Loaded {len(self._scaffolds)} scaffolds from {self.scaffolds_file}")
            else:
                logger.warning(f"Scaffolds file not found: {self.scaffolds_file}")
                self._scaffolds = {}
        except Exception as e:
            logger.error(f"Error loading scaffolds: {e}")
            self._scaffolds = {}

    def get_scaffold(self, name: str) -> Optional[Dict[str, Any]]:
        """Get scaffold by name.

        Args:
            name: Scaffold name (case-insensitive)

        Returns:
            Scaffold data dict or None if not found
        """
        name_lower = name.lower().replace(' ', '_').replace('-', '_')
        return self._scaffolds.get(name_lower)

    def list_scaffolds(self, category: Optional[str] = None) -> List[str]:
        """List available scaffolds.

        Args:
            category: Filter by category (optional)

        Returns:
            List of scaffold names
        """
        if category:
            # Get scaffolds by category from metadata
            try:
                with open(self.scaffolds_file, 'r') as f:
                    data = json.load(f)
                    categories = data.get('categories', {})
                    return categories.get(category, [])
            except Exception:
                return []

        return list(self._scaffolds.keys())

    def get_categories(self) -> List[str]:
        """Get available scaffold categories."""
        try:
            with open(self.scaffolds_file, 'r') as f:
                data = json.load(f)
                categories = data.get('categories', {})
                return list(categories.keys())
        except Exception:
            return []


class StructureBuilder:
    """Programmatic molecule structure building operations."""

    def __init__(self):
        self.scaffold_lib = ScaffoldLibrary()

    def build_chain(self, carbons: int, terminal_group: str = "H", internal_pattern: str = "C") -> str:
        """Build an alkyl chain.

        Args:
            carbons: Number of carbons in chain
            terminal_group: Terminal group ("H", "OH", "NH2", "Cl", etc.)
            internal_pattern: Pattern for internal carbons ("CH2" for alkane)

        Returns:
            SMILES string of the chain
        """
        if carbons < 1:
            raise ValueError("Chain must have at least 1 carbon")

        terminal_map = {
            "OH": "O",
            "NH2": "N",
            "Cl": "Cl",
            "Br": "Br",
            "I": "I",
            "F": "F",
        }
        terminal_smiles = terminal_map.get(terminal_group, terminal_group)

        # Normalize common alkyl patterns to valid SMILES
        internal_smiles = internal_pattern
        if internal_smiles.upper() in {"CH2", "CH3", "CH"}:
            internal_smiles = "C"

        if carbons == 1:
            # Special case for single carbon
            if terminal_group == "H":
                return "C"
            return f"C{terminal_smiles}"

        # Build chain
        chain = "C"  # Start with first carbon
        for i in range(1, carbons - 1):
            chain += internal_smiles
        chain += "C"  # End with last carbon

        # Add terminal group if not hydrogen
        if terminal_group != "H":
            chain += terminal_smiles

        return chain

    def build_ring(self, size: int, aromatic: bool = False, heteroatoms: Optional[List[str]] = None) -> str:
        """Build a ring structure.

        Args:
            size: Ring size (3-8)
            aromatic: Whether ring should be aromatic
            heteroatoms: List of heteroatoms to include (e.g., ["N", "O"])

        Returns:
            SMILES string of the ring
        """
        if size < 3 or size > 8:
            raise ValueError("Ring size must be between 3 and 8")

        if heteroatoms:
            return self._build_heterocyclic_ring(size, aromatic, heteroatoms)
        else:
            return self._build_carbocyclic_ring(size, aromatic)

    def _build_carbocyclic_ring(self, size: int, aromatic: bool) -> str:
        """Build carbocyclic ring."""
        if aromatic:
            return f"c1{'c' * (size - 1)}1"  # Aromatic ring
        else:
            return f"C1{'C' * (size - 1)}1"  # Aliphatic ring

    def _build_heterocyclic_ring(self, size: int, aromatic: bool, heteroatoms: List[str]) -> str:
        """Build heterocyclic ring."""
        if len(heteroatoms) > size:
            raise ValueError("Cannot have more heteroatoms than ring atoms")

        atoms = []
        hetero_idx = 0

        for i in range(size):
            if hetero_idx < len(heteroatoms):
                hetero = heteroatoms[hetero_idx]
                if aromatic:
                    # Convert to lowercase for aromatic
                    atoms.append(hetero.lower())
                else:
                    atoms.append(hetero.upper())
                hetero_idx += 1
            else:
                atoms.append("c" if aromatic else "C")

        if not atoms:
            return ""

        return f"{atoms[0]}1{''.join(atoms[1:])}1"

    def attach_functional_group(self, base_smiles: str, group: str, position: str = "terminal") -> str:
        """Attach functional group to a molecule.

        Args:
            base_smiles: Base molecule SMILES
            group: Functional group to attach ("OH", "NH2", "Cl", etc.)
            position: Where to attach ("terminal", "random", etc.)

        Returns:
            Modified SMILES string
        """
        mol = Chem.MolFromSmiles(base_smiles)
        if mol is None:
            raise ValueError(f"Invalid base SMILES: {base_smiles}")

        # Find attachment point
        attachment_idx = self._find_attachment_point(mol, position)

        # Create functional group
        group_mol = self._create_functional_group(group)

        # Combine molecules
        combined = Chem.CombineMols(mol, group_mol)

        # Add bond between molecules
        editable = Chem.EditableMol(combined)
        editable.AddBond(attachment_idx, mol.GetNumAtoms(), Chem.BondType.SINGLE)

        result_mol = editable.GetMol()

        # Generate new SMILES
        return Chem.MolToSmiles(result_mol)

    def _find_attachment_point(self, mol: Chem.Mol, position: str) -> int:
        """Find atom index for functional group attachment."""
        if position == "terminal":
            # Find terminal carbon
            for atom in mol.GetAtoms():
                if atom.GetSymbol() == "C" and atom.GetDegree() == 1:
                    return atom.GetIdx()
        # Default to first carbon
        for atom in mol.GetAtoms():
            if atom.GetSymbol() == "C":
                return atom.GetIdx()
        return 0

    def _create_functional_group(self, group: str) -> Chem.Mol:
        """Create functional group molecule."""
        group_map = {
            "OH": "O",
            "NH2": "N",
            "Cl": "Cl",
            "Br": "Br",
            "I": "I",
            "F": "F",
            "CHO": "C=O",
            "COOH": "C(=O)O"
        }

        smiles = group_map.get(group, group)
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Unknown functional group: {group}")
        return mol


class FragmentOperations:
    """Advanced fragment manipulation operations."""

    def __init__(self):
        self.batch_processor = BatchProcessor()

    def replace_substructure(self, smiles: str, query: str, replacement: str) -> List[str]:
        """Replace substructures in a molecule.

        Args:
            smiles: Input molecule SMILES
            query: SMARTS pattern to find
            replacement: SMILES to replace with

        Returns:
            List of modified SMILES strings
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid input SMILES: {smiles}")

        query_mol = Chem.MolFromSmarts(query)
        if query_mol is None:
            query_mol = Chem.MolFromSmiles(query)  # Try as SMILES
            if query_mol is None:
                raise ValueError(f"Invalid query pattern: {query}")

        replacement_mol = Chem.MolFromSmiles(replacement)
        if replacement_mol is None:
            raise ValueError(f"Invalid replacement SMILES: {replacement}")

        # Perform replacement
        products = Chem.ReplaceSubstructs(mol, query_mol, replacement_mol)

        # Convert back to SMILES
        result_smiles = []
        for product in products:
            Chem.SanitizeMol(product)  # Ensure valid structure
            result_smiles.append(Chem.MolToSmiles(product))

        return result_smiles

    def find_maximum_common_substructure(self, smiles_list: List[str]) -> Optional[str]:
        """Find MCS of multiple molecules.

        Args:
            smiles_list: List of SMILES strings

        Returns:
            MCS SMARTS string or None
        """
        if not MCS_AVAILABLE:
            raise RuntimeError("MCS functionality not available (rdFMCS not installed)")

        if len(smiles_list) < 2:
            raise ValueError("Need at least 2 molecules for MCS")

        mols = []
        for smiles in smiles_list:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                raise ValueError(f"Invalid SMILES: {smiles}")
            mols.append(mol)

        try:
            mcs_result = rdFMCS.FindMCS(mols)
            return mcs_result.smartsString if mcs_result.smartsString else None
        except Exception as e:
            logger.error(f"MCS computation failed: {e}")
            return None

    def disconnect_molecule(self, smiles: str, max_cuts: int = 3) -> List[Dict[str, Any]]:
        """Find strategic disconnections for retrosynthesis.

        Args:
            smiles: Input molecule SMILES
            max_cuts: Maximum number of bonds to cut

        Returns:
            List of disconnection strategies with fragments
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")

        # Strategy: Find bonds that when cut create simpler fragments
        # This is a simplified retrosynthesis approach

        disconnections = []
        bonds = list(mol.GetBonds())

        for i, bond in enumerate(bonds):
            if len(disconnections) >= max_cuts:
                break

            # Only consider single bonds for now
            if bond.GetBondType() != Chem.BondType.SINGLE:
                continue

            # Cut the bond
            fragmented = Chem.FragmentOnBonds(mol, [bond.GetIdx()])

            # Get fragments
            frags = Chem.GetMolFrags(fragmented, asMols=True)

            if len(frags) == 2:  # Successful disconnection
                frag_smiles = [Chem.MolToSmiles(frag) for frag in frags]
                disconnections.append({
                    "bond_idx": bond.GetIdx(),
                    "fragments": frag_smiles,
                    "description": f"Cut bond between {frag_smiles[0]} and {frag_smiles[1]}"
                })

        return disconnections

    def enumerate_functional_groups(self, scaffold: str, groups: List[str], positions: List[str] = None, max_variants: int = 5) -> List[Dict[str, Any]]:
        """Enumerate functional group combinations on a scaffold.

        Args:
            scaffold: Scaffold SMILES
            groups: List of functional groups to try
            positions: Positions to modify (for rings)
            max_variants: Maximum variants to return

        Returns:
            List of variant dictionaries with SMILES and descriptions
        """
        scaffold_mol = Chem.MolFromSmiles(scaffold)
        if scaffold_mol is None:
            raise ValueError(f"Invalid scaffold SMILES: {scaffold}")

        variants = []

        # Simple approach: try attaching each group to the scaffold
        for group in groups:
            try:
                # Create functional group
                if group == "OH":
                    group_smiles = "O"
                elif group == "NH2":
                    group_smiles = "N"
                elif group == "F":
                    group_smiles = "F"
                elif group == "Cl":
                    group_smiles = "Cl"
                elif group == "Br":
                    group_smiles = "Br"
                elif group == "NO2":
                    group_smiles = "N(=O)O"
                else:
                    continue

                # For benzene-like scaffolds, try different positions
                if scaffold.lower().startswith("c1ccccc1"):
                    # Try ortho, meta, para positions
                    positions_to_try = [1, 2, 4] if positions is None else [int(p) for p in positions if p.isdigit()]

                    for pos in positions_to_try:
                        try:
                            # Create modified scaffold
                            modified_smiles = self._attach_to_benzene_position(scaffold, group_smiles, pos)
                            if modified_smiles and len(variants) < max_variants:
                                variants.append({
                                    "smiles": modified_smiles,
                                    "scaffold": scaffold,
                                    "functional_group": group,
                                    "position": pos,
                                    "description": f"{scaffold} with {group} at position {pos}"
                                })
                        except Exception:
                            continue
                else:
                    # For non-aromatic scaffolds, try terminal attachment
                    try:
                        modified_smiles = self._attach_terminal_group(scaffold, group_smiles)
                        if modified_smiles and len(variants) < max_variants:
                            variants.append({
                                "smiles": modified_smiles,
                                "scaffold": scaffold,
                                "functional_group": group,
                                "position": "terminal",
                                "description": f"{scaffold} with terminal {group}"
                            })
                    except Exception:
                        continue

            except Exception:
                continue

        return variants

    def _attach_to_benzene_position(self, benzene_smiles: str, group_smiles: str, position: int) -> Optional[str]:
        """Attach group to specific benzene position."""
        # This is a simplified implementation
        # For position 1 (ortho to existing group if present, or just position 1)
        if position == 1:
            return f"c1c({group_smiles})cccc1"
        elif position == 2:
            return f"c1cc({group_smiles})ccc1"
        elif position == 3:
            return f"c1ccc({group_smiles})cc1"
        elif position == 4:
            return f"c1cccc({group_smiles})c1"
        return None

    def _attach_terminal_group(self, scaffold_smiles: str, group_smiles: str) -> Optional[str]:
        """Attach group to terminal position."""
        # Simple approach: just concatenate
        return f"{scaffold_smiles}{group_smiles}"


class BatchProcessor:
    """Efficient batch processing of multiple molecules."""

    def __init__(self):
        pass

    def process_smiles_file(self, input_file: str, operation: str = "validate") -> Dict[str, Any]:
        """Process a file containing SMILES strings.

        Args:
            input_file: Path to input file (SMILES format)
            operation: Operation to perform ("validate", "canonicalize", etc.)

        Returns:
            Processing results
        """
        results = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "processed": [],
            "errors": []
        }

        try:
            with open(input_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    results["total"] += 1

                    # Extract SMILES (assume first column for now)
                    smiles = line.split()[0]

                    try:
                        if operation == "validate":
                            is_valid, error = SMILESUtilities.validate_smiles(smiles)
                            if is_valid:
                                results["valid"] += 1
                                results["processed"].append({"smiles": smiles, "valid": True})
                            else:
                                results["invalid"] += 1
                                results["processed"].append({"smiles": smiles, "valid": False, "error": error})
                        elif operation == "canonicalize":
                            canon_smiles = SMILESUtilities.canonicalize_smiles(smiles)
                            results["processed"].append({"original": smiles, "canonical": canon_smiles})
                        else:
                            results["processed"].append({"smiles": smiles, "operation": operation})

                    except Exception as e:
                        results["errors"].append(f"Line {line_num}: {str(e)}")

        except FileNotFoundError:
            raise ValueError(f"Input file not found: {input_file}")

        return results

    def calculate_descriptors_batch(self, smiles_list: List[str], descriptors: List[str] = None) -> List[Dict[str, Any]]:
        """Calculate molecular descriptors for multiple molecules.

        Args:
            smiles_list: List of SMILES strings
            descriptors: List of descriptor names to calculate

        Returns:
            List of descriptor dictionaries
        """
        if descriptors is None:
            descriptors = ["MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA"]

        results = []

        for smiles in smiles_list:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                results.append({"smiles": smiles, "error": "Invalid SMILES"})
                continue

            desc_values = {}
            for desc_name in descriptors:
                try:
                    desc_func = getattr(Descriptors, desc_name, None)
                    if desc_func:
                        desc_values[desc_name] = desc_func(mol)
                    else:
                        desc_values[desc_name] = None
                except Exception as e:
                    desc_values[desc_name] = f"Error: {str(e)}"

            results.append({
                "smiles": smiles,
                "descriptors": desc_values
            })

        return results

    def filter_by_substructure(self, smiles_list: List[str], pattern: str) -> List[str]:
        """Filter molecules containing a specific substructure.

        Args:
            smiles_list: List of SMILES strings
            pattern: SMARTS pattern to search for

        Returns:
            Filtered list of SMILES
        """
        query = Chem.MolFromSmarts(pattern)
        if query is None:
            query = Chem.MolFromSmiles(pattern)
            if query is None:
                raise ValueError(f"Invalid pattern: {pattern}")

        filtered = []
        for smiles in smiles_list:
            mol = Chem.MolFromSmiles(smiles)
            if mol and mol.HasSubstructMatch(query):
                filtered.append(smiles)

        return filtered

    def generate_homologous_series(self, base_smiles: str, extension: str, count: int) -> List[Dict[str, Any]]:
        """Generate a homologous series by extending a base molecule.

        Args:
            base_smiles: Starting molecule SMILES
            extension: Group to add (e.g., "CH2", "CH2CH2")
            count: Number of homologs to generate

        Returns:
            List of homolog molecules with SMILES and descriptions
        """
        series = []
        current_smiles = base_smiles

        for i in range(count):
            mol = Chem.MolFromSmiles(current_smiles)
            if mol is None:
                break

            series.append({
                "smiles": current_smiles,
                "index": i + 1,
                "name": f"Homolog {i + 1}",
                "description": f"Homologous series member {i + 1}"
            })

            # Extend by adding the extension group
            if extension == "CH2":
                # Add methylene group - find terminal carbon
                # This is a simplified approach
                current_smiles = f"{current_smiles}C"
            elif extension == "CH2CH2":
                current_smiles = f"{current_smiles}CC"
            else:
                # Generic extension
                current_smiles = f"{current_smiles}{extension}"

        return series

    def scan_functional_groups(self, scaffold: str, groups: List[str], positions: List[str] = None) -> List[Dict[str, Any]]:
        """Scan functional group combinations on a scaffold.

        Args:
            scaffold: Scaffold SMILES
            groups: Functional groups to attach
            positions: Positions to try (for rings)

        Returns:
            List of all combinations with SMILES and descriptions
        """
        combinations = []

        if positions is None:
            positions = ["para"]  # Default for benzene

        for group in groups:
            for position in positions:
                try:
                    # Use FragmentOperations for this
                    frag_ops = FragmentOperations()
                    variants = frag_ops.enumerate_functional_groups(scaffold, [group], [position], max_variants=1)

                    for variant in variants:
                        combinations.append({
                            "scaffold": scaffold,
                            "functional_group": group,
                            "position": position,
                            "smiles": variant["smiles"],
                            "description": variant["description"]
                        })

                except Exception as e:
                    logger.debug(f"Failed to create {group} at {position}: {e}")
                    continue

        return combinations


class AnalysisEngine:
    """Advanced molecular analysis using RDKit capabilities."""

    def __init__(self):
        pass

    def analyze_molecule(self, smiles: str) -> Dict[str, Any]:
        """Comprehensive molecular analysis.

        Args:
            smiles: SMILES string

        Returns:
            Analysis results
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")

        results = {
            "smiles": smiles,
            "valid": True,
            "properties": {},
            "structure": {},
            "descriptors": {}
        }

        # Basic properties
        results["properties"]["num_atoms"] = mol.GetNumAtoms()
        results["properties"]["num_bonds"] = mol.GetNumBonds()
        results["properties"]["num_rings"] = mol.GetRingInfo().NumRings()

        # Molecular descriptors
        results["descriptors"]["molecular_weight"] = Descriptors.MolWt(mol)
        results["descriptors"]["logp"] = Descriptors.MolLogP(mol)
        results["descriptors"]["tpsa"] = Descriptors.TPSA(mol)
        results["descriptors"]["h_bond_donors"] = Descriptors.NumHDonors(mol)
        results["descriptors"]["h_bond_acceptors"] = Descriptors.NumHAcceptors(mol)
        results["descriptors"]["rotatable_bonds"] = Descriptors.NumRotatableBonds(mol)

        # Chiral centers
        try:
            from rdkit.Chem import FindMolChiralCenters
            chiral_centers = FindMolChiralCenters(mol, includeUnassigned=True)
            results["structure"]["chiral_centers"] = len(chiral_centers)
            results["structure"]["chiral_center_details"] = chiral_centers
        except Exception:
            results["structure"]["chiral_centers"] = 0

        # Fingerprints
        try:
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=1024)
            results["fingerprints"] = {
                "morgan_radius_2": fp.ToBitString()
            }
        except Exception:
            results["fingerprints"] = {}

        return results

    def detect_chemistry_problems(self, smiles: str) -> List[str]:
        """Detect potential chemistry problems in a molecule.

        Args:
            smiles: SMILES string

        Returns:
            List of problem descriptions
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ["Invalid SMILES string"]

        problems = []

        try:
            from rdkit.Chem import DetectChemistryProblems
            chemistry_problems = DetectChemistryProblems(mol)

            for problem in chemistry_problems:
                problems.append(f"{problem.GetType()}: {problem.Message()}")

        except Exception as e:
            problems.append(f"Error detecting chemistry problems: {str(e)}")

        return problems


class SMILESUtilities:
    """SMILES validation, canonicalization, and utility functions."""

    @staticmethod
    def validate_smiles(smiles: str) -> Tuple[bool, str]:
        """Validate SMILES string.

        Args:
            smiles: SMILES string to validate

        Returns:
            (is_valid, error_message)
        """
        if not smiles or not smiles.strip():
            return False, "Empty SMILES string"

        try:
            mol = Chem.MolFromSmiles(smiles.strip())
            if mol is None:
                return False, "Invalid SMILES syntax"
            return True, ""
        except Exception as e:
            return False, str(e)

    @staticmethod
    def canonicalize_smiles(smiles: str) -> str:
        """Convert SMILES to canonical form.

        Args:
            smiles: Input SMILES

        Returns:
            Canonical SMILES string
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")

        return Chem.MolToSmiles(mol, canonical=True)

    @staticmethod
    def smiles_to_molfile(smiles: str) -> str:
        """Convert SMILES to MOL file format.

        Args:
            smiles: SMILES string

        Returns:
            MOL file content as string
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")

        return Chem.MolToMolBlock(mol)

    @staticmethod
    def smiles_to_inchi(smiles: str) -> str:
        """Convert SMILES to InChI.

        Args:
            smiles: SMILES string

        Returns:
            InChI string
        """
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                raise ValueError(f"Invalid SMILES: {smiles}")

            from rdkit.Chem import inchi
            return inchi.MolToInchi(mol)
        except Exception as e:
            raise ValueError(f"InChI conversion failed: {str(e)}")


class RDKitBuilderService:
    """Main service class coordinating all RDKit operations."""

    def __init__(self):
        self.scaffold_lib = ScaffoldLibrary()
        self.structure_builder = StructureBuilder()
        self.fragment_ops = FragmentOperations()
        self.batch_processor = BatchProcessor()
        self.analysis_engine = AnalysisEngine()

    def get_scaffold(self, name: str) -> Optional[Dict[str, Any]]:
        """Get scaffold by name."""
        return self.scaffold_lib.get_scaffold(name)

    def build_molecule(self, description: Dict[str, Any]) -> str:
        """Build molecule from description.

        Args:
            description: Dictionary describing the molecule to build

        Returns:
            SMILES string
        """
        # This is a simplified implementation - could be expanded
        # with LLM integration for complex descriptions

        build_type = description.get("type", "scaffold")

        if build_type == "scaffold":
            scaffold_name = description.get("scaffold")
            scaffold = self.get_scaffold(scaffold_name)
            if scaffold:
                return scaffold["smiles"]
            raise ValueError(f"Unknown scaffold: {scaffold_name}")

        elif build_type == "chain":
            return self.structure_builder.build_chain(
                description.get("carbons", 1),
                description.get("terminal_group", "H")
            )

        elif build_type == "ring":
            return self.structure_builder.build_ring(
                description.get("size", 6),
                description.get("aromatic", False),
                description.get("heteroatoms")
            )

        raise ValueError(f"Unknown build type: {build_type}")
