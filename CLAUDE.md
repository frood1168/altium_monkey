# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

`altium-monkey` is a Python toolkit (3.11/3.12) for reading, writing, analyzing, and rendering Altium EDA files (`.SchDoc`, `.SchLib`, `.PcbDoc`, `.PcbLib`, `.PrjPcb`, `.OutJob`, `.IntLib`) without the Altium GUI. Package source lives at `src/py/altium_monkey/`.

## Commands

All Altium files are OLE/CFB compound binaries. The package is managed with `uv`.

**Install dev environment:**
```powershell
uv sync
```

**Run tests:**
```powershell
uv run pytest tests/
uv run pytest tests/test_assets.py::test_pcbdoc_bom_writes_resolved_component_rows  # single test
```

**Run an example:**
```powershell
uv run python examples/hello_schdoc/hello_schdoc.py
```

**Check / regenerate docs:**
```powershell
uv run python tools/generate_docs.py --check
uv run python tools/generate_docs.py
```

**Build wheel:**
```powershell
uv run python -m build
```

Tests in `tests/test_assets.py` run the example scripts as subprocesses against real Altium assets and verify their outputs.

## Architecture

### OLE Layer

All Altium files use OLE/CFB (Microsoft Compound Binary Format). `altium_ole.py` provides a self-contained reader/writer (`AltiumOleFile`, `AltiumOleWriter`) with no external dependency on `olefile`. Everything else parses the streams inside these containers.

### Schematic Object Model

**`AltiumSchDoc`** (`altium_schdoc.py`) and **`AltiumSchLib`/`AltiumSymbol`** (`altium_schlib.py`) use `ObjectCollection` (`altium_object_collection.py`) as their authoritative mutable store.

- Typed views (`schdoc.notes`, `schdoc.ports`, `schdoc.components`, etc.) are live read-only filters over the collection — do not append to them.
- All membership changes go through container methods: `add_object(...)`, `insert_object(...)`, `remove_object(...)`.
- Objects are created with `make_sch_*` factory functions from `altium_sch_object_factory.py`, which accept public types (`SchPointMils`, `SchRectMils`, `SchFontSpec`, `ColorValue`, enums) and produce record objects.
- The document resolves font table entries, `IndexInSheet`, `OwnerIndex`, and serialization details when objects are added and saved.
- Some records have ownership rules: harness entries belong to connectors; sheet entries/names/filenames belong to sheet symbols; component pins/designators/parameters belong to components. Add them through the owner, not directly.

### PCB Object Model

**`AltiumPcbDoc`** (`altium_pcbdoc.py`) and **`AltiumPcbLib`/`AltiumPcbFootprint`** (`altium_pcblib.py`) are helper-oriented rather than `ObjectCollection`-oriented.

- Authoring uses high-level `add_*` methods (`add_track`, `add_arc`, `add_pad`, `add_region`, `add_text`, `add_component_from_pcblib`, `add_extruded_3d_body`, `add_embedded_3d_model`).
- Parsed primitives are accessible through typed lists: `pcbdoc.tracks`, `pcbdoc.pads`, `pcbdoc.arcs`, `pcbdoc.nets`, `pcbdoc.components`, `pcbdoc.component_bodies`, etc.
- Direct list mutation is possible but is an advanced path — use `add_*` helpers when they exist.
- PCB builder internals are split across `altium_pcbdoc_builder_*.py` modules; these are internal machinery, not the public API.

### Record Modules

Individual record types live in dedicated modules:
- `altium_record_sch__<name>.py` — schematic record types (arc, bezier, bus, component, designator, pin, net_label, etc.)
- `altium_record_pcb__<name>.py` — PCB record types (arc, pad, track, via, net, region, component_body, model, etc.)

### Project / Design Layer

- `altium_prjpcb.py` — `AltiumPrjPcb` for project parameters, variants, document references, OutJob resolution
- `altium_outjob.py` / `altium_outjob_runner.py` — `AltiumOutJob` and the runner
- `AltiumDesign` / `AltiumDesign.to_json()` — project-level extraction to the public JSON contract (`docs/schemas/altium_monkey/`)

### Key Conventions

**Units:** Schematic authoring is mil-based (`SchPointMils`, `SchRectMils`). PCB high-level helpers use explicit `*_mils` parameter names. Internal Altium storage is 10,000 units per mil — never work in those units directly unless round-tripping raw records.

**Public API:** Functions and methods decorated with `@public_api` (from `altium_api_markers.py`) are the stable surface. Prefer importing from `altium_monkey` directly (the package `__init__.py`) rather than internal submodules.

**Examples:** `examples/manifest.toml` indexes all examples. Each example is in `examples/<id>/` with an entrypoint at `examples/<id>/<id>.py` and outputs under `examples/<id>/output/`. The test suite runs each example as a subprocess and checks declared outputs.

**Docs generation:** `tools/generate_docs.py` generates parts of the Markdown docs. Run with `--check` in CI or before committing doc changes.
