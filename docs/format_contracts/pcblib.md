# PcbLib Contract

`AltiumPcbLib` is the public model for PCB footprint libraries.

## Stable Surface

- Parse existing `.PcbLib` files.
- Preserve unknown or unsupported data during normal read/write flows.
- Create new footprint libraries.
- Add, find, split, and render footprints.
- Add pads, tracks, arcs, regions, text, vias, component bodies, and embedded
  STEP models to footprints. STEP-derived component-body bounds use
  `wn-geometer`; explicit bounds remain supported.
- Author pad solder-mask and paste-mask expansion modes with the stable
  vocabulary `none`, `rule`, and `manual`. Manual expansion values are signed
  mil-unit values.
- Author round, square, and slotted drill-hole pads. Slotted holes require a
  positive slot length; square holes require a positive drill size.
- Author footprint vias with top/bottom tenting flags and independent
  top/bottom solder-mask expansion values.
- Author footprint via IPC-4761 protection metadata, propagation delay, and
  fabrication/assembly testpoint flags.
- Author footprint-level primitive parameters through the PcbLib
  `PrimitiveParameters` stream.
- Inspect and author semantic mechanical layer kind assignments through
  `mechanical_layer_kinds`, `get_mechanical_layer_kind(...)`, and
  `set_mechanical_layer_kind(...)`. The mapping is stored in
  `Library/LayerKindMapping/Data` and synchronized into the PcbLib
  `Library/Data` `MECHKIND` layer-table/cache fields used by Altium.
- Author mechanical layer display names, enabled flags, and component mirror
  pairs through `set_mechanical_layer(...)` and
  `set_mechanical_layer_pair(...)`. These update the PcbLib `Library/Data`
  layer table and `MECHPAIR*` entries.
- Author custom-pad anchor geometry with explicit anchor width, height,
  rotation, and shape. Custom-pad regions use the native 1-based `PADINDEX`
  that corresponds to the authored anchor pad.
- Author footprint text as stroke, TrueType, or barcode text. Stroke fonts use
  the stable vocabulary `default`, `sans-serif`, and `serif`. Barcode text
  supports Code 39 and Code 128 option sets shared with PcbDoc text authoring.
- Extract embedded 3D model payloads.

## Object Model

`AltiumPcbLib` owns footprints and embedded model streams.
`AltiumPcbFootprint` owns its primitive lists and helper methods. Attach a
footprint to a library before adding primitives that need library-owned streams
or metadata.

Footprint primitive parameters are exposed as
`footprint.footprint_primitive_parameters` and authored with
`set_footprint_primitive_parameter(...)`. They are separate from the ordinary
footprint `parameters` dictionary.

## Units

High-level footprint helper methods use explicit mil-unit parameter names.
Low-level record fields may expose source integer storage units.

## Embedded 3D Models

If STEP bounds cannot be computed on the current host, footprint authoring may
fall back to an axis-aligned rectangle around available SMD/through-hole pads as
a recovery projection. This fallback is not a geometry-equivalent STEP import.

## Layer Names

PcbLib footprints do not have a board layer stack. Stable layer keys use token
names, and default display labels are used only for human-facing labels.
Mechanical layer display names, enabled flags, and mirror pairs are library
registry metadata. Mechanical layer kind assignments are semantic metadata and
do not by themselves rename or enable mechanical layers.

## SVG

`AltiumPcbFootprint.to_svg(...)` and `to_layer_svgs(...)` accept
`PcbSvgRenderOptions`. Normal output includes a root `viewBox` in millimeter
coordinates.

See [SVG](svg.md) for the shared rendering contract.

## Test Gates

The PcbLib contract is covered by footprint parsing, split/extract, authoring,
primitive-parameter and via-structure fixture coverage, 3D model, SVG, public
examples, and release signoff.

