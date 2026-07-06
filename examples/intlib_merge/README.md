# intlib_merge

Merge a directory of `.IntLib` files into a single combined integrated library.

Each source `.IntLib` is an OLE package that embeds `.SchLib` and `.PcbLib`
source streams. This example discovers every `.IntLib` in a directory, extracts
those embedded streams, merges the symbols and footprints, and repacks the
result into one new `.IntLib` with compressed source streams. Duplicate symbol
names are handled with the default rename behavior; duplicate footprints are
skipped so the SchLib cross-references stay valid.

## What It Shows

1. `AltiumIntLib(...).extract_sources(...)` to pull embedded SchLib/PcbLib streams
2. `AltiumSchLib.merge(input_paths, output_path, handle_conflicts="rename")`
3. `AltiumPcbLib.add_existing_footprint(...)` to combine footprints
4. `AltiumOleWriter` to repack the merged streams into an `.IntLib` container

## Run

From the package root:

```powershell
uv run python examples\intlib_merge\intlib_merge.py
```

Run arg-free, it recursively discovers the two `.IntLib` files bundled under the
shared sample projects (`rt_super_c1` and `loz-old-man`) and writes
`output/merged.IntLib`.

To merge your own libraries, pass a directory:

```powershell
uv run python examples\intlib_merge\intlib_merge.py C:\path\to\intlibs --recurse -o combined.IntLib
```

Options: `--recurse`/`-r` (search subdirectories), `--output`/`-o` (output path),
`--name`/`-n` (base name for embedded stream files), and
`--conflicts {rename,skip}` (duplicate name handling).

## Input

Libraries merged by the arg-free demo (discovered recursively under the shared
sample projects — no duplicated fixtures):

```text
examples/assets/projects/rt_super_c1/RT_SUPER_C1.IntLib
examples/assets/projects/loz-old-man/loz-old-man.IntLib
```

## Output

```text
examples/intlib_merge/output/merged.IntLib
```
