# SVG Contract

altium-monkey emits SVG for schematic documents, schematic library symbols,
PCB documents, and PCB library footprints. SVG is a review and integration
format, not a full replacement for the source Altium files.

## Common Rules

- Normal SVG output includes a root `viewBox`.
- `include_view_box=False` omits only the root `viewBox` attribute.
- Omitting the `viewBox` does not change geometry, metadata, filenames, layer
  keys, or element identifiers.
- Strict schematic oracle modes may omit the root `viewBox` by default so they
  preserve the comparison surface used by renderer tests.
- SVG DOM `id` values are render-output identifiers. Downstream tools should
  prefer documented `data-*` metadata when semantic identity is needed.

## Schematic SVG

SchDoc and SchLib SVG output uses schematic pixel-canvas coordinates. The
renderer converts source schematic coordinates into the emitted SVG coordinate
space before writing geometry.

The normal schematic SVG root carries document identity attributes:

- `data-doc-id`: the schematic document id used for this render. For parsed
  SchDoc output this is normally the sheet file UniqueID; for SchLib symbol
  output it is a synthesized symbol render id.
- `data-doc-ver`: the schematic SVG renderer contract version for this root
  shape.

The normal schematic SVG group shape is:

- `<g id="scene">`: top-level scene group
- `<g id="DocumentMainGroup">`: document-level drawing group
- `<g id="<data-doc-id>">`: drawing group for the rendered sheet or symbol
- optional background and mask groups when the selected render options require
  them
- source-record groups such as `<g id="<record UniqueID>">` for rendered
  records that have a source UniqueID

Most schematic graphical records render inside a group whose SVG `id` is the
source record UniqueID. Component groups use the component UniqueID. Pin,
wire, label, port, sheet-entry, harness, and power-port records use their own
record UniqueIDs when available. Some synthetic or helper geometry may not have
a stable source-owned id and should not be treated as semantic identity.

Schematic SVG does not currently embed a document-level JSON metadata payload.
The relationship sidecar is the `AltiumDesign.to_json(...)` and
`Netlist.to_json(...)` payload:

- `components[].svg_id` points to the component SVG group id, normally the
  component record UniqueID.
- optional `indexes.svg_to_component` maps component SVG ids back to
  designators when indexes are requested.
- `nets[].graphical` groups related schematic SVG ids by record type:
  `wires`, `junctions`, `labels`, `power_ports`, `ports`, `sheet_entries`, and
  `pins`.
- `nets[].graphical.pins[]` contains `{designator, pin, svg_id}` objects so a
  viewer can highlight the actual pin SVG element.
- `nets[].endpoints[]` provides semantic trace endpoints. `element_id` is the
  current SVG render target, while `object_id` is the source electrical object
  id when it differs from the rendered element. Endpoint connection points use
  source schematic coordinates, not SVG coordinates.

For schematic visualization, use the SVG as the drawing surface and the design
or netlist JSON as the semantic lookup table. Do not infer electrical meaning
from rendered text strings or group nesting alone.

Embedded schematic images preserve the best available payload. Native PNG,
JPEG, GIF, SVG, and WebP payloads are embedded with their natural media type.
Plain BMP payloads are decoded to PNG for browser-compatible SVG output.
Alpha data is preserved when it exists in the stored image payload.

Schematic text is measured through the font resolver before SVG is emitted.
Installed system fonts are preferred, and callers can add search roots through
`ALTIUM_FONT_DIRS`. Common Altium/Windows font families can fall back to
bundled open-source fonts when unavailable: Arimo for Arial and Microsoft Sans
Serif-style families, Tinos for Times New Roman-style families, and Cousine for
Courier New or monospace families. When bundled fallback fonts are used,
schematic SVG embeds those font faces so browser layout follows the same
metrics used by the renderer.

## PCB SVG

