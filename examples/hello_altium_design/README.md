# hello_altium_design

Load an existing Altium project with `AltiumDesign`, print the available
variants and document paths, and write the full design JSON plus BOM/netlist
artifacts to disk.

This example is intentionally small. It is meant to show the public
project-loading and design-analysis API, not internal netlist plumbing.

## What It Shows

1. `AltiumDesign.from_prjpcb(...)`
2. `AltiumDesign.to_json(...)`
3. `AltiumDesign.to_netlist(...)`
4. `AltiumDesign.to_bom(...)`
5. `AltiumDesign.get_variants(...)`
6. Reading compiled net `winning_name`, `alternate_names`, and
   `name_sources` from `design.a2` physical pages
7. Reading `physical_pages` to find physical documents, page-local components,
   page-local nets, and repeated/channel-safe SVG identities
8. Rendering project-aware physical schematic SVGs with
   `AltiumDesign.to_physical_svg(physical_page_id)`

## Run

From the repository root:

```powershell
uv run python examples\hello_altium_design\hello_altium_design.py
```

## Input Project

This sample uses the redistributable project staged at:

```text
examples/assets/projects/rt_super_c1/RT_SUPER_C1.PrjPcb
```

## Output

The script writes:

```text
examples/hello_altium_design/output/project_summary.json
examples/hello_altium_design/output/altium_design.json
examples/hello_altium_design/output/physical_pages_summary.json
examples/hello_altium_design/output/physical_svg_manifest.json
examples/hello_altium_design/output/physical_svgs/<physical-page>.svg
examples/hello_altium_design/output/netlist.json
examples/hello_altium_design/output/compiled_net_name_examples.json
examples/hello_altium_design/output/bom_all.json
examples/hello_altium_design/output/variant_boms/<variant>.json
```

`altium_design.json` uses the `altium_monkey.design.a2` schema. `netlist.json`
uses the `altium_monkey.netlist.a0` schema.

`physical_pages_summary.json` is a compact consumer-oriented view of the
`design.a2` physical-page contract. It shows the stable identity rule:

```text
physical_page.id + svg_id
```

For simple projects this decays to one physical page per source sheet. For
repeated sheets or channelized projects, the same source SVG ID can appear on
multiple physical pages with different resolved component designators.

`physical_svg_manifest.json` lists the SVG files written through
`AltiumDesign.to_physical_svg(physical_page_id)`. These SVGs render source
schematic geometry in project compile context, so resolved physical designators
are used before text measurement and SVG emission.

`compiled_net_name_examples.json` demonstrates the canonical pattern for
compiled net names: `winning_name` is the selected compiled net name, while
`alternate_names` and `name_sources` expose other labels or source objects that
contributed to the same compiled net. It can be empty for projects without
alternate names.

When the project references a PcbDoc, `altium_design.json` also includes the
optional root `pnp` block with pick-and-place placements in millimeters. See
[`pcbdoc_pick_n_place`](../pcbdoc_pick_n_place/README.md) for a
focused CSV/JSON pick-and-place example.
