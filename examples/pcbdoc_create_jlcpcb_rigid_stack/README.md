# pcbdoc_create_jlcpcb_rigid_stack

Create a new PcbDoc from a Python-authored JLCPCB-style eight-layer rigid
stack. The example does not read a source `.stackupx` file; it models the
stackup rows, material properties, stackup settings, and TOP-to-BOTTOM layer
pair directly in Python with `AltiumLayerStackDocument.from_rigid_layer_rows`.
It uses semantic row constructors such as `AltiumRigidStackRowSpec.copper`,
`.prepreg`, `.core`, `.solder_mask`, and `.overlay` plus typed material,
placement, and stackup setting objects. It does not require raw StackupX type
GUIDs, .NET property type strings, stackup attribute tuples, or legacy layer
IDs.

The row sequence is based on JLCPCB `JLC081211-1080`: eight copper layers,
nine dielectric/prepreg/core rows, top/bottom solder mask, and overlay rows.

## Run

From the package root:

```powershell
uv run python examples\pcbdoc_create_jlcpcb_rigid_stack\pcbdoc_create_jlcpcb_rigid_stack.py
```

or with a normal Python environment that has `altium_monkey` installed:

```powershell
python examples\pcbdoc_create_jlcpcb_rigid_stack\pcbdoc_create_jlcpcb_rigid_stack.py
```

## Outputs

```text
examples/pcbdoc_create_jlcpcb_rigid_stack/output/pcbdoc_create_jlcpcb_rigid_stack.PcbDoc
examples/pcbdoc_create_jlcpcb_rigid_stack/output/pcbdoc_create_jlcpcb_rigid_stack.stackup
examples/pcbdoc_create_jlcpcb_rigid_stack/output/pcbdoc_create_jlcpcb_rigid_stack.stackupx
examples/pcbdoc_create_jlcpcb_rigid_stack/output/jlcpcb_rigid_stack_manifest.json
```

The manifest compares the authored stack with the generated PcbDoc, `.stackup`,
and `.stackupx` readbacks. A successful run prints `Semantic match: True`.