PcbDoc and PcbLib SVG output uses millimeter coordinates. PCB SVG filenames and
dictionary keys use stable layer tokens such as `TOP`, `BOTTOM`, and
`TOPOVERLAY`.

Human-facing PCB layer labels are separate from stable layer tokens.
`data-layer-name` and JSON layer maps carry token-oriented names.
`data-layer-display-name` carries a user-facing label. Parsed PcbDoc output
uses the resolved board layer stack when one is available and otherwise falls
back to the default layer display label.

PcbLib footprints do not own a board layer stack, so footprint SVG output can
only use default display labels.

When PCB metadata is enabled, the PCB SVG root carries render-context
attributes:

- `data-stage`: render stage such as `viz`, `validation`, or `export`
- `data-group-mode`: grouping mode requested by render options
- `data-enrichment-schema`: the PCB enrichment schema id
- `data-view-kind`: view type such as `board`, `layer_set`, or
  `board_outline_only`
- `data-mirror-x`: whether the SVG scene is mirrored around X
- `data-source`: source PcbDoc filename when known
- `data-board-centroid-*-mils`: board centroid values when known

PCB layer groups use ids such as `layer-TOP`, `layer-BOTTOM`, and
`layer-DRILLS`. When metadata is enabled, layer groups and layer-owned
primitives carry:

- `data-layer-id`: source legacy layer id
- `data-layer-key`: stable short key such as `L1`, `L32`, or `DRILLS`
- `data-layer-name`: stable token such as `TOP`, `BOTTOM`, or `DRILLS`
- `data-layer-display-name`: human-facing label
- `data-layer-role`: normalized role such as `copper`, `silkscreen`,
  `soldermask`, `paste`, `mechanical`, `drill`, or `other`

PCB primitive metadata uses `data-primitive` values such as `track`, `arc`,
`pad`, `via`, `region`, `text`, `pad-hole`, and `via-hole`. Relationship
attributes are emitted when the source primitive carries the linkage:

- `data-net-index`, `data-net`, `data-net-uid`
- `data-net-class` and `data-net-classes`
- `data-component-index`, `data-component`, `data-component-uid`
- `data-pad-designator` and `data-pad-number` for pad geometry
- `data-text-role` for PCB text (`designator`, `comment`, or `free`)

Where deterministic primitive identity is assigned, the SVG element has both
`id` and `data-element-key`. The current key form is
`pcb-<primitive-kind>-<index>` with optional layer and role suffixes. Treat the
exact string as stable within one emitted SVG and as a lookup key for that
rendered artifact. Use semantic `data-*` attributes for cross-render matching.

Board-outline geometry uses `data-feature`:

- `data-feature="board-outline"` for the outer profile
- `data-feature="board-cutout"` plus `data-feature-index` for board-profile
  voids

Drill geometry uses:

- `data-primitive="pad-hole"` or `data-primitive="via-hole"`
- `data-hole-owner`
- `data-hole-kind`
- `data-hole-plating`
- `data-hole-render`

## PCB Enrichment Metadata

When PCB metadata is enabled, the root SVG and the embedded metadata payload
use schema id `altium_monkey.pcb.svg.enrichment.a0`.

The PCB enrichment payload records document-level context such as:

- emitted view information
- included layer ids
- layer token and display-name mappings
- net and net-class summaries
- component placement summaries
- board-outline and drill relationships

The payload is embedded as escaped JSON in:

```xml
<metadata id="pcb-enrichment-a0" data-schema="altium_monkey.pcb.svg.enrichment.a0">
  ...
</metadata>
```

The metadata element id is a DOM lookup anchor. The `data-schema` attribute and
JSON `schema` field are the payload contract identifiers.

The schema contract pages contain the machine-readable payload shape. The SVG
contract here documents how that payload relates to the rendered SVG elements.

## Test Gates

The SVG contract is protected by targeted unit tests, public example tests,
corpus SVG lanes, and release signoff checks. The signoff gate also checks that
these contract docs are synchronized into the released docs.
