# pcbdoc_create_rigid_flex_two_branch

Create a fixture-backed advanced rigid-flex PcbDoc with east and west branch
extensions.

This sample uses a neutral public spec derived from an AD-authored two-branch
fixture. It writes a recreated PcbDoc with one main rigid stack, east and west
flex extensions, east and west rigid end stacks, two branch roots, one board
region carrying two bend lines, split-plane polygons, and mechanical
split-line evidence. It also emits exact AD-exported `.stackup` and
`.stackupx` reference files, then reads the PcbDoc back with
`AltiumLayerStackDocument` and verifies the authored topology.

## What It Shows

1. Building an `AltiumLayerStackDocument` with multiple branch roots
2. Preserving parent branch linkage and branch-section-stack metadata
3. Writing native stack data through `PcbDocBuilder.set_layer_stack_document(...)`
4. Replaying split-plane polygons and mechanical split-line evidence
5. Re-reading the generated PcbDoc through `AltiumPcbDoc`
6. Verifying branch topology, bend ownership, native geometry, and exact stackup exports

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_rigid_flex_two_branch\pcbdoc_create_rigid_flex_two_branch.py
```

## Output

```text
examples/pcbdoc_create_rigid_flex_two_branch/output/pcbdoc_create_rigid_flex_two_branch.PcbDoc
examples/pcbdoc_create_rigid_flex_two_branch/output/pcbdoc_create_rigid_flex_two_branch.stackup
examples/pcbdoc_create_rigid_flex_two_branch/output/pcbdoc_create_rigid_flex_two_branch.stackupx
examples/pcbdoc_create_rigid_flex_two_branch/output/rigid_flex_two_branch_manifest.json
```
