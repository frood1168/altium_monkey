# pcbdoc_create_rigid_flex_branch

Create a fixture-derived rigid-flex PcbDoc with one branch topology.

The generated board recreates a known synthetic topology with a main rigid
stack, a two-layer flex extension, and a rigid extension. The sample builds the
typed `AltiumLayerStackDocument` from a public JSON spec asset, writes a PcbDoc
plus exact AD-exported `.stackup` and `.stackupx` reference files, then reads
the PcbDoc back and verifies the substack, board-region, bend-line, branch
topology, split-plane polygons, and track evidence.

## What It Shows

1. Building a rigid/flex/rigid substack chain from a portable spec
2. Creating a branch with three branch sections
3. Preserving a bend line on the fixture's default/end region
4. Writing native PcbDoc stack data and embedded StackupX branch data
5. Replaying fixture polygon and track evidence
6. Re-reading the generated PcbDoc with `AltiumLayerStackDocument`
7. Verifying exact `.stackup` and `.stackupx` reference output

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_rigid_flex_branch\pcbdoc_create_rigid_flex_branch.py
```

## Output

```text
examples/pcbdoc_create_rigid_flex_branch/output/pcbdoc_create_rigid_flex_branch.PcbDoc
examples/pcbdoc_create_rigid_flex_branch/output/pcbdoc_create_rigid_flex_branch.stackup
examples/pcbdoc_create_rigid_flex_branch/output/pcbdoc_create_rigid_flex_branch.stackupx
examples/pcbdoc_create_rigid_flex_branch/output/rigid_flex_branch_manifest.json
```
