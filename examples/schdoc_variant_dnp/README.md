# schdoc_variant_dnp

Scan every schematic in a project for components marked DNP, then set those
components as **Not Fitted** in a named variant inside the `.PrjPcb` file.

A component counts as DNP when either the `sch_layout_dnp` control parameter
equals `DNP`, or a value parameter (Value, Resistance, Capacitance, Inductance,
Voltage, Current, Power, Tolerance) equals `DNP`. Components previously marked
Not Fitted that no longer carry a DNP marker are cleared. Hierarchical sheet
symbol UIDs are resolved so each variation entry uses Altium's native
`\SHEETSYM\COMPUID` format.

## What It Shows

1. resolving reachable `.SchDoc` paths from a `.PrjPcb` project
2. detecting DNP components across a hierarchical schematic
3. rewriting `VariationN` / `ParamVariationN` entries in a project variant in
   Altium-native ordering
4. saving a modified project copy plus a JSON summary manifest

## Run

Arg-free demo (uses the bundled RT_SUPER_C1 sample project and its
`1v8-2x3USON` variant):

```powershell
uv run python examples\schdoc_variant_dnp\schdoc_variant_dnp.py
```

Real usage against your own project and variant:

```powershell
uv run python examples\schdoc_variant_dnp\schdoc_variant_dnp.py path\to\MyProject.PrjPcb "Initial Design"
```

## Input

With no arguments the sample reads the bundled project:

```text
examples/assets/projects/rt_super_c1/RT_SUPER_C1.PrjPcb
```

and its reachable `.SchDoc` files. The asset files are never modified.

## Output

The script writes a modified project copy and a summary manifest:

```text
examples/schdoc_variant_dnp/output/RT_SUPER_C1.PrjPcb
examples/schdoc_variant_dnp/output/schdoc_variant_dnp_manifest.json
```

Review the copied `.PrjPcb`, then copy it over the original (with Altium closed).
The manifest records the source and output paths, the target variant, the DNP
components found, and how many Not Fitted flags were set or reset.
