---
name: molecule-svg-drawing
description: Conventions for drawing accurate 2D skeletal chemical structures in SVG.
  Covers zigzag backbones, wedge/dashed-wedge bonds, heteroatom labels, stereochemistry
  notation, and common pitfalls.
---
<!--
SYNCED FILE: Generated from the private ChemIllusion repo.
Source key: molecule-svg-drawing
Do not edit directly unless submitting a patch proposal.
Public edits may be overwritten by the next export.
-->

# Molecule SVG Drawing Skill

Rules and conventions for rendering chemically accurate 2D skeletal structures in inline SVG (e.g., for Remotion compositions, storyboards, or static assets).

## Backbone Geometry

- **Zigzag convention:** Carbon chains are drawn as zigzags with ~120° angles between bonds.
- **Bond length:** Keep consistent (~40-50 SVG units between vertices).
- **Trigonal-planar centers:** Carbonyl carbons, formamide nitrogens, alkenes, and aromatic atoms should keep substituent bonds roughly 120° apart. Do not turn an sp2 center into a straight line to simplify label placement.
- **Implicit carbons:** Vertices without labels represent carbon atoms. Only heteroatoms (N, O, S, etc.) and their hydrogens are labeled.

## Bond Types

### Regular Bonds

- Solid lines, stroke-width ~2.0-2.5.
- Double bonds: two parallel lines (offset ~3 units), one slightly thinner.
- For bonds connected to explicit atom or group labels, use the label's atom-center coordinate as the endpoint. Draw the bond behind the text and place the label over it with centered anchors so the bond visually reaches the atom center. Do not shorten bonds to the text bounding box edge or leave a gap before the label.
- For double bonds to labeled atoms, offset the two strokes symmetrically around the atom-center-to-atom-center line.

### Wedge Bonds (Stereo — Coming Toward Viewer)

- **Solid filled triangle** (`<polygon>`).
- **Narrow (pointed) end at the stereocenter**, wide end at the substituent.
- Width: ~30% narrower than the bond length (roughly ±8 units at the wide end for a 36-unit bond).
- Example: `<polygon points="128.5,58 131.5,58 138,24 122,24" fill="#cbd5e1" />`

### Dashed Wedge Bonds (Stereo — Going Away From Viewer)

- **Series of horizontal dashes** (perpendicular to the bond axis).
- Dashes are **narrow at the stereocenter, wider toward the substituent**.
- ~9 evenly spaced horizontal `<line>` elements.
- Each line widens symmetrically from center: e.g., `x1=130±0.5` at bottom to `x1=130±8` at top.
- Example:
  ```svg
  <line x1="129.5" y1="56" x2="130.5" y2="56" stroke="#cbd5e1" stroke-width="1.6"/>
  <line x1="129" y1="52" x2="131" y2="52" stroke="#cbd5e1" stroke-width="1.6"/>
  ...
  <line x1="122" y1="24" x2="138" y2="24" stroke="#cbd5e1" stroke-width="1.6"/>
  ```

### Common Wedge Pitfalls

- The **wide end faces the substituent**, NOT the stereocenter. This is the most common mistake.
- Dashed wedge dashes are **horizontal** (perpendicular to the bond direction), never parallel to the bond.
- For vertical bonds, dashes are horizontal lines. For angled bonds, rotate dash orientation to stay perpendicular.

## Heteroatom Labels

- **Element symbol centered on the bond terminus.** The atom letter sits at the endpoint of the bond — not offset to one side.
- **Hydrogen counts** follow the element at the same font size, with numeric subscripts at a smaller font size trailing to the right.
- Example for NH₂:
  ```svg
  <text x="122" y="18" fill="#cbd5e1" fontSize="15" textAnchor="start" fontWeight="600">NH</text>
  <text x="147" y="22" fill="#cbd5e1" fontSize="10" textAnchor="start">2</text>
  ```
  Here, "N" is centered on the bond endpoint; "H" follows at the same size; "2" is a smaller subscript.
- **Font size:** Heteroatom labels should be noticeably larger than bond stroke width (e.g., font-size 15 with stroke-width 2.2).
- In skeletal formulas, always show explicit heteroatom labels with their hydrogens (NH₂, OH, SH, etc.), not just bare element symbols, unless the context is a very compact notation.

## Stereochemistry: SMILES ↔ Visual Mapping

| SMILES | Configuration | Visual            |
| ------ | ------------- | ----------------- |
| `@@`   | S             | Solid wedge bond  |
| `@`    | R             | Dashed wedge bond |

**Do not swap these.** `@@` is always one configuration, `@` is always the other configuration (for standard tetrahedral centers with CIP priority ordering in the SMILES). Looking at the chiral center from the direction of the "from" atom (as per atom order in SMILES), @ means "the other three atoms are listed anti-clockwise; @@ means clockwise.

## Color Conventions

- **Default: monochrome.** All bonds and atom labels in a single neutral color (e.g., `#cbd5e1` on dark backgrounds, `#374151` on light backgrounds).
- **Do not color atoms by element** unless specifically requested. Colored atoms compete with other visual signals (highlights, region colors in the fragment editor).
- When color is used on SMILES text (e.g., in the fragment editor), keep the structure preview monochrome to maintain focus.

## Dark Background Rendering

- Structure color: `#cbd5e1` (light slate gray).
- Background: `#111827` (near-black).
- Avoid pure white (`#ffffff`) for bonds — too harsh on dark backgrounds.

## SVG Best Practices

- Use `viewBox` for scalability; avoid fixed width/height on the SVG element.
- `preserveAspectRatio="xMidYMid meet"` for centered scaling.
- Use `fontFamily="system-ui, sans-serif"` for text elements.
- Group related elements (backbone, wedge, labels) logically for readability.

---
*Maintained by the [ChemIllusion](https://chemillusion.com) team as part of OpenMolClaw.*
