# pcbdoc_create_impedance_rigid_stack

Create a new PcbDoc with a synthetic eight-layer rigid stack, representative
controlled-impedance profiles, and matching Layer Stack Manager interchange
exports.

This example demonstrates direct native PcbDoc authoring of
`IMPEDANCEPROFILE_V8_*` and `TRACEIMPEDANCE_V8_*` rows through
`AltiumLayerStackDocument.from_rigid_stack(...)`. It also writes `.stackup` and
`.stackupx` files from the same model and reparses all three outputs.

## What It Shows

1. `AltiumRigidCopperLayerSpec`
2. `AltiumRigidDielectricLayerSpec`
3. `AltiumImpedanceProfileSpec`
4. `AltiumTransmissionLineSpec`
5. `AltiumLayerStackDocument.from_rigid_stack(...)`
6. `PcbDocBuilder.set_layer_stack_document(...)`
7. `AltiumLayerStackDocument.to_stackup().write(...)`
8. `AltiumLayerStackDocument.to_stackupx().write(...)`
9. Reopening the generated PcbDoc, `.stackup`, and `.stackupx`
10. Comparing impedance profile and transmission-line semantics

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_impedance_rigid_stack\pcbdoc_create_impedance_rigid_stack.py
```

## Output

```text
examples/pcbdoc_create_impedance_rigid_stack/output/pcbdoc_create_impedance_rigid_stack.PcbDoc
examples/pcbdoc_create_impedance_rigid_stack/output/pcbdoc_create_impedance_rigid_stack.stackup
examples/pcbdoc_create_impedance_rigid_stack/output/pcbdoc_create_impedance_rigid_stack.stackupx
examples/pcbdoc_create_impedance_rigid_stack/output/impedance_rigid_stack_manifest.json
```
