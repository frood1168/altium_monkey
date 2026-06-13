# schdoc_style

Apply a uniform style to all schematic documents in an Altium project using a
single TOML configuration file.

## What It Does

Reads `style.toml` from the example directory, loads every `.SchDoc` referenced
by the project, applies the configured fonts, colors, and line widths to each
schematic element type, and writes the styled copies to `output/hydroscope_styled/`.

## Running

```powershell
uv run python examples/schdoc_style/schdoc_style_extract.py path\to\project.PrjPcb
# edit path\to\clean\style.toml
uv run python examples/schdoc_style/schdoc_style.py path\to\project.PrjPcb
```

Outputs are written to `<project_dir>/clean/`.

## Configuring Styles

Edit `style.toml` to control what gets changed. Each section maps to one
schematic element type. All keys within a section are optional — omit a key to
leave that property unchanged on the element.

```toml
[net_label]
font_name = "Arial"
font_size = 10
bold = false
color = "#0000FF"

[port]
width_mils = 100
height_mils = 20
```

Removing a section entirely means no style is applied to that element type.

### Supported sections

| Section | Element type |
|---|---|
| `[document]` | Sheet background and system font |
| `[wire]` | Wires |
| `[net_label]` | Net labels |
| `[port]` | Hierarchical ports (`width_mils`, `height_mils`, `alignment` also supported) |
| `[power_port]` | Power ports |
| `[cross_sheet_connector]` | Cross-sheet (off-sheet) connectors — font, `color`, and `justification` |
| `[note]` | Notes |
| `[text_string]` | Free-floating text labels |
| `[no_erc]` | No-ERC markers |
| `[signal_harness]` | Signal harnesses |
| `[harness_connector]` | Harness connectors (`width_mils`, `height_mils` also supported) |
| `[harness_entry]` | Harness entries |
| `[harness_type]` | Harness type labels |
| `[sheet_symbol]` | Sheet symbols (`width_mils`, `height_mils` also supported) |
| `[sheet_entry]` | Sheet entries (children of sheet symbols) |
| `[component.designator]` | Component designator text |
| `[component.parameter]` | Visible component parameter text |
| `[component.graphics]` | Component graphic primitives (lines, arcs, body rectangles) |

### Color values

Use `"#RRGGBB"` hex strings for all color properties.

### Enum values

- `line_width`: `"SMALLEST"`, `"SMALL"`, `"MEDIUM"`, `"LARGE"`
- `line_style`: `"SOLID"`, `"DASHED"`, `"DOTTED"`, `"DASH_DOT"`
- `arrow_kind` (sheet entries): `"BLOCK_TRIANGLE"`, `"TRIANGLE"`, `"ARROW"`, `"ARROW_TAIL"`
- `symbol` (no_erc): `"CROSS_THIN"`, `"CROSS"`, `"CROSS_SMALL"`, `"CHECKBOX"`, `"TRIANGLE"`
- `alignment` (port): `"LEFT"`, `"CENTER"`, `"RIGHT"`
- `justification` (cross_sheet_connector): `"BOTTOM_LEFT"`, `"BOTTOM_CENTER"`, `"BOTTOM_RIGHT"`, `"CENTER_LEFT"`, `"CENTER_CENTER"`, `"CENTER_RIGHT"`, `"TOP_LEFT"`, `"TOP_CENTER"`, `"TOP_RIGHT"`

## Extracting Styles From an Existing Project

`schdoc_style_extract.py` is the companion script. It reads all SchDocs in a
project, collects the current style values for every element type, and writes
a seed `extracted_style.toml` to `output/`:

```powershell
uv run python examples/schdoc_style/schdoc_style_extract.py
```

The generated file uses the same section and key names as `style.toml`. For
each property the first value encountered across all elements is written
uncommented; any additional distinct values are captured as `# Conflicts found:`
comments below the section. Copy the output to `style.toml`, keep the values
you want, remove sections you don't need, and run `schdoc_style.py` to apply.

## Using With Your Own Project

Replace the `INPUT_PRJPCB` and output path constants near the top of either
script with your own project path, or adapt them to accept a project path as
a command-line argument.
