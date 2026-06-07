# pcbdoc_create_rigid_flex_multibranch

Create a fixture-derived rigid-flex PcbDoc with multiple branch records.

The generated board recreates a known nested topology with east, west, and
west-extension branches. The sample builds the typed `AltiumLayerStackDocument`
from a public JSON spec asset, adds native region, polygon, and track evidence
for the extension areas, writes a PcbDoc plus exact AD-exported `.stackup` and
`.stackupx` reference files, then reads the PcbDoc back and verifies all
substacks, board regions, bend lines, parent branches, and branch sections.

## What It Shows

1. Building several rigid and flex substacks from a portable spec
2. Creating multiple branch records with parent-branch linkage
3. Assigning bend lines to separate flex regions
4. Replaying region, polygon, and track evidence for the extension areas
5. Writing native PcbDoc stack data and embedded StackupX branch data
6. Re-reading the generated PcbDoc with `AltiumLayerStackDocument`
7. Verifying exact `.stackup` and `.stackupx` reference output

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_rigid_flex_multibranch\pcbdoc_create_rigid_flex_multibranch.py
```

## Output

```text
examples/pcbdoc_create_rigid_flex_multibranch/output/pcbdoc_create_rigid_flex_multibranch.PcbDoc
examples/pcbdoc_create_rigid_flex_multibranch/output/pcbdoc_create_rigid_flex_multibranch.stackup
examples/pcbdoc_create_rigid_flex_multibranch/output/pcbdoc_create_rigid_flex_multibranch.stackupx
examples/pcbdoc_create_rigid_flex_multibranch/output/rigid_flex_multibranch_manifest.json
```
