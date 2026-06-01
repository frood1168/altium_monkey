# schdoc_param_layout

Position schematic component parameter fields using a template derived from a
reference schematic. Parameter offsets are stored in the component's local
coordinate frame, so they apply correctly regardless of how the component is
rotated or mirrored in the target project.

## Workflow

```
reference.SchDoc  ──extract──▶  clean/param_layout.toml
                                        │
                                        ▼
project.PrjPcb    ──apply───▶  clean/<schematic>.SchDoc
```

### Step 1 — Create a reference schematic

Open any `.SchDoc` in Altium and place the component symbols you want to
template. Manually drag each parameter field (designator, Value, Footprint,
etc.) to exactly where you want it. One placed instance of each symbol type is
enough — the template captures offsets per library reference name.

### Step 2 — Extract the template

```powershell
uv run python examples/schdoc_param_layout/schdoc_param_layout_extract.py reference.SchDoc
```

Writes `<reference_dir>/clean/param_layout.toml`. Inspect the file and edit if
needed — each section is `[LibraryReference.ParameterName]`.

### Step 3 — Apply to your project

```powershell
uv run python examples/schdoc_param_layout/schdoc_param_layout.py project.PrjPcb
```

Reads `<project_dir>/clean/param_layout.toml` and writes positioned copies of
all project SchDocs to `<project_dir>/clean/`.

## Template format (`param_layout.toml`)

Sections are three-level: `[LibraryReference.Rotation.ParameterName]`.

```toml
["MIMXRT685SFVKB".DEG_0.Designator]
offset_x = 50.0
offset_y = 80.0
orientation = "DEGREES_0"
justification = "BOTTOM_LEFT"
is_hidden = false

["MIMXRT685SFVKB".DEG_90.Designator]
offset_x = -80.0
offset_y = 50.0
orientation = "DEGREES_90"
justification = "BOTTOM_LEFT"
is_hidden = false
```

**`LibraryReference`** is the Altium `LibReference` property — the symbol name
in the library (not the instance designator like R1 or U3). Only components
whose `LibReference` matches a key in the template are updated.

**`Rotation`** is one of `DEG_0`, `DEG_90`, `DEG_180`, `DEG_270`. The apply
script matches both the library reference and the component's current rotation.
A component at 90° only gets the `DEG_90` entry applied, never a different
orientation's layout. If the template has no entry for a component's orientation,
that component is left unchanged.

**`offset_x`/`offset_y`** are world-frame offsets from the component origin
(mils). Because the reference schematic IS the ground truth for each rotation,
no coordinate transformation is applied — offsets are measured and stored
exactly as placed, and applied exactly as stored.

`is_hidden = true` hides the parameter on the schematic.

`auto_position` is always forced to `false` on modified parameters so Altium
does not reposition them on the next DRC/update cycle.

## Partial coverage

You do not need all four orientations in the template. If your reference
schematic has a component only at 0° and 90°, only components at those two
orientations will be updated. Components at 180° or 270° are left unchanged.

## Conflicts in the extracted template

If multiple instances of the same component type at the same rotation have
different parameter positions, the first-encountered position is written
uncommented and the others are captured as comments:

```toml
["R_0402".DEG_0.Designator]
offset_x = 20.0
offset_y = 30.0
# Conflicts found:
# offset_x = 25.0
# offset_y = 28.0
```

Edit the uncommented entry to the position you want.

## Known limitations

- Mirrored components are not differentiated from non-mirrored — a `DEG_0`
  entry applies to all components at 0° regardless of mirror state.
