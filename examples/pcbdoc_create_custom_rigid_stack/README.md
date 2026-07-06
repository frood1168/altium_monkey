# pcbdoc_create_custom_rigid_stack

Create a new PcbDoc with a custom four-layer rigid stack, save `.stackup` and
`.stackupx` interchange files from the same authored model, reparse everything,
and write a semantic comparison manifest.

This example demonstrates the model-backed rigid writer API:
`AltiumLayerStackDocument.from_rigid_layer_rows(...)`. The stack uses explicit
ordered physical rows, including overlay, solder-mask, copper, and adjacent
dielectric/prepreg rows.

## What It Shows

1. `AltiumRigidStackRowSpec`
2. `AltiumLayerStackDocument.from_rigid_layer_rows(...)`
3. Exporting the same authored model as `.stackup` and `.stackupx`
4. `PcbDocBuilder.set_layer_stack_document(...)`
5. `PcbDocBuilder.save(...)`
6. Reopening the generated PcbDoc with `AltiumPcbDoc.from_file(...)`
7. Comparing authored, PcbDoc, `.stackup`, and `.stackupx` readback semantics

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_custom_rigid_stack\pcbdoc_create_custom_rigid_stack.py
```

## Output

```text
examples/pcbdoc_create_custom_rigid_stack/output/pcbdoc_create_custom_rigid_stack.PcbDoc
examples/pcbdoc_create_custom_rigid_stack/output/pcbdoc_create_custom_rigid_stack.stackup
examples/pcbdoc_create_custom_rigid_stack/output/pcbdoc_create_custom_rigid_stack.stackupx
examples/pcbdoc_create_custom_rigid_stack/output/custom_rigid_stack_manifest.json
```
