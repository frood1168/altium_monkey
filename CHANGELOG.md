# Changelog

All notable changes to the schematic/PCB cleanup tools are recorded here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — branch `sch-cleanup-tools`

### 2026-06-30

#### Schematic style tool (`examples/schdoc_style/`)
- **Differentiate named parameter styles.** `schdoc_style_extract.py` now routes
  only `Resistance`, `Capacitance`, `Inductance`, and `PartNumber` into their own
  `[component.parameter.<Name>]` subsections (gated by `_NAMED_PARAMETER_SECTIONS`).
  All other parameters continue to fall under the default `[component.parameter]`.
- The apply side (`schdoc_style.py`) already supported named-vs-default fallback:
  any property omitted from a named subsection falls back to `[component.parameter]`,
  and parameters not in the named set use the default.
- Added the four named subsections to `examples/assets/style.toml`.

#### `run_schdoc_style.ps1`
- Reworked to apply the **existing** `style.toml` only — no extract step.
- Styled SchDocs are staged to `clean/` and the directory is **kept** (not deleted).
- Originals are snapshotted to `history/<timestamp>/` before being overwritten in
  place with the styled versions.

#### DNP handling
- **`sch_layout_dnp` now drives the No-BOM component kind.** In
  `examples/schdoc_param_layout/schdoc_param_layout.py`, `_is_dnp()` returns `True`
  when the `sch_layout_dnp` control parameter equals `"DNP"`, in addition to the
  existing value-parameter check (`value/resistance/inductance/capacitance/
  voltage/current/power/tolerance`). Components are set to `STANDARD_NO_BOM`
  accordingly, and this composes with the existing `_apply_dnp_swap` visual swap.
- **Variant DNP tool kept in sync.** `examples/schdoc_variant_dnp/schdoc_variant_dnp.py`
  `_is_dnp()` was updated identically so `sch_layout_dnp == "DNP"` also flags a
  component as Not Fitted in the named project variant.

#### New: `run_variant_dnp.ps1`
- PowerShell wrapper for the variant DNP tool. Takes `-ProjectDir` and `-Variant`.
- Updates the named variant's Not Fitted set in the `.PrjPcb`, backs up the
  original `.PrjPcb` to `history/<timestamp>/`, then copies the updated `.PrjPcb`
  from `clean/` back in place.
- **Altium must be closed** for the in-place overwrite of the `.PrjPcb`.
