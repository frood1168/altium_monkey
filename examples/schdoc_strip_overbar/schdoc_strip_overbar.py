"""Normalize overbar notation in SchDoc net names, labels, and ports.

Altium uses backslash (\\) after a character to indicate an overline/overbar.
Some files also wrap overbar groups in curly-brace delimiters: {C\\S\\} means
"CS" with overbar over both letters.  Stray braces also appear as bus-index
notation ({0}, {1}, {2}, ...) with no overbar intent.

This script normalises all three cases:
  - Strips '{' and '}' delimiters, together with any '\\' that was applying
    overbar to the delimiter itself (so {C\\S\\} becomes C\\S\\, preserving
    the overbar on C and S in altium_monkey native format).
  - Stray '{}' with no following '\\' (e.g. bus indices like {2}) are stripped
    without touching surrounding '\\' characters.
  - '\\' characters that apply overbar to real content characters are left
    untouched, so the overbar renders correctly in Altium after saving.

Usage examples:
    # Process individual SchDoc files, writing to ./output/
    uv run python examples/schdoc_strip_overbar/schdoc_strip_overbar.py Sheet1.SchDoc Sheet2.SchDoc

    # Process all SchDocs in a project
    uv run python examples/schdoc_strip_overbar/schdoc_strip_overbar.py MyProject.PrjPcb

    # Preview changes without saving
    uv run python examples/schdoc_strip_overbar/schdoc_strip_overbar.py --dry-run Sheet1.SchDoc

    # Modify files in-place
    uv run python examples/schdoc_strip_overbar/schdoc_strip_overbar.py --in-place Sheet1.SchDoc

    # Write to a specific output directory
    uv run python examples/schdoc_strip_overbar/schdoc_strip_overbar.py --output-dir cleaned/ Sheet1.SchDoc
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from altium_monkey import (
    AltiumSchCrossSheetConnector,
    AltiumSchDoc,
    AltiumSchHarnessEntry,
    AltiumSchNetLabel,
    AltiumSchPin,
    AltiumSchPort,
    AltiumSchPowerPort,
    AltiumSchSheetEntry,
)
from altium_monkey.altium_prjpcb import AltiumPrjPcb

def normalize_overbar(text: str) -> str:
    """Remove '{'/'}' delimiters from Altium overbar notation, preserving '\\' markers.

    Altium stores overbar text as char followed by '\\' (e.g. C\\S\\ = CS with
    overbar).  Some sources wrap groups in curly braces: {C\\S\\}.  This function
    strips the braces and any '\\' that was marking a brace as an overbar target,
    leaving all other '\\' markers intact so the overbar survives in Altium.

    Examples:
        '{\\C\\S\\}\\' -> 'C\\S\\'   (CS with overbar preserved)
        'DO/IO_{1}'    -> 'DO/IO_1'   (stray brace stripped, no overbar)
    """
    result: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "{}":
            # Skip the brace.  If it is immediately followed by '\\', that
            # backslash was applying overbar to the brace being removed — skip
            # it too so we don't orphan an overbar marker onto the next char.
            if i + 1 < len(text) and text[i + 1] == "\\":
                i += 2
            else:
                i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def _clean_field(obj: object, field: str, counts: Counter) -> bool:
    """Normalize overbar notation on obj.field; return True if changed."""
    original = getattr(obj, field, None)
    if not isinstance(original, str):
        return False
    cleaned = normalize_overbar(original)
    if cleaned == original:
        return False
    setattr(obj, field, cleaned)
    counts[field] += 1
    return True


def process_schdoc(input_path: Path, output_path: Path | None, *, dry_run: bool) -> dict:
    """
    Strip overbar characters from all named objects in a SchDoc.

    Returns a summary dict. When dry_run is True the file is never written.
    """
    doc = AltiumSchDoc(input_path)
    counts: Counter[str] = Counter()
    changes: list[dict] = []

    for nl in doc.net_labels:
        if not isinstance(nl, AltiumSchNetLabel):
            continue
        orig = nl.text
        if _clean_field(nl, "text", counts):
            changes.append({"type": "net_label", "field": "text", "from": orig, "to": nl.text})

    for port in doc.ports:
        if not isinstance(port, AltiumSchPort):
            continue
        orig = port.name
        if _clean_field(port, "name", counts):
            changes.append({"type": "port", "field": "name", "from": orig, "to": port.name})

    for pp in doc.power_ports:
        if not isinstance(pp, AltiumSchPowerPort):
            continue
        orig = pp.text
        if _clean_field(pp, "text", counts):
            changes.append({"type": "power_port", "field": "text", "from": orig, "to": pp.text})

    for csc in doc.cross_sheet_connectors:
        if not isinstance(csc, AltiumSchCrossSheetConnector):
            continue
        orig = csc.text
        if _clean_field(csc, "text", counts):
            changes.append({"type": "cross_sheet_connector", "field": "text", "from": orig, "to": csc.text})

    for se in doc.sheet_entries:
        if not isinstance(se, AltiumSchSheetEntry):
            continue
        orig = se.name
        if _clean_field(se, "name", counts):
            changes.append({"type": "sheet_entry", "field": "name", "from": orig, "to": se.name})

    for he in doc.harness_entries:
        if not isinstance(he, AltiumSchHarnessEntry):
            continue
        orig = he.name
        if _clean_field(he, "name", counts):
            changes.append({"type": "harness_entry", "field": "name", "from": orig, "to": he.name})

    for component in doc.components:
        for pin in getattr(component, "pins", []):
            if not isinstance(pin, AltiumSchPin):
                continue
            orig_name = pin.name
            if _clean_field(pin, "name", counts):
                changes.append({"type": "pin", "field": "name", "from": orig_name, "to": pin.name})
            orig_desig = pin.designator
            if _clean_field(pin, "designator", counts):
                changes.append({"type": "pin", "field": "designator", "from": orig_desig, "to": pin.designator})

    total = sum(counts.values())

    if total > 0 and not dry_run and output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)

    return {
        "source": str(input_path),
        "output": str(output_path) if output_path else None,
        "saved": total > 0 and not dry_run and output_path is not None,
        "total_changes": total,
        "changes_by_field": dict(sorted(counts.items())),
        "changes": changes,
    }


def _resolve_output(input_path: Path, output_dir: Path | None, in_place: bool) -> Path | None:
    if in_place:
        return input_path
    if output_dir is not None:
        return output_dir / input_path.name
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize overbar notation in Altium SchDoc files. "
            "Strips '{'/'}' group delimiters (and any backslash marking them as overbar targets) "
            "while preserving '\\\\' markers on real content characters so overbars "
            "continue to render correctly in Altium. "
            "Applies to net labels, ports, power ports, cross-sheet connectors, "
            "sheet entries, harness entries, and pins."
        ),
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="FILE",
        help="One or more .SchDoc files, or a single .PrjPcb file.",
    )
    dest_group = parser.add_mutually_exclusive_group()
    dest_group.add_argument(
        "--output-dir",
        metavar="DIR",
        help=(
            "Write cleaned files to this directory (preserving filename). "
            "Defaults to an 'output/' subdirectory next to each source file when "
            "neither --output-dir nor --in-place is given."
        ),
    )
    dest_group.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite source files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing any files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every individual change.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    output_dir: Path | None = Path(args.output_dir) if args.output_dir else None

    # Collect SchDoc paths
    schdoc_paths: list[Path] = []
    for raw in args.inputs:
        p = Path(raw).resolve()
        if not p.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            sys.exit(1)
        suffix = p.suffix.lower()
        if suffix == ".prjpcb":
            project = AltiumPrjPcb(p)
            found = project.get_reachable_schdoc_paths()
            if not found:
                print(f"ERROR: no SchDoc files found in project: {p}", file=sys.stderr)
                sys.exit(1)
            schdoc_paths.extend(found)
        elif suffix == ".schdoc":
            schdoc_paths.append(p)
        else:
            print(f"ERROR: expected .SchDoc or .PrjPcb, got: {p}", file=sys.stderr)
            sys.exit(1)

    if not schdoc_paths:
        print("ERROR: no SchDoc files to process.", file=sys.stderr)
        sys.exit(1)

    dry_label = " (dry run)" if args.dry_run else ""
    grand_total = 0

    for src in schdoc_paths:
        if output_dir is not None:
            dest: Path | None = output_dir / src.name
        elif args.in_place:
            dest = src
        else:
            dest = src.parent / "output" / src.name

        result = process_schdoc(src, dest, dry_run=args.dry_run)
        total = result["total_changes"]
        grand_total += total

        if total == 0:
            print(f"{src.name}: no overbar characters found")
            continue

        save_note = ""
        if args.dry_run:
            save_note = " (not saved)"
        elif result["saved"]:
            save_note = f" -> {dest}"
        else:
            save_note = " (not saved — no output path)"

        print(f"{src.name}: {total} change(s){dry_label}{save_note}")

        by_field = result["changes_by_field"]
        for field, count in sorted(by_field.items()):
            print(f"  {field}: {count}")

        if args.verbose:
            for change in result["changes"]:
                print(f"    [{change['type']}.{change['field']}] {change['from']!r} -> {change['to']!r}")

    if len(schdoc_paths) > 1:
        print(f"\nTotal: {grand_total} change(s) across {len(schdoc_paths)} file(s)")


if __name__ == "__main__":
    main()
