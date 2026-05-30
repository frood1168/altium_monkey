# pcbdoc_user_union

Create a user-defined PCB union over placed components and board primitives.

The sample loads a blank PcbDoc, places two footprints from local PcbLib files
as `TP1` and `MH1`, adds a free NPTH pad, via, STEP-backed 3D body, tracks,
arcs, a full circle, fill, solid region, and overlay text, groups those objects
into a named user union, saves the board, and reparses the output to verify the
union catalog and member references.

## What It Shows

1. `AltiumPcbDoc.from_file(...)`
2. `AltiumPcbLib.from_file(...)`
3. `AltiumPcbDoc.add_component_from_pcblib(...)`
4. `AltiumPcbDoc.add_pad(...)`
5. `AltiumPcbDoc.add_via(...)`
6. `AltiumPcbDoc.add_embedded_3d_model(...)`
7. `AltiumPcbDoc.add_track(...)`
8. `AltiumPcbDoc.add_arc(...)`
9. `AltiumPcbDoc.add_fill(...)`
10. `AltiumPcbDoc.add_region(...)`
11. `AltiumPcbDoc.add_text(...)`
12. `AltiumPcbDoc.create_user_union(...)`
13. `AltiumPcbDoc.user_unions`
14. `AltiumPcbDoc.save(...)`

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_user_union\pcbdoc_user_union.py
```

## Output

```text
examples/pcbdoc_user_union/output/pcbdoc_user_union.PcbDoc
examples/pcbdoc_user_union/output/pcbdoc_user_union.json
```

The JSON summary records the union name, union index, total member count, and
member counts by parsed PcbDoc collection.
