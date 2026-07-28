# AltiumDesign

`AltiumDesign` is the project-level analysis surface. Use it when you need a
compiled view across a `.PrjPcb`, its schematic documents, variants, component
metadata, and schematic connectivity.

Use it when you need to:

1. load a project from `.PrjPcb`
2. emit the public design JSON contract
3. emit the public netlist JSON contract
4. inspect project netlist JSON
5. generate PCB-backed pick-and-place data when a PcbDoc is referenced
6. inspect project parameters, variants, components, sheets, and nets

## Public Contracts

`AltiumDesign.to_json(...)` emits `altium_monkey.design.a2`.

`AltiumDesign.to_netlist().to_json(...)` emits `altium_monkey.netlist.a0`.

`AltiumDesign.compile(force=False)` returns the beta compiled schematic model.
Project netlist, design JSON, and physical schematic rendering now derive from
this compiled model instead of a separate legacy hierarchy rewriter.

`AltiumDesign.to_physical_ir(physical_page_id)` and
`AltiumDesign.to_physical_svg(physical_page_id)` render one compiled physical
schematic page. Use these APIs for repeated sheets and multi-channel projects
where one logical `.SchDoc` appears multiple times with different resolved
designators such as `R1.1`, `R1.2`, `R1A`, or `R1B`.

`AltiumDesign.to_pnp(...)` returns pick-and-place entries from the project
PcbDoc. When a project has a PcbDoc, `AltiumDesign.to_json(...)` also includes
the same data under the optional root `pnp` field.

The default PnP coordinate mode is `altium-pick-place`. It matches Altium's
Pick Place export by taking the center of the bounding box of component-owned
pad anchor points and falling back to the component origin when a component has
no owned pads. Use `position_mode="component-origin"` when the footprint
placement origin is the desired coordinate. In design JSON, `pnp.position_mode`
records the selected mode and `center_x`/`center_y` are the selected PnP
position, not a generic geometric centroid.

The `schema` field is the contract version. These payloads do not use a root
`version` field.

The root `generator` field is `altium_monkey`.

See [schema contracts](schemas/index.md) for field-level contract notes.
See [compiled design migration](api_patterns/compiled_design.md) for guidance
when moving strict validators or SVG/component consumers from `altium_monkey.design.a1` to
`altium_monkey.design.a2`.

## Compiled vs Logical Views

Use `AltiumDesign` when a consumer needs the resolved physical project view.
For project inputs, these public surfaces derive from the compiled schematic
model:

1. `AltiumDesign.to_json(...)`
2. `AltiumDesign.to_netlist()`
3. `AltiumDesign.to_physical_ir(physical_page_id)`
4. `AltiumDesign.to_physical_svg(physical_page_id)`

This means repeated sheets, channel instances, annotation-driven designator
changes, and project net naming are resolved before data is emitted.

Use `AltiumSchDoc.to_ir()` or `AltiumSchDoc.to_svg()` when you intentionally
want the raw logical source sheet without project compile context. Those
single-sheet renderers do not know which physical page instance they represent,
so they do not substitute channel-resolved designators.

For projects without repeated physical sheet instances, the compiled project
view decays to the familiar one-source-sheet/one-physical-page shape. Consumers
can still use `physical_pages`; there is just no ambiguity to resolve.

## Compiled Physical Pages

`AltiumDesign.to_json(...)` includes a compact compiled physical-page
projection for user-facing tools:

1. `physical_pages`: one row per compiled physical schematic page, including
   page-local components, nets, graphical evidence, and hierarchy identity.
2. `indexes`: optional lookup maps when `include_indexes=True`.

`physical_pages` is always present in `design.a2`, including simple projects
without repeated sheets. In those projects it decays to the single physical
instance per source sheet.

`compile` and `diagnostics` are optional root fields. Request them with
`AltiumDesign.to_json(include_compile_metadata=True)` when a consumer needs
compile health, resolved options, annotation state, statistics, or warning/error
records. The default payload omits them to keep the normal design JSON compact.

The physical review identity is `physical_page.id` plus a graphical `svg_id`.
For repeated sheets, the same logical SVG element can represent more than one
physical component. In that case:

1. `indexes.svg_to_component` keeps only unambiguous one-to-one mappings for
   existing consumers.
