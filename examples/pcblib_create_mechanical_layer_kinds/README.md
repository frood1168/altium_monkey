# pcblib_create_mechanical_layer_kinds

Create a metadata-only PcbLib footprint and assign the mechanical layer kinds
covered by the current PcbLib layer-kind fixtures, arranged for easy Altium UI
inspection.

## What It Shows

1. `AltiumPcbLib.set_mechanical_layer(...)`
2. `AltiumPcbLib.set_mechanical_layer_pair(...)`
3. `AltiumPcbLib.set_mechanical_layer_kind(...)`
4. `AltiumPcbLib.mechanical_layer_kinds`
5. `MechanicalLayerKind`
6. M1 through M32 mechanical layer registry entries
7. M2 through M9 standalone layer kinds such as Board Shape and Route Tool Path
8. M10/M11 through M30/M31 component-layer pairs
9. M2 through M31 semantic layer-kind assignments
10. Reopening the generated PcbLib to verify the registry, pairs, mapping stream,
    layer sets, Route Tool Path field, and zero footprint primitives

## Run

From the repository root:

```powershell
uv run python examples\pcblib_create_mechanical_layer_kinds\pcblib_create_mechanical_layer_kinds.py
```

## Output

```text
examples/pcblib_create_mechanical_layer_kinds/output/pcblib_create_mechanical_layer_kinds.PcbLib
examples/pcblib_create_mechanical_layer_kinds/output/pcblib_create_mechanical_layer_kinds.json
```
