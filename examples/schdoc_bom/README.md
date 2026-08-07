# schdoc_bom — configurable parameter BOM from a project

Walks every schematic reachable from a `.PrjPcb`, pulls the component fields named in
`bom_fields.toml`, and writes them to a CSV. The columns live in the TOML, not in the
script, so re-shaping the BOM is an edit to a config file rather than a code change.

## Run

```powershell
# Bundled example — hydroscope project, writes to output/
uv run python examples/schdoc_bom/schdoc_bom.py

# Your own project
uv run python examples/schdoc_bom/schdoc_bom.py C:\path\to\MyBoard.PrjPcb

# A single sheet
uv run python examples/schdoc_bom/schdoc_bom.py C:\path\to\Sheet.SchDoc
```

Given a project path, the script reads `bom_fields.toml` from the project folder when one
is there and falls back to the copy next to the script otherwise, then writes
`<ProjectName>_BOM.csv` and `<ProjectName>_parameters.csv` beside the project. Override
either with `--config` / `--output`.

## Outputs

| File | Contents |
|------|----------|
| `<name>_BOM.csv` | One row per component, one column per entry in `columns` |
| `<name>_parameters.csv` | Every parameter name in the project and how many components carry it |

The second file is the discovery tool: run once, open it, and copy the exact parameter
spellings you want into `bom_fields.toml`. CSVs are written UTF-8 with a BOM so Excel
opens µ, Ω and Ø correctly.

## Configuring the columns

Each entry in `columns` becomes one CSV column, in the order listed:

```toml
columns = [
  { name = "Document",    source = "document"   },
  { name = "Identifier",  source = "designator" },
  { name = "Capacitance" },
  { name = "Value"       },
  { name = "PartNumber"  },
]
```

- `name` — the CSV header.
- `source` — omit it (or set `"parameter"`) to read a component parameter. The built-in
  sources cover the things a schematic knows that are not parameters: `document`,
  `document_path`, `designator`, `comment`, `description`, `lib_reference`, `footprint`,
  `library_path`, `source_library_name`, `design_item_id`, `unique_id`, `component_kind`,
  `part_designator`, `part_id`, `part_count`.
- `parameter` — the parameter to read when it is spelled differently from the header,
  e.g. `{ name = "MPN", parameter = "Manufacturer Part Number" }`.

Parameter names match case-insensitively. A parameter a component does not carry comes out
blank; a column that is blank for *every* component is called out on the console, since
that almost always means the name does not match anything in the project.

## Options

```toml
[options]
include_non_bom_components  = false   # keep graphical / *_no_bom parts out
merge_multi_part_components = true    # U1A..U1D collapse to one row
sort_by = ["Document", "Identifier"]  # natural sort, so R2 precedes R10
blank = ""                            # text for a missing parameter
```

`merge_multi_part_components` only merges components whose symbol declares more than one
part. Two *single*-part components sharing a designator is a real design error, so those
stay as separate rows rather than being quietly folded together. When merged placements
disagree on a column — usually `Document`, when the parts sit on different sheets — the
distinct values are joined with `; ` so nothing is lost.
