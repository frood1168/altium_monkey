# pcbdoc_create_rigid_flex_branch_intrusion

Create a fixture-backed advanced rigid-flex PcbDoc with branch intrusion
settings.

This sample uses a neutral public spec derived from an AD-authored branch
intrusion fixture. It writes a recreated PcbDoc with a main rigid stack, a flex
extension, a rigid extension, explicit left/right intrusion values on the flex
branch section, split-plane polygons, mechanical split evidence, and one bend
line. It also emits exact AD-exported `.stackup` and `.stackupx` reference
files, then reads the PcbDoc back with `AltiumLayerStackDocument` and verifies
the authored topology.

## What It Shows

1. Building an `AltiumLayerStackDocument` for an advanced branch-chain board
2. Preserving branch-section-stack intrusion fields through PcbDoc authoring
3. Writing native stack data through `PcbDocBuilder.set_layer_stack_document(...)`
4. Replaying split-plane polygons and mechanical split-line evidence
5. Re-reading the generated PcbDoc through `AltiumPcbDoc`
6. Verifying branch topology, intrusion metadata, bend lines, native geometry, and exact stackup exports

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_rigid_flex_branch_intrusion\pcbdoc_create_rigid_flex_branch_intrusion.py
```

## Output

```text
examples/pcbdoc_create_rigid_flex_branch_intrusion/output/pcbdoc_create_rigid_flex_branch_intrusion.PcbDoc
examples/pcbdoc_create_rigid_flex_branch_intrusion/output/pcbdoc_create_rigid_flex_branch_intrusion.stackup
examples/pcbdoc_create_rigid_flex_branch_intrusion/output/pcbdoc_create_rigid_flex_branch_intrusion.stackupx
examples/pcbdoc_create_rigid_flex_branch_intrusion/output/rigid_flex_branch_intrusion_manifest.json
```
