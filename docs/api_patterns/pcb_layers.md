# PCB Layers

PCB layer APIs use several Altium layer identity systems. The current public
authoring API is intentionally conservative: `layer=` arguments are
legacy-layer-first, while broader V7-aware layer-reference work remains a
future API.

## `PcbLayer`

`PcbLayer` is the legacy Altium/TV6 layer enum used by current PCB primitive
helpers. It contains the common copper, overlay, paste, solder, drill, keepout,
and Mechanical 1 through Mechanical 16 values.

Do not treat `PcbLayer` as an unlimited signal-layer or mechanical-layer enum:

```text
PcbLayer.TOP           -> 1
PcbLayer.MID1          -> 2
PcbLayer.MID30         -> 31
PcbLayer.BOTTOM        -> 32
PcbLayer.MECHANICAL_1  -> 57
PcbLayer.MECHANICAL_16 -> 72
Drill Drawing          -> 73
Multi-Layer            -> 74
Connect                -> 75
```

Mechanical 17 is not `PcbLayer(73)`. Value 73 is Drill Drawing.
AD 26.8.1 extended signal layer Mid31 is not `PcbLayer(32)`. Value 32 is
legacy Bottom.

## Serialized V7 Saved Layer IDs

Altium also stores serialized V7 saved layer IDs in Board6, stack/cache, and
configuration data. These are 32-bit layer identities, not `PcbLayer` enum
values. Signal and mechanical layers use these families:

```text
Signal ordinal N -> 0x01000000 + N
Bottom sentinel  -> 0x0100FFFF
Mechanical N -> 0x01020000 + N
```

For example:

```text
Top           -> 0x01000001 / 16777217
Mid30         -> 0x0100001F / 16777247
Mid31         -> 0x01000020 / 16777248
Bottom        -> 0x0100FFFF / 16842751
Mechanical 17 -> 0x01020011 / 16908305
Mechanical 33 -> 0x01020021 / 16908321
```

The Mid31 example is a collision risk if a caller strips the V7 family prefix:
the saved ID species `0x20` means extended signal ordinal 32, while legacy
integer `32` means `PcbLayer.BOTTOM`.

Some parsed records expose V7 side fields such as `v7_layer_id`,
`layer_v7_save_id`, `barcode_layer_v7`, or `V7_LAYER` property text. Those
fields are source metadata. They are not generally accepted as values for
public `layer=` arguments unless a method explicitly documents a V7 override.

## Current Authoring Rule

For new public PCB/PcbLib authoring, pass documented legacy layer values:

```python
pcbdoc.add_track((0, 0), (100, 0), width_mils=8, layer=PcbLayer.TOP)
pcbdoc.add_text(text="REF**", position_mils=(0, 0), height_mils=40,
                layer=PcbLayer.TOP_OVERLAY)
footprint.add_pad(designator="1", position_mils=(0, 0), width_mils=40,
                  height_mils=30, layer=PcbLayer.TOP)
```

Some builder paths also accept stable legacy layer-name tokens such as
`"Top Layer"` and `"Bottom Layer"`. These still resolve to legacy/TV6 layer
ids.

Do not pass serialized V7 saved layer IDs such as `16908305` as `layer=`.
Current helpers usually store `layer` into a legacy primitive field and may
synthesize V7 side metadata from it. A serialized V7 saved layer ID is too
large and belongs to a different identity family.

## Mechanical Layer Metadata

Mechanical layer display names, enabled flags, mirror pairs, and semantic
roles are metadata around layers, not proof that every primitive authoring or
rendering path can target that layer.

`LayerKindMapping/Data` uses a separate mechanical-role id scheme:

```text
Mechanical 1..16  -> 57..72
Mechanical 17..32 -> 0x04000000 | mechanical_number
```

That is different from serialized V7 saved IDs. For example, Mechanical 17 is
`0x04000011` in `LayerKindMapping/Data` but `0x01020011` as a serialized V7
saved layer ID.

## SVG And Export Boundary

SVG layer keys and filenames currently use `PcbLayer` token names plus
documented derived renderer layers such as `DRILLS`. Parsed PcbDoc output can
use board-specific display names when the resolved layer stack is available,
but the stable token set remains legacy-layer-oriented.

Extended V7 layer rendering/export, including Mechanical 17+ and AD 26.8.1
Mid31+ / 128-signal-layer SVG and IPC-2581 behavior, is future V7-aware
layer-reference work. The intended direction is a deliberate layer-reference
API rather than expanding `PcbLayer`.

Current SVG output should not be treated as a Mechanical 17+ or Mid31+
fidelity contract. Parsed primitives whose real layer is recoverable only from
V7 side fields may be omitted, rejected, or grouped through the legacy fallback
until the V7-aware layer-reference API exists. `visible_layers` and
`layer_render_order` do not accept serialized V7 saved IDs or tokens such as
`MID31` under the current public contract.

## V8, V9, And Stack Data

V8 rows are Layer Stack Manager rows such as `LAYER_V8_*` and
`VIASPAN_V8_*`. V9 rows are native Board6 stack/cache rows such as
`V9_STACK_LAYER*`, `V9_CACHE_LAYER*`, and `V9_STACKCUSTOMDATA`.

These rows describe stack topology, layer registries, names, and richer
physical-stack metadata. They are not alternative values to pass to `layer=`.
Use layer-stack APIs for stack inspection/authoring, and use current primitive
helpers only within their documented legacy layer boundary.
