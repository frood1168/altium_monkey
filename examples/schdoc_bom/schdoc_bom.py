"""Pull a configurable set of component parameters out of a project into a CSV BOM.

The columns are declared in bom_fields.toml, not in this file, so the BOM can be
re-shaped by editing the TOML. Alongside the BOM the script writes an index of
every parameter name that occurs in the project, which is how you find out what
else you could add to the TOML.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import tomllib
from collections import Counter, OrderedDict
from pathlib import Path

from altium_monkey import (
    AltiumSchDesignator,
    AltiumSchDoc,
    AltiumSchParameter,
    ComponentKind,
)
from altium_monkey.altium_component_kind import component_kind_includes_in_bom
from altium_monkey.altium_prjpcb import AltiumPrjPcb


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"

_DEFAULT_PRJPCB = ASSETS_DIR / "projects" / "hydroscope" / "Hydroscope.PrjPcb"
_DEFAULT_CONFIG = SAMPLE_DIR / "bom_fields.toml"
_CONFIG_BASENAME = "bom_fields.toml"

_PART_SUFFIX = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# --------------------------------------------------------------------------
# Component field access
# --------------------------------------------------------------------------


def _designator(component: object) -> str:
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchDesignator):
            return (param.text or "").strip()
    return ""


def _parameter_map(component: object) -> dict[str, str]:
    """Parameter name (lowercased) -> text, for one component.

    First occurrence of a name wins; Altium tolerates duplicates and the first
    is the one it displays.
    """
    values: dict[str, str] = {}
    for param in getattr(component, "parameters", []):
        if not isinstance(param, AltiumSchParameter):
            continue
        name = (param.name or "").strip()
        if not name:
            continue
        key = name.lower()
        if key not in values:
            values[key] = (param.text or "").strip()
    return values


def _parameter_names(component: object) -> set[str]:
    """Parameter names as authored, for the parameter index.

    Kept separate from _parameter_map, which lowercases keys for lookup — the
    index has to show the exact spelling so it can be pasted into the TOML.
    """
    names: set[str] = set()
    for param in getattr(component, "parameters", []):
        if not isinstance(param, AltiumSchParameter):
            continue
        name = (param.name or "").strip()
        if name:
            names.add(name)
    return names


def _component_kind_name(component: object) -> str:
    raw = getattr(component, "component_kind", None)
    try:
        return ComponentKind(raw).name.lower()
    except (TypeError, ValueError):
        return f"unknown:{raw}"


def _includes_in_bom(component: object) -> bool:
    raw = getattr(component, "component_kind", None)
    try:
        return component_kind_includes_in_bom(ComponentKind(raw))
    except (TypeError, ValueError):
        return True


def _logical_part_count(component: object) -> int:
    """Number of parts in the symbol, 1 for an ordinary component.

    Altium stores PartCount as actual_count + 1, so a plain resistor reads 2
    and a two-gate symbol reads 3. AltiumSchLib normalizes this on the way in;
    the SchDoc component record does not, so it has to be undone here — without
    it every component looks multi-part.
    """
    stored = int(getattr(component, "part_count", 1) or 1)
    return stored - 1 if stored > 1 else 1


def _part_designator(component: object, designator: str) -> str:
    """R1 for a single-part symbol, U3A / U3B ... for a multi-part one."""
    if _logical_part_count(component) <= 1:
        return designator
    part_id = int(getattr(component, "current_part_id", 1) or 1)
    index = part_id - 1
    if 0 <= index < len(_PART_SUFFIX):
        return f"{designator}{_PART_SUFFIX[index]}"
    return f"{designator}_P{part_id}"


_BUILTIN_SOURCES: dict[str, object] = {
    "document": lambda comp, ctx: ctx["document"],
    "document_path": lambda comp, ctx: ctx["document_path"],
    "designator": lambda comp, ctx: ctx["designator"],
    "comment": lambda comp, ctx: ctx["parameters"].get("comment", ""),
    "description": lambda comp, ctx: str(
        getattr(comp, "component_description", "") or ""
    ),
    "lib_reference": lambda comp, ctx: str(getattr(comp, "lib_reference", "") or ""),
    "footprint": lambda comp, ctx: str(getattr(comp, "footprint", "") or ""),
    "library_path": lambda comp, ctx: str(getattr(comp, "library_path", "") or ""),
    "source_library_name": lambda comp, ctx: str(
        getattr(comp, "source_library_name", "") or ""
    ),
    "design_item_id": lambda comp, ctx: str(getattr(comp, "design_item_id", "") or ""),
    "unique_id": lambda comp, ctx: str(getattr(comp, "unique_id", "") or ""),
    "component_kind": lambda comp, ctx: _component_kind_name(comp),
    "part_designator": lambda comp, ctx: _part_designator(comp, ctx["designator"]),
    "part_id": lambda comp, ctx: str(getattr(comp, "current_part_id", 1) or 1),
    "part_count": lambda comp, ctx: str(_logical_part_count(comp)),
}


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


class Column:
    """One CSV column: a header plus where its value comes from."""

    def __init__(self, name: str, source: str, parameter: str) -> None:
        self.name = name
        self.source = source
        self.parameter = parameter

    def value(self, component: object, ctx: dict) -> str | None:
        """The cell text, or None when the component has no such parameter."""
        if self.source == "parameter":
            return ctx["parameters"].get(self.parameter.lower())
        return str(_BUILTIN_SOURCES[self.source](component, ctx))  # type: ignore[operator]


def _load_config(path: Path) -> tuple[list[Column], dict]:
    config = tomllib.loads(path.read_text(encoding="utf-8"))

    raw_columns = config.get("columns")
    if not raw_columns:
        raise SystemExit(f"{path}: no [[columns]] / columns entries defined")

    columns: list[Column] = []
    for index, entry in enumerate(raw_columns):
        if not isinstance(entry, dict):
            raise SystemExit(f"{path}: columns[{index}] must be a table")
        name = str(entry.get("name", "")).strip()
        if not name:
            raise SystemExit(f"{path}: columns[{index}] is missing a name")
        source = str(entry.get("source", "parameter")).strip().lower()
        if source != "parameter" and source not in _BUILTIN_SOURCES:
            known = ", ".join(sorted(_BUILTIN_SOURCES))
            raise SystemExit(
                f"{path}: column {name!r} has unknown source {source!r}.\n"
                f"Use \"parameter\" or one of: {known}"
            )
        parameter = str(entry.get("parameter", name)).strip()
        columns.append(Column(name, source, parameter))

    seen: set[str] = set()
    for column in columns:
        if column.name in seen:
            raise SystemExit(f"{path}: duplicate column name {column.name!r}")
        seen.add(column.name)

    raw_options = config.get("options", {})
    options = {
        "include_non_bom_components": bool(
            raw_options.get("include_non_bom_components", False)
        ),
        "merge_multi_part_components": bool(
            raw_options.get("merge_multi_part_components", True)
        ),
        "sort_by": [str(name) for name in raw_options.get("sort_by", [])],
        "blank": str(raw_options.get("blank", "")),
    }
    return columns, options


# --------------------------------------------------------------------------
# Row building
# --------------------------------------------------------------------------


def _natural_key(value: str) -> tuple:
    """Sort key that orders R2 before R10 and is total across mixed text."""
    parts = re.split(r"(\d+)", value or "")
    return tuple(
        (1, int(part), "") if part.isdigit() else (0, 0, part.upper())
        for part in parts
        if part != ""
    )


def _collect_rows(
    schdoc_paths: list[Path],
    project_dir: Path,
    columns: list[Column],
    options: dict,
) -> tuple[list[OrderedDict], Counter, dict]:
    rows: list[OrderedDict] = []
    parameter_counts: Counter = Counter()
    stats = {
        "documents": len(schdoc_paths),
        "components_seen": 0,
        "skipped_non_bom": 0,
        "skipped_no_designator": 0,
    }

    for schdoc_path in schdoc_paths:
        document = AltiumSchDoc(schdoc_path)
        try:
            document_path = schdoc_path.relative_to(project_dir).as_posix()
        except ValueError:
            document_path = schdoc_path.as_posix()

        for component in document.components:
            stats["components_seen"] += 1

            parameters = _parameter_map(component)
            parameter_counts.update(_parameter_names(component))

            if not options["include_non_bom_components"] and not _includes_in_bom(
                component
            ):
                stats["skipped_non_bom"] += 1
                continue

            designator = _designator(component)
            if not designator:
                stats["skipped_no_designator"] += 1
                continue

            ctx = {
                "document": schdoc_path.name,
                "document_path": document_path,
                "designator": designator,
                "parameters": parameters,
            }

            row: OrderedDict = OrderedDict()
            for column in columns:
                row[column.name] = column.value(component, ctx)
            row["__designator__"] = designator
            row["__document__"] = schdoc_path.name
            row["__part_count__"] = _logical_part_count(component)
            rows.append(row)

    return rows, parameter_counts, stats


def _merge_multi_part(
    rows: list[OrderedDict], columns: list[Column]
) -> tuple[list[OrderedDict], int]:
    """Fold the placements of one multi-part symbol into a single row.

    Only components that declare part_count > 1 are merged; a repeated
    designator between two single-part components is a real design problem and
    is left visible as two rows. Where merged placements disagree on a column
    (most often Document, when the parts sit on different sheets) the distinct
    values are joined with "; " so nothing is dropped.
    """
    merged: OrderedDict = OrderedDict()
    passthrough: list[OrderedDict] = []
    merge_count = 0

    for row in rows:
        if row["__part_count__"] <= 1:
            passthrough.append(row)
            continue
        key = row["__designator__"]
        if key in merged:
            target = merged[key]
            for column in columns:
                existing = target[column.name]
                incoming = row[column.name]
                if incoming in (None, "") or incoming == existing:
                    continue
                if existing in (None, ""):
                    target[column.name] = incoming
                else:
                    seen = [part.strip() for part in str(existing).split(";")]
                    if str(incoming) not in seen:
                        target[column.name] = f"{existing}; {incoming}"
            merge_count += 1
        else:
            merged[key] = row

    return passthrough + list(merged.values()), merge_count


def _sort_rows(rows: list[OrderedDict], sort_by: list[str]) -> None:
    known = [name for name in sort_by if rows and name in rows[0]]
    if not known:
        known = ["__document__", "__designator__"]
    rows.sort(key=lambda row: tuple(_natural_key(str(row[name] or "")) for name in known))


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel opens the file with the right encoding on Windows.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_bom(
    path: Path, columns: list[Column], rows: list[OrderedDict], blank: str
) -> None:
    headers = [column.name for column in columns]
    body = [
        [blank if row[column.name] in (None, "") else str(row[column.name]) for column in columns]
        for row in rows
    ]
    _write_csv(path, headers, body)


def _write_parameter_index(path: Path, counts: Counter) -> None:
    body = [
        [name, str(count)]
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    _write_csv(path, ["Parameter", "Components"], body)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _resolve_schdocs(source: Path) -> tuple[list[Path], Path, str]:
    """Return (schdoc paths, project dir, label) for a .PrjPcb or a lone .SchDoc."""
    if source.suffix.lower() == ".schdoc":
        return [source], source.parent, source.stem
    project = AltiumPrjPcb(source)
    schdoc_paths = project.get_reachable_schdoc_paths()
    if not schdoc_paths:
        raise SystemExit(f"No SchDoc files reachable from project: {source}")
    return schdoc_paths, source.parent, source.stem


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the component parameters named in bom_fields.toml from every "
            "schematic in a project and write them to a CSV BOM."
        ),
    )
    parser.add_argument(
        "source",
        nargs="?",
        metavar="PROJECT.PrjPcb | SHEET.SchDoc",
        help=(
            "Project (or a single schematic) to read. Uses "
            f"<dir>/{_CONFIG_BASENAME} when present, otherwise the bundled config, "
            "and writes <dir>/<name>_BOM.csv. Omit to run the bundled hydroscope "
            "example, which writes to output/."
        ),
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="bom_fields.toml",
        help="Field configuration to use, overriding the search above.",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="BOM.csv",
        help="Where to write the BOM CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.source:
        source = Path(args.source).resolve()
        if not source.exists():
            raise SystemExit(f"Not found: {source}")
        schdoc_paths, project_dir, label = _resolve_schdocs(source)
        local_config = project_dir / _CONFIG_BASENAME
        config_path = local_config if local_config.exists() else _DEFAULT_CONFIG
        bom_path = project_dir / f"{label}_BOM.csv"
        parameter_index_path = project_dir / f"{label}_parameters.csv"
    else:
        schdoc_paths, project_dir, label = _resolve_schdocs(_DEFAULT_PRJPCB)
        config_path = _DEFAULT_CONFIG
        bom_path = SAMPLE_DIR / "output" / "bom.csv"
        parameter_index_path = SAMPLE_DIR / "output" / "available_parameters.csv"

    if args.config:
        config_path = Path(args.config).resolve()
    if args.output:
        bom_path = Path(args.output).resolve()
        parameter_index_path = bom_path.with_name(f"{bom_path.stem}_parameters.csv")

    if not config_path.exists():
        raise SystemExit(f"Field configuration not found: {config_path}")

    columns, options = _load_config(config_path)

    rows, parameter_counts, stats = _collect_rows(
        schdoc_paths, project_dir, columns, options
    )

    merged_count = 0
    if options["merge_multi_part_components"]:
        rows, merged_count = _merge_multi_part(rows, columns)

    _sort_rows(rows, options["sort_by"])

    _write_bom(bom_path, columns, rows, options["blank"])
    _write_parameter_index(parameter_index_path, parameter_counts)

    print(f"Project: {label}")
    print(f"Config:  {config_path}")
    print(f"SchDocs: {stats['documents']}")
    print(f"Components read: {stats['components_seen']}")
    if stats["skipped_non_bom"]:
        print(f"  skipped (not in BOM):   {stats['skipped_non_bom']}")
    if stats["skipped_no_designator"]:
        print(f"  skipped (no designator): {stats['skipped_no_designator']}")
    if merged_count:
        print(f"  merged multi-part placements: {merged_count}")
    print(f"BOM rows: {len(rows)}")

    # A column that is blank for every part is nearly always a name that does
    # not match the project's parameters — say so rather than shipping an
    # empty column silently.
    empty = [
        column.name
        for column in columns
        if column.source == "parameter"
        and not any(row[column.name] for row in rows)
    ]
    if empty:
        print(
            "\nNo component carries these parameters: " + ", ".join(empty) + "\n"
            f"See {parameter_index_path.name} for the names this project actually uses."
        )

    print("\nWrote:")
    print(f"  {bom_path}")
    print(f"  {parameter_index_path}")


if __name__ == "__main__":
    main()
