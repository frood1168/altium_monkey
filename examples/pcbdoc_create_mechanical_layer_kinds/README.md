# pcbdoc_create_mechanical_layer_kinds

Create a metadata-only PcbDoc and assign the mechanical layer kinds covered by
the current PcbDoc layer-kind fixtures, arranged for easy Altium UI inspection.

## What It Shows

1. `AltiumPcbDoc.set_mechanical_layer(...)`
2. `AltiumPcbDoc.set_mechanical_layer_pair(...)`
3. `AltiumPcbDoc.set_mechanical_layer_kind(...)`
4. `MechanicalLayerKind`
5. M1 through M32 mechanical layer registry entries
6. M2 through M9 standalone layer kinds such as Board Shape and Route Tool Path
7. M10/M11 through M30/M31 component-layer pairs
8. M2 through M31 semantic layer-kind assignments
9. Reopening the generated PcbDoc to verify the registry, pairs, mapping stream,
   layer sets, Route Tool Path field, and zero primitive objects

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_mechanical_layer_kinds\pcbdoc_create_mechanical_layer_kinds.py
```

## Output

```text
examples/pcbdoc_create_mechanical_layer_kinds/output/pcbdoc_create_mechanical_layer_kinds.PcbDoc
examples/pcbdoc_create_mechanical_layer_kinds/output/pcbdoc_create_mechanical_layer_kinds.json
```
