# pcbdoc_create_flex_in_cutout

Create a fixture-backed advanced rigid-flex PcbDoc with a flex region inside a
board cutout.

This sample writes a recreated AD-style PcbDoc with one rigid substack, one
flex substack, a flex board region inside a rigid-board cutout, one bend line,
native cutout-region evidence, and mechanical split/region tracks. It also
emits exact AD-exported `.stackup` and `.stackupx` reference files, then reads
the PcbDoc back with `AltiumLayerStackDocument` and verifies the authored
topology.

## What It Shows

1. Building an `AltiumLayerStackDocument` for an advanced flex-in-cutout board
2. Assigning board regions to rigid and flex substacks with stable native ids
3. Writing native stack data through `PcbDocBuilder.set_layer_stack_document(...)`
4. Replaying board-cutout region and mechanical split-line evidence
5. Re-reading the generated PcbDoc through `AltiumPcbDoc`
6. Verifying board cutouts, regions, bend lines, mechanical evidence, exact primitive streams, and exact stackup exports

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_flex_in_cutout\pcbdoc_create_flex_in_cutout.py
```

## Output

```text
examples/pcbdoc_create_flex_in_cutout/output/pcbdoc_create_flex_in_cutout.PcbDoc
examples/pcbdoc_create_flex_in_cutout/output/pcbdoc_create_flex_in_cutout.stackup
examples/pcbdoc_create_flex_in_cutout/output/pcbdoc_create_flex_in_cutout.stackupx
examples/pcbdoc_create_flex_in_cutout/output/flex_in_cutout_manifest.json
```
