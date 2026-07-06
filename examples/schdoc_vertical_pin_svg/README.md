# schdoc_vertical_pin_svg

Generate a schematic library symbol with pins in all four orientations, insert
that symbol into a schematic, render the schematic to SVG, and write a JSON
proof manifest for pin-name and pin-designator rotation.

This example is a small regression target for `AltiumSchDoc.to_svg()`. It uses
the same public authoring flow as normal schematic work: create an
`AltiumSchLib`, place the symbol with
`AltiumSchDoc.add_component_from_library(...)`, then render the placed
component. It shows that native/default text on 90 and 270 degree pins remains
rotated in SVG, while component-referenced horizontal pin text stays horizontal.
It also shows explicit vertical text settings on horizontal pins.

## What It Shows

1. `AltiumSchLib.add_symbol(...)`
2. `make_sch_pin(...)` with 0, 90, 180, and 270 degree pin orientations
3. `AltiumSchDoc.add_component_from_library(...)`
4. Default vertical pin text rendering
5. `PinTextRotation.HORIZONTAL` and `PinTextRotation.VERTICAL`
6. Name and designator rotation proof from generated SVG text elements
7. `AltiumSchDoc.save(...)` plus `AltiumSchDoc.to_svg(...)`

## Run

From the package root:

```powershell
uv run python examples\schdoc_vertical_pin_svg\schdoc_vertical_pin_svg.py
```

## Output

The script writes:

```text
examples/schdoc_vertical_pin_svg/output/schdoc_vertical_pin_svg.SchLib
examples/schdoc_vertical_pin_svg/output/schdoc_vertical_pin_svg.SchDoc
examples/schdoc_vertical_pin_svg/output/schdoc_vertical_pin_svg.svg
examples/schdoc_vertical_pin_svg/output/vertical_pin_svg_manifest.json
```
