# pcbdoc_create_rigid_flex_impedance_backdrill

Create a fixture-backed nested rigid-flex PcbDoc with impedance profiles and
backdrill/via-span metadata.

This sample uses a neutral public spec derived from an AD-authored nested
rigid-flex fixture. It writes a recreated PcbDoc with seven substacks, three
branches, three bend lines, split-plane polygons, mechanical region evidence,
impedance profiles, transmission-line rows, and multiple layer-pair/via-span
definitions including backdrill spans. It also emits exact AD-exported
`.stackup` and `.stackupx` reference files, then reads the PcbDoc back with
`AltiumLayerStackDocument` and verifies the authored topology.

## What It Shows

1. Building an `AltiumLayerStackDocument` for nested advanced rigid-flex
2. Preserving impedance and transmission-line data in native PcbDoc stack data
3. Preserving layer-pair/via-span and backdrill metadata
4. Writing native stack data through `PcbDocBuilder.set_layer_stack_document(...)`
5. Replaying split-plane polygons, regions, and mechanical split-line evidence
6. Verifying branch topology, bends, impedance data, layer pairs, native geometry, and exact stackup exports

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_create_rigid_flex_impedance_backdrill\pcbdoc_create_rigid_flex_impedance_backdrill.py
```

## Output

```text
examples/pcbdoc_create_rigid_flex_impedance_backdrill/output/pcbdoc_create_rigid_flex_impedance_backdrill.PcbDoc
examples/pcbdoc_create_rigid_flex_impedance_backdrill/output/pcbdoc_create_rigid_flex_impedance_backdrill.stackup
examples/pcbdoc_create_rigid_flex_impedance_backdrill/output/pcbdoc_create_rigid_flex_impedance_backdrill.stackupx
examples/pcbdoc_create_rigid_flex_impedance_backdrill/output/rigid_flex_impedance_backdrill_manifest.json
```
