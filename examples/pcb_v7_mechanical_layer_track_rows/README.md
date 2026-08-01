# pcb_v7_mechanical_layer_track_rows

Generate a PcbDoc and a PcbLib footprint that each place one 1000 mil by 10 mil
vertical track on every ordinary numbered mechanical user layer in this public
authoring target: Mechanical1 through Mechanical53.

The authoring code uses `PcbLayerRef.mechanical(...)` and custom mechanical
display names. It does not pass raw serialized V7 saved-layer integers to
`layer=`.

This sample directly covers public issue
https://github.com/wavenumber-eng/altium_monkey/issues/23: a PcbLib footprint
with primitives on Mechanical17 and higher must save, reparse, and render to
SVG without collapsing those layers through the legacy Mechanical16 enum slot.

## What It Shows

1. High-level PcbDoc and PcbLib authoring with `PcbLayerRef.mechanical(...)`
2. Custom mechanical layer names for legacy and V7-only mechanical layers
3. Save/reparse verification for every track token and V7 saved-layer id
4. SVG metadata for V7-only mechanical layers without fake legacy layer ids
5. Highest-layer coverage with Mechanical53 in both PcbDoc and PcbLib

## Run

From the repository root:

```powershell
uv run python examples\pcb_v7_mechanical_layer_track_rows\pcb_v7_mechanical_layer_track_rows.py
```

## Output

```text
examples/pcb_v7_mechanical_layer_track_rows/output/pcb_v7_mechanical_layer_track_rows.PcbDoc
examples/pcb_v7_mechanical_layer_track_rows/output/pcb_v7_mechanical_layer_track_rows.PcbLib
examples/pcb_v7_mechanical_layer_track_rows/output/pcbdoc_mechanical_layer_track_rows.svg
examples/pcb_v7_mechanical_layer_track_rows/output/pcblib_mechanical_layer_track_rows.svg
examples/pcb_v7_mechanical_layer_track_rows/output/pcb_v7_mechanical_layer_track_rows.json
```
