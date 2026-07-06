# schlib_style_apply

Read a style template (`schlib_style.toml`) and stamp pin visibility, pin text
fonts, body-rectangle style, and line style onto every symbol in one or more
target SchLib files.

The TOML is produced (and optionally hand-edited) by
`schlib_style_apply_extract.py`. Per-symbol sections (`[SymbolName.pin]`, etc.)
override the `[default.*]` sections for that specific symbol; omitting a section
type leaves those objects unchanged.

## What It Shows

1. `AltiumSchLib` load / iterate symbols
2. Applying pin visibility and pin text font settings (`AltiumSchPin`, `PinItemMode`)
3. Applying body-rectangle and line style (`LineWidth`)
4. Writing modified SchLib copies plus a JSON summary manifest

## Run

From the repository root:

```powershell
uv run python examples\schlib_style_apply\schlib_style_apply.py
```

With no arguments it applies the bundled style template to the bundled sample
SchLibs and writes the results to `output/`. You can also target your own files:

```powershell
# A folder of SchLib files:
uv run python examples\schlib_style_apply\schlib_style_apply.py --toml STYLE.toml SCHLIB_DIR

# A single SchLib:
uv run python examples\schlib_style_apply\schlib_style_apply.py --toml STYLE.toml MY.SchLib
```

## Inputs

```text
examples/assets/schlib/                        # bundled sample SchLib(s)
examples/schlib_style_apply/clean/schlib_style.toml   # style template
```

## Output

```text
examples/schlib_style_apply/output/                              # styled SchLib copies
examples/schlib_style_apply/output/schlib_style_apply_manifest.json
```

## Related

`schlib_style_apply_extract.py` generates a `schlib_style.toml` from an existing
SchLib so you can capture a house style and re-apply it elsewhere.