2. `indexes.svg_to_components` maps a logical SVG ID to every physical
   component designator represented by that source element.
3. `indexes.physical_svg_to_components` maps
   `"{physical_page.id}|{svg_id}"` to the physical component designator(s) on
   that page.
4. `indexes.component_to_physical_page`,
   `indexes.physical_page_to_components`, and `indexes.physical_page_to_nets`
   provide direct page-level navigation.

For projects without repeated physical sheet instances, the public design JSON
decays to the historical component/net/SVG shape while still deriving the data
from the compiled model. For repeated or channelized projects, consumers should
use `physical_pages` and the physical SVG indexes instead of assuming a single
logical SVG ID identifies exactly one component.

Each `physical_pages[]` row is intended to be directly useful to review tools:

1. `id`: the compiled physical page id.
2. `physical_instance_path`: the resolved page path/name used by the compiler.
3. `source_sheet` / `source_path`: the logical SchDoc rendered for this page.
4. `components`: page-local resolved component rows with `designator`,
   `logical_designator`, `physical_designator`, `svg_id`, `dnp`, and `fitted`.
5. `nets`: page-local compiled nets with terminals, graphical pin/object IDs,
   aliases, and optional name-source provenance.

Net records may include `aliases` and `name_sources`. `aliases` are alternate
net names discovered while merging compiled connectivity. `name_sources`
records explain where candidate names came from, including the winning compiled
name, explicit labels, ports, sheet entries, power ports, and other compiled
name contributors when available.

The net `name` is the compiled winner. `aliases` are useful when a schematic
wire has multiple labels, when a port/sheet-entry name differs from a local net
label, or when different pages contribute different candidate names to the same
compiled net. Consumers should display or key on `name` unless they explicitly
need provenance or search over alternate names.

## Current Boundaries

Variant processing includes DNP/not-fitted handling, project current-variant
state, variant metadata in design JSON, and per-designator parameter overrides.
`to_bom(variant=...)` applies parameter overrides to component parameters,
values, and descriptions while retaining DNP rows with a `dnp` flag.
`to_pnp(variant=...)` omits DNP placements for the selected variant.
Design JSON component rows expose active-variant `dnp` and `fitted` state when
available. Schematic SVG/IR rendering does not hide, dim, or mutate DNP
component geometry by itself; consumers can apply their own policy from the
metadata.

Alternate fitted component rows are preserved in project variant metadata but
are not applied as semantic component replacements in BOM, netlist, PNP, or SVG
output yet.

The compiled design path resolves hierarchical sheets, repeated channels,
physical page instances, and annotation-file driven designator mapping for the
governed release corpus. `.Annotation` files are parsed for compile-relevant
physical designator and sheet/document metadata. Annotation `NetNameManager`
records are preserved as annotation metadata, but are not applied as compiled
flat-net renames because reference compile evidence does not apply those
records during schematic compilation.

Use schematic SVG rendering directly when you only need page-level drawings.
Use `AltiumDesign` when you need project context such as parameters, variants,
compiled physical pages, resolved designators, or netlist data.

WireList output is removed from the public output path. WireList can lose
information that exists in the compiled model, especially for repeated sheets,
long generated names, aliases, name-source provenance, and zero-pin interface
nets. Use `AltiumDesign.to_json(...)`, `AltiumDesign.compile().to_dict()`, or
`AltiumDesign.to_netlist().to_json(...)` for programmatic consumers.

Use `design.load_pcbdoc().components` when a PCB-backed BOM should reflect the
components that are actually placed on the board. The `pcbdoc_bom` example shows
that pattern.

## Examples

Start with:

1. [`hello_altium_design`](../examples/hello_altium_design/README.md)
2. [`pcbdoc_bom`](../examples/pcbdoc_bom/README.md)
3. [`pcbdoc_pick_n_place`](../examples/pcbdoc_pick_n_place/README.md)
4. [`schdoc_svg`](../examples/schdoc_svg/README.md)
5. [`pcbdoc_stats`](../examples/pcbdoc_stats/README.md)
6. [`prjpcb_make_project`](../examples/prjpcb_make_project/README.md)

`hello_altium_design` is the canonical project-design example for this release.
It writes full `design.a2` JSON, a physical-page summary, compiled net-name
examples, and project-aware physical schematic SVGs.
