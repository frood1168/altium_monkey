# pcbdoc_create_flex_stiffener

Create a fixture-backed flex-only PcbDoc with top and bottom stiffener stack
regions.

This sample uses a neutral public spec derived from an AD-authored flex/stiffener
fixture. It writes a recreated PcbDoc with one flex main substack, two stiffener
substacks, coverlay rows, adhesive rows, one bend line, a rounded board cutout,
coverlay polygon definitions, and native region evidence for the
flex/stiffener extents. It also emits exact AD-exported `.stackup` and
`.stackupx` reference files, then reads the PcbDoc back with
`AltiumLayerStackDocument` and verifies the authored topology.

## What It Shows

1. Building an `AltiumLayerStackDocument` with flex/stiffener substacks
2. Assigning board regions to substacks with `AltiumStackRegion`
3. Writing native stack data through `PcbDocBuilder.set_layer_stack_document(...)`
4. Adding board-cutout and native region primitives with `PcbDocBuilder.add_region(...)`
5. Re-reading the generated PcbDoc through `AltiumPcbDoc`
6. Verifying stiffener layers, coverlay rows, regions, bends, cutouts, polygons, branch data, and exact stackup exports

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_flex_stiffener\pcbdoc_create_flex_stiffener.py
```

## Output

```text
examples/pcbdoc_create_flex_stiffener/output/pcbdoc_create_flex_stiffener.PcbDoc
examples/pcbdoc_create_flex_stiffener/output/pcbdoc_create_flex_stiffener.stackup
examples/pcbdoc_create_flex_stiffener/output/pcbdoc_create_flex_stiffener.stackupx
examples/pcbdoc_create_flex_stiffener/output/flex_stiffener_manifest.json
```
