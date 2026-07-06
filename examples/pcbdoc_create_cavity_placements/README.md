# pcbdoc_create_cavity_placements

Create a fixture-backed rigid PcbDoc and place one cavity footprint on top,
bottom, and internal copper layers.

This sample recreates a rigid cavity-placement board: component records on
`TOP`, `MID1`, `MID2`, `MID4`, and `BOTTOM`; the copied
`R0402_0.40MM_HD.PcbLib` footprint inserted onto those layers; Mechanical 1
cavity-definition regions with a 0.5 mm cavity height; shape-based cavity
companions; one shared embedded STEP model payload; and simple rigid
layer-stack dielectric thicknesses plus copper component-placement settings.
The component designator text records also use top-overlay placement, font
size, text-box, and snap-point metadata; component comments are hidden.

## What It Shows

1. Loading a fixture-backed rigid `AltiumLayerStackDocument`
2. Loading and copying `R0402_0.40MM_HD.PcbLib`
3. Placing the footprint on internal component layers with `PcbDocBuilder`
4. Preserving board-side cavity regions and shape-based companions
5. Copying one embedded STEP model from the source PcbLib into the PcbDoc
6. Preserving AD-authored copper component-placement policy
7. Preserving the fixture-style designator text layout while hiding comments
8. Reopening the generated PcbDoc and writing a verification manifest

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_cavity_placements\pcbdoc_create_cavity_placements.py
```

## Output

```text
examples/pcbdoc_create_cavity_placements/output/pcbdoc_create_cavity_placements.PcbDoc
examples/pcbdoc_create_cavity_placements/output/R0402_0.40MM_HD.PcbLib
examples/pcbdoc_create_cavity_placements/output/pcbdoc_create_cavity_placements.stackup
examples/pcbdoc_create_cavity_placements/output/pcbdoc_create_cavity_placements.stackupx
examples/pcbdoc_create_cavity_placements/output/cavity_placements_manifest.json
```
