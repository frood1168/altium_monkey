# pcbdoc_create_from_stackup_files

Create new PcbDoc files from Altium `.stackup` and `.stackupx` layer-stack
exports, then reparse the generated PcbDocs to verify layer-stack semantics.

This example demonstrates the interchange-file authoring path for simple rigid
boards:

1. `AltiumLayerStackDocument.from_stackup(...)`
2. `AltiumLayerStackDocument.from_stackupx(...)`
3. `PcbDocBuilder.set_layer_stack_document(...)`
4. `PcbDocBuilder.save(...)`
5. Reopening the generated PcbDocs with `AltiumPcbDoc.from_file(...)`
6. Comparing imported and readback layer families, names, and thickness fields

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_from_stackup_files\pcbdoc_create_from_stackup_files.py
```

## Input

```text
examples/pcbdoc_create_from_stackup_files/input/rigid_source.stackup
examples/pcbdoc_create_from_stackup_files/input/rigid_source.stackupx
```

## Output

```text
examples/pcbdoc_create_from_stackup_files/output/from_stackup.PcbDoc
examples/pcbdoc_create_from_stackup_files/output/from_stackupx.PcbDoc
examples/pcbdoc_create_from_stackup_files/output/from_stackup_files_manifest.json
```
