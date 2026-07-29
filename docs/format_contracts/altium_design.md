# AltiumDesign Contract

`AltiumDesign` is the public project-level loader and integration model.

## Stable Surface

- Load an Altium project from `.PrjPcb`.
- Discover schematic, PCB, library, harness, and output-job documents where
  supported.
- Build compiled schematic netlists.
- Emit JSON design and netlist payloads with declared schema ids.
- Render project-level schematic SVG outputs.
- Preserve active project variant identity and component DNP/fitted state in
  project-level JSON when the `.PrjPcb` declares a current variant.
- Surface compact compiled-design metadata and diagnostics in project-level
  JSON without embedding the full compiled model.

## Schema Contracts

JSON payloads include explicit schema ids such as `altium_monkey.design.a1` and
`altium_monkey.netlist.a0`. Breaking JSON payload changes require a new schema
id. Additive fields may appear within the current schema when existing fields
keep their meaning.

## Netlist Connectivity

Project-level `AltiumDesign.to_netlist()` and `AltiumDesign.to_json()` are
compiled physical outputs. Single-document `AltiumSchDoc` SVG/IR/netlist APIs
remain logical source-sheet outputs unless the caller routes through
`AltiumDesign.to_physical_ir(...)` or `AltiumDesign.to_physical_svg(...)`.

Compiled netlist output uses the same sheet-entry and harness-entry hotspot
contract as `AltiumSchDoc`: `DistanceFromTop` and `DistanceFromTop_Frac1` are
composed before endpoint matching, then rounded half-away-from-zero to native
integer schematic units. This prevents fractional entry placement from
collapsing onto an adjacent same-named wire or port during project hierarchy
resolution.

## SVG Linkage

Design JSON may carry ids that link back to schematic SVG output.
`components[].svg_id` points to the rendered component group id, and optional
`indexes.svg_to_component` maps SVG ids back to component designators.
Netlist records carry `nets[].graphical` and `nets[].endpoints` for schematic
highlighting and semantic trace workflows.

For designs with repeated sheets or instantiated channels, `svg_id` alone is a
logical source identity and is not enough to identify one physical component.
The design payload therefore also carries `physical_pages`, a user-facing index
over the compiled physical schematic pages. Each physical page row includes:

- `id`: the physical sheet identity;
- `source_sheet` and `source_path`: the logical SchDoc rendered by SVG;
- `is_top_level`: true for the root physical schematic page;
- channel fields such as `physical_instance_path`, `channel_index`,
  `channel_prefix`, `channel_alpha`, and `room_name`;
- `parent_sheet_symbol`: compact metadata for the physical sheet-symbol
  placement that instantiated this page, or null for the top-level page;
- `components`: resolved component rows on that physical page, including
  `designator`, `logical_designator`, `physical_designator`,
  `source_unique_id`, `source_unique_id_path`, `svg_id`, `dnp`, and `fitted`;
- `nets`: compiled-flat net rows observed on that physical page, including
  the winning `name`, `aliases`, `name_sources`, page-local terminals, and
  graphical object ids grouped by role.

The physical review identity for a schematic component is:

```text
physical_page.id + component.svg_id
```

When indexes are requested, repeated/channel-aware consumers should prefer:

- `indexes.svg_to_components`: logical SVG id to all resolved physical
  component designators;
- `indexes.physical_svg_to_components`: `physical_page_id|svg_id` to resolved
  component designators;
- `indexes.component_to_physical_page`: resolved component designator to
  physical page id;
- `indexes.physical_page_to_components`: physical page id to resolved
  component designators;
- `indexes.physical_page_to_nets`: physical page id to net names.

`indexes.svg_to_component` remains as the existing scalar lookup
for unambiguous logical SVG ids. For repeated/channel designs, ambiguous SVG
ids are intentionally omitted from that scalar map so consumers do not silently
pick one physical instance.

For non-channel and non-repeated designs, this physical-page layer decays to
the historical one-to-one logical SVG/component mapping.

## Net Name Provenance

Compiled flat-net rows expose one winning `name`. When the compiler discovers
additional candidate names on the same electrical net, those names are exposed
as `aliases` and may be explained through `name_sources`.

Consumers that need stable connectivity keys should use the winning `name`.
Consumers that need search, review, or graphical explanation can include
`aliases` and `name_sources` to show labels, ports, sheet entries, power ports,
and other source objects that contributed alternate names.

`aliases` are emitted in deterministic Altium-compatible total sort order with
the winning `name` excluded. Case-only ties therefore remain stable across
processes, which is important for review bundles and visualizers that diff or
cache alternate-name lists.

## Variants and DNP

`project.current_variant` reports the active project variant from the
`.PrjPcb`, when one is set. `variants[]` lists available project variants and
marks the active row with `is_current`.

Top-level `components[]` rows and `physical_pages[].components[]` rows include:

- `dnp`: true when the component's resolved physical designator is marked
  not-fitted in the active project variant;
- `fitted`: the inverse of `dnp`.

The design JSON contract does not filter DNP components. Consumers that need
variant-aware visibility can filter or style using these fields while retaining
the full resolved design context.

## Compile Metadata and Diagnostics

`compile` is a compact summary of the compiled-design state that produced the
public design projection. It includes:

- `schema`: compiled-design model schema id;
- `summary`: counts and warning/error health;
- `options`: resolved compile options such as channel designator format and
  channel room naming style;
- `annotation`: annotation-file load state and counts;
- `stats`: compiler statistics and selected top-level physical/logical ids.

`diagnostics[]` flattens compile warnings/errors from the compiled model into a
consumer-friendly list. Each row keeps the compiled diagnostic fields and adds
`owner_kind` plus `owner_id` when the diagnostic belongs to a specific
document, component, symbol, or net.

## Physical IR and SVG Rendering

Project-level physical rendering is explicit:

- `AltiumDesign.to_physical_ir(physical_page_id)` returns schematic geometry IR
  for one compiled physical page.
- `AltiumDesign.to_physical_svg(physical_page_id)` renders that physical IR to
  SVG.

Both APIs use the logical SchDoc geometry for the selected page, but component
designator text is resolved from the compiled physical page before text
measurement and IR/SVG emission. This is required for repeated sheets and
instantiated channels where the raw sheet contains `R1` but the physical page
contains `R1.1`, `R1A`, or another project-configured resolved designator.

The default `AltiumSchDoc.to_ir()` and `AltiumSchDoc.to_svg()` APIs remain
logical-sheet renderers. Consumers that review compiled projects should select
the intended `physical_pages[].id` and use the physical rendering APIs.

Variant-specific graphical suppression, such as hiding or dimming DNP
components, is a consumer policy layered over the physical rendering path. The
resolved design JSON carries DNP/fitted state; the source schematic geometry is
not mutated.

See [SVG](svg.md) for the SVG-side contract.

## Boundary

`AltiumDesign` exposes Altium-native project data. Cross-CAD normalization is a
separate consumer concern.

## Test Gates

The AltiumDesign contract is covered by design loading, netlist, JSON schema,
SVG, public examples, and release signoff.
