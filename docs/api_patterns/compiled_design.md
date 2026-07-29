# Compiled Design Migration

`AltiumDesign.to_json()` now emits `altium_monkey.design.a2`. The change keeps
the existing Python call surface but makes the project JSON contract explicit
for compiled physical pages, repeated sheets, and channel-resolved designators.

## Strict Schema Validators

If a consumer validates `AltiumDesign.to_json()` output against
`altium_monkey.design.a1`, refresh to `altium_monkey.design.a2`.

`design.a1` used `additionalProperties: false`, so current payloads cannot
silently reuse that schema ID after adding the default `physical_pages` root
field.

`design_a2.schema.json` is self-contained for strict validation. The sibling
`design_a1`, `design_a0`, and `netlist_a0` schemas remain bundled for consumers
pinned to earlier contracts or validating those payload families directly.

## Compile Metadata Is Opt-In

Default design JSON includes the user-facing physical-page projection but omits
compile health details:

```python
payload = design.to_json()
assert "physical_pages" in payload
assert "compile" not in payload
assert "diagnostics" not in payload
```

Request compile metadata and public diagnostics only when needed:

```python
payload = design.to_json(include_compile_metadata=True)
compile_summary = payload["compile"]["summary"]
diagnostics = payload["diagnostics"]
```

Use `design.compile().to_dict()` when a tool needs the full beta compiled model
rather than the compact design contract.

## Physical Pages, Parts, And Nets

`physical_pages` is the main project-review index. It is always present in
`design.a2`.

```python
payload = design.to_json(include_indexes=True)

for page in payload["physical_pages"]:
    print(page["id"], page["physical_instance_path"], page["source_sheet"])

    for component in page["components"]:
        print(component["designator"], component["svg_id"])

    for net in page["nets"]:
        print(net["name"], len(net["terminals"]))
```

For non-repeated projects, this decays to one physical page for each source
sheet. For repeated sheets and multi-channel projects, each repeated instance
gets its own physical page row and resolved component designators.

Use the indexes when a consumer needs direct lookup:

```python
indexes = payload["indexes"]
page_id = indexes["component_to_physical_page"]["R1.2"]
page_components = indexes["physical_page_to_components"][page_id]
page_nets = indexes["physical_page_to_nets"][page_id]
```

## Net Name Winners And Alternates

The compiled net row `name` is the winning Altium-style net name. `aliases`
contains alternate discovered names from the same compiled net. `name_sources`
explains the candidates when provenance is available.

`aliases` are deterministic and exclude the winning `name`. They are sorted
with the same Altium-compatible total ordering used by the compiler for
case-insensitive net-name ties.

```python
for page in payload["physical_pages"]:
    for net in page["nets"]:
        winner = net["name"]
        alternates = net.get("aliases", [])
        sources = net.get("name_sources", [])
        if alternates or len(sources) > 1:
            print(page["physical_instance_path"], winner, alternates)
```

This is useful when multiple net labels are placed on one wire, when a port or
sheet entry uses a different name than the connected page-local label, or when
several pages contribute names to one compiled net. Consumers should key on the
winning `name` unless they intentionally need search/provenance over alternate
names.

## SVG And Component Identity

For simple projects, `indexes.svg_to_component` still provides the familiar
one-to-one SVG ID to component designator map.

For repeated or channelized projects, one logical SVG element can represent
multiple physical components. In that case, `svg_to_component` omits ambiguous
entries and consumers should use:

```python
key = f"{physical_page_id}|{svg_id}"
designators = payload["indexes"]["physical_svg_to_components"][key]
```

The review-safe identity is always:

```text
physical_page.id + svg_id
```

`indexes.svg_to_components` is useful when a tool starts from a logical SVG ID
and wants all physical designators represented by that source element.

To join a physical SVG element back to a designator, combine the selected
physical page id with the element's source SVG id:

```python
key = f"{physical_page_id}|{svg_id}"
designators = payload["indexes"]["physical_svg_to_components"].get(key, [])
```

## Physical IR And SVG

Use project-aware rendering when resolved channel designators matter:

```python
svg = design.to_physical_svg(physical_page_id)
ir = design.to_physical_ir(physical_page_id)
```

These APIs render the logical SchDoc geometry for one compiled physical page
while substituting resolved physical designator text, such as `R1.1`, `R1.2`,
`R1A`, or `R1B`. Source SchDoc records are not mutated.

Standalone single-SchDoc SVG/IR rendering remains a logical page renderer and
does not have project compile context.

`AltiumSchDoc.to_svg()` is therefore appropriate for drawing one raw source
sheet. `AltiumDesign.to_physical_svg(physical_page_id)` is appropriate for
project review output where the same source sheet may appear more than once.

`altium_cruncher`-style design-review bundles should treat the physical page id
as part of schematic SVG identity. A manifest row should identify the physical
page, the source sheet, and the SVG path, then use `design.a2` indexes for
component/net lookup.

## Netlisting Compatibility

`AltiumDesign.to_netlist()`, `compile_netlist()`, and
`AltiumNetlistMultiSheetCompiler` remain importable with their existing call
signatures. Multi-sheet project behavior now routes through the compiled design
model rather than the retired clone/rewrite netlisting path.

WireList serialization is removed from the public output path. For repeated
sheets, zero-pin interface nets, long generated names, aliases, and name-source
provenance, use `AltiumDesign.to_json()`,
`AltiumDesign.to_netlist().to_json()`, or `design.compile().to_dict()`.
