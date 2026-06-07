# pcbdoc_create_custom_rigid_stack

Create a new PcbDoc with a custom four-layer rigid stack, save it, reparse it,
and write a semantic comparison manifest.

This example demonstrates the model-backed rigid writer API:
`AltiumLayerStackDocument.from_rigid_stack(...)`. The stack uses custom copper
names, copper thicknesses, dielectric names, dielectric thicknesses, material
names, dielectric constants, dielectric types, and loss tangent values.

## What It Shows

1. `AltiumRigidCopperLayerSpec`
2. `AltiumRigidDielectricLayerSpec`
3. `AltiumLayerStackDocument.from_rigid_stack(...)`
4. `PcbDocBuilder.set_layer_stack_document(...)`
5. `PcbDocBuilder.save(...)`
6. Reopening the generated PcbDoc with `AltiumPcbDoc.from_file(...)`
7. Comparing authored and readback layer-stack semantics

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_custom_rigid_stack\pcbdoc_create_custom_rigid_stack.py
```

## Output

```text
examples/pcbdoc_create_custom_rigid_stack/output/pcbdoc_create_custom_rigid_stack.PcbDoc
examples/pcbdoc_create_custom_rigid_stack/output/custom_rigid_stack_manifest.json
```
