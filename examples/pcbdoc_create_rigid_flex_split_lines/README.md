# pcbdoc_create_rigid_flex_split_lines

Create a fixture-backed Rigid-Flex 1.0 PcbDoc that uses split-line board
regions.

This sample writes a recreated AD-style Rigid-Flex 1.0 PcbDoc with one rigid
substack, one flex substack, two flex board regions, one rigid board region,
split-line evidence, coverlay polygons, and bend lines. It also emits exact
AD-exported `.stackup` and `.stackupx` reference files, then reads the PcbDoc back with
`AltiumLayerStackDocument` and verifies the authored topology.

## What It Shows

1. Building an `AltiumLayerStackDocument` for the older Rigid-Flex 1.0 flow
2. Assigning split-line board regions to rigid and flex substacks
3. Writing native stack data through `PcbDocBuilder.set_layer_stack_document(...)`
4. Replaying coverlay polygon and region evidence into a generated PcbDoc
5. Re-reading the generated PcbDoc through `AltiumPcbDoc`
6. Verifying regions, bends, split-line topology, native geometry, and exact stackup exports

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_rigid_flex_split_lines\pcbdoc_create_rigid_flex_split_lines.py
```

## Output

```text
examples/pcbdoc_create_rigid_flex_split_lines/output/pcbdoc_create_rigid_flex_split_lines.PcbDoc
examples/pcbdoc_create_rigid_flex_split_lines/output/pcbdoc_create_rigid_flex_split_lines.stackup
examples/pcbdoc_create_rigid_flex_split_lines/output/pcbdoc_create_rigid_flex_split_lines.stackupx
examples/pcbdoc_create_rigid_flex_split_lines/output/rigid_flex_split_lines_manifest.json
```
