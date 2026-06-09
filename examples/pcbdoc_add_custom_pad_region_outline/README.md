# pcbdoc_add_custom_pad_region_outline

Add arc-bearing shape outlines to PcbDoc regions and custom pads.

The sample creates a rectangular board outline, adds a shape-based copper
region whose outline uses native extended vertices, then adds a PcbDoc custom
pad with a matching arc-capable primary body and a separate bottom-layer body.
It reparses the written board and writes a JSON manifest from the parsed
records.

## What It Shows

1. `AltiumPcbDoc.from_file(...)`
2. `AltiumPcbDoc.add_region(..., outline_vertices=...)`
3. `AltiumPcbDoc.add_custom_pad(..., outline_vertices=...)`
4. `PcbCustomPadLayerShapeSpec(..., outline_vertices=...)`
5. Reparse checks for arc vertices and `CustomShapes/Data`
6. `AltiumPcbDoc.save(...)`

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_add_custom_pad_region_outline\pcbdoc_add_custom_pad_region_outline.py
```

## Output

```text
examples/pcbdoc_add_custom_pad_region_outline/output/pcbdoc_add_custom_pad_region_outline.PcbDoc
examples/pcbdoc_add_custom_pad_region_outline/output/pcbdoc_add_custom_pad_region_outline.json
```
