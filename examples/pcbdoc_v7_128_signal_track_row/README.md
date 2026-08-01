# pcbdoc_v7_128_signal_track_row

Generate an AD 26.8 style PcbDoc with 128 signal layers and one vertical track
on every signal layer.

The sample first creates a local `.stackupx` file, re-imports that StackUpX
through `AltiumLayerStackDocument.from_stackupx(...)`, then uses
`PcbDocBuilder.set_layer_stack_document(...)` before adding primitives. Track
authoring uses `PcbLayerRef.top()`, `PcbLayerRef.mid_layer(...)`, and
`PcbLayerRef.bottom()` instead of serialized V7 saved-layer integers.

Each track is 1000 mil long, 10 mil wide, and separated by 20 mil so the
generated board opens in Altium as a compact row of vertical tracks.

## What It Shows

1. Programmatic StackUpX generation for a public, reproducible large stack
2. `AltiumLayerStackDocument.from_stackupx(...)`
3. `PcbDocBuilder.set_layer_stack_document(...)`
4. `PcbLayerRef.mid_layer(126)` authoring without collapsing to Bottom
5. PcbDoc save/reparse verification for every track layer token and V7 saved id
6. SVG metadata for V7-only signal layers without fake legacy layer ids
7. A JSON `signal_layers` table pairing each ref token with its stack display
   name and V7 saved-layer id

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_v7_128_signal_track_row\pcbdoc_v7_128_signal_track_row.py
```

## Output

```text
examples/pcbdoc_v7_128_signal_track_row/output/pcbdoc_v7_128_signal_track_row.PcbDoc
examples/pcbdoc_v7_128_signal_track_row/output/ad26_128_signal.stackupx
examples/pcbdoc_v7_128_signal_track_row/output/pcbdoc_v7_128_signal_track_row.svg
examples/pcbdoc_v7_128_signal_track_row/output/pcbdoc_v7_128_signal_track_row.json
```
