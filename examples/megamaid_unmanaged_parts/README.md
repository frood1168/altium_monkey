# megamaid_unmanaged_parts

Report the *unmanaged* parts in a design — components sourced from local
`.SchLib`/`.PcbLib` files rather than a managed online (vault) library.

## What a MegaMaid dump is

"MegaMaid" is an extraction pass that empties an Altium project into plain,
GUI-free artifacts under one output directory. This example reads the pieces it
needs:

```text
<megamaid_dir>/
  json/schdoc/*.json   one JSON per SchDoc; document.Objects[] holds Component
                       records with UniqueID, LibReference, DesignItemId,
                       VaultGUID, SourceLibraryName
  netlist/*.json       components[] keyed by svg_id (== SchDoc UniqueID) with
                       designator, footprint, description, parameters
                       (PartNumber, Manufacturer, Comment/Value)
  schlib/split/*.SchLib   per-symbol libraries, file stem == LibReference
  pcblib/split/*.PcbLib   per-footprint libraries, file stem == footprint
```

A component is treated as **unmanaged** when its `VaultGUID` is empty. Managed
(vault-sourced) components carry a GUID and are excluded from the report.

## What it does

1. Parses every `json/schdoc/*.json` and collects Component records.
2. Keeps the ones with no `VaultGUID` (the unmanaged parts).
3. Joins them to the netlist by `UniqueID` == `svg_id` for footprint / part
   number / designator.
4. Groups by `(LibReference, footprint, PartNumber)` so generic symbols (R, L,
   C) with different real parts stay separate, and lists their designators.
5. Notes which split `.SchLib` / `.PcbLib` files were extracted for each part.

## Run

Arg-free demo against the bundled fixture, from the package root:

```powershell
uv run python examples\megamaid_unmanaged_parts\megamaid_unmanaged_parts.py
```

Against a real MegaMaid output directory (positional override):

```powershell
uv run python examples\megamaid_unmanaged_parts\megamaid_unmanaged_parts.py path\to\MegaMaid\Rfboard --output report.json
```

## Inputs

- `sample_megamaid/` — a small hand-authored MegaMaid dump used as the default
  when no directory is given. It contains four unmanaged parts (a resistor
  shared across two sheets, an inductor, and an MCU with no PartNumber) plus one
  managed vault capacitor that is correctly filtered out, along with matching
  split `.SchLib` / `.PcbLib` placeholder files.

## Output

Written under `examples/megamaid_unmanaged_parts/output/`:

```text
output/unmanaged_parts_report.json
output/unmanaged_parts_report.csv
```

The JSON groups unique unmanaged parts with their designators and the split
library files found; the CSV is the same data as a spreadsheet-friendly table.
