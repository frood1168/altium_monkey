# pcbdoc_inspect_layer_stack

Inspect a PcbDoc, `.stackup`, or `.stackupx` layer stack with the
source-aware layer-stack model and write deterministic JSON.

This example is read-only. By default it loads the public blank PcbDoc asset,
builds an `AltiumLayerStackDocument`, writes a compact summary, and includes
the full debug JSON for the native stack evidence. You can also pass an
Altium Layer Stack Manager `.stackup` or `.stackupx` export to inspect the
interchange view through the same model.

## What It Shows

1. `AltiumPcbDoc.from_file(...)`
2. `AltiumLayerStackDocument.from_pcbdoc(...)`
3. `AltiumLayerStackDocument.from_stackup(...)`
4. `AltiumLayerStackDocument.from_stackupx(...)`
5. Reading physical layers, layer pairs, substacks, board-region counts, and
   impedance-profile counts
6. `AltiumLayerStackDocument.to_debug_json()`

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_inspect_layer_stack\pcbdoc_inspect_layer_stack.py
```

Inspect an exported stackup file:

```powershell
uv run python examples\pcbdoc_inspect_layer_stack\pcbdoc_inspect_layer_stack.py path\to\board.stackupx --output output\board_layer_stack.json
```

## Output

```text
examples/pcbdoc_inspect_layer_stack/output/layer_stack.json
```
