# pcbdoc_create_layer_stack

Create a PcbDoc from the canonical empty-board layer stack model, save it, and
reparse it to verify semantic layer-stack equality.

This example demonstrates the first writer bridge for
`AltiumLayerStackDocument`. It does not author an arbitrary stackup yet; it
regenerates the canonical empty-board stack rows from typed model values and
preserves the surrounding board-data scaffold.

## What It Shows

1. `AltiumLayerStackDocument.canonical_empty()`
2. `AltiumLayerStackDocument.to_canonical_empty_board_data()`
3. `PcbDocBuilder`
4. `PcbDocBuilder.save(...)`
5. Reopening the generated PcbDoc with `AltiumPcbDoc.from_file(...)`
6. Comparing authored and readback layer-stack semantics

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_layer_stack\pcbdoc_create_layer_stack.py
```

## Output

```text
examples/pcbdoc_create_layer_stack/output/pcbdoc_create_layer_stack.PcbDoc
examples/pcbdoc_create_layer_stack/output/layer_stack_manifest.json
```
