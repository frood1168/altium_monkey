"""Apply symbol style settings from schlib_style.toml to SchLib files.

Reads the TOML generated (and optionally hand-edited) by
schlib_style_apply_extract.py and stamps pin visibility, pin text fonts, body
rectangle style, and line style onto every symbol in each target SchLib.

Per-symbol sections in the TOML ([SymbolName.pin] etc.) override [default.*]
for that specific symbol.  Omitting a section type leaves those objects
unchanged.

Usage:
    # Apply to a folder of SchLib files:
    uv run python examples/schlib_style_apply/schlib_style_apply.py [--toml STYLE.toml] SCHLIB_DIR

    # Apply to a single SchLib:
    uv run python examples/schlib_style_apply/schlib_style_apply.py [--toml STYLE.toml] MY.SchLib

    # Use built-in defaults (assets/schlib/ → output/):
    uv run python examples/schlib_style_apply/schlib_style_apply.py
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from pathlib import Path

from altium_monkey import AltiumSchLib, AltiumSchPin, LineWidth
from altium_monkey.altium_sch_enums import PinItemMode


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
_DEFAULT_LAYOUT_TOML = SAMPLE_DIR / "clean" / "schlib_style.toml"
_DEFAULT_SCHLIB_DIR = ASSETS_DIR / "schlib"
_DEFAULT_OUTPUT_DIR = SAMPLE_DIR / "output"

_LINE_WIDTH_VALUE = {"SMALLEST": 0, "SMALL": 1, "MEDIUM": 2, "LARGE": 3}


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _hex_to_bgr(hex_str: str) -> int:
    """Convert "#RRGGBB" to Win32 BGR integer."""
    h = hex_str.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


# ---------------------------------------------------------------------------
# Style applicators
# ---------------------------------------------------------------------------

def _apply_pin_style(symbol: object, style: dict, counts: Counter) -> None:
    """Stamp pin visibility and font onto all pins in a symbol."""
    show_name = bool(style.get("show_name", True))
    show_desig = bool(style.get("show_designator", True))
    name_font: str | None = style.get("name_font")
    name_font_size: int | None = style.get("name_font_size")
    desig_font: str | None = style.get("designator_font")
    desig_font_size: int | None = style.get("designator_font_size")

    for pin in getattr(symbol, "pins", []):
        if not isinstance(pin, AltiumSchPin):
            continue

        pin.show_name = show_name
        pin.show_designator = show_desig

        if name_font:
            pin.name_settings.font_mode = PinItemMode.CUSTOM
            pin.name_settings.font_id = None  # cleared so font_name drives resolution
            pin.name_settings.font_name = name_font
            pin.name_settings.font_size = name_font_size

        if desig_font:
            pin.designator_settings.font_mode = PinItemMode.CUSTOM
            pin.designator_settings.font_id = None
            pin.designator_settings.font_name = desig_font
            pin.designator_settings.font_size = desig_font_size

        counts["pin"] += 1


def _apply_rect_style(symbol: object, style: dict, counts: Counter) -> None:
    """Stamp color and line width onto all rectangles in a symbol."""
    border_color = _hex_to_bgr(style["border_color"]) if "border_color" in style else None
    fill_color = _hex_to_bgr(style["fill_color"]) if "fill_color" in style else None
    lw_name = style.get("line_width")
    lw = LineWidth(_LINE_WIDTH_VALUE[lw_name]) if lw_name in _LINE_WIDTH_VALUE else None
    is_solid = style.get("is_solid")

    for rect in getattr(symbol, "rectangles", []):
        if border_color is not None:
            rect.color = border_color
        if fill_color is not None:
            rect.area_color = fill_color
        if lw is not None:
            rect.line_width = lw
        if is_solid is not None:
            rect.is_solid = bool(is_solid)
        counts["rect"] += 1


def _apply_line_style(symbol: object, style: dict, counts: Counter) -> None:
    """Stamp color and line width onto all lines and polylines in a symbol."""
    color = _hex_to_bgr(style["color"]) if "color" in style else None
    lw_name = style.get("line_width")
    lw = LineWidth(_LINE_WIDTH_VALUE[lw_name]) if lw_name in _LINE_WIDTH_VALUE else None

    for obj in list(getattr(symbol, "lines", [])) + list(getattr(symbol, "polylines", [])):
        if color is not None:
            obj.color = color
        if lw is not None:
            obj.line_width = lw
        counts["line"] += 1


def _resolve_style(layout: dict, sym_name: str, section: str) -> dict | None:
    """Return per-symbol style for section, falling back to [default]."""
    sym_override = layout.get(sym_name, {}).get(section)
    if sym_override is not None:
        return sym_override
    return layout.get("default", {}).get(section)


def apply_style_to_schlib(
    input_path: Path,
    output_path: Path,
    layout: dict,
) -> dict:
    schlib = AltiumSchLib(input_path)
    counts: Counter[str] = Counter()
    sym_results = []

    for symbol in schlib.symbols:
        sym_counts: Counter[str] = Counter()

        pin_style = _resolve_style(layout, symbol.name, "pin")
        if pin_style is not None:
            _apply_pin_style(symbol, pin_style, sym_counts)

        rect_style = _resolve_style(layout, symbol.name, "body_rect")
        if rect_style is not None:
            _apply_rect_style(symbol, rect_style, sym_counts)

        line_style = _resolve_style(layout, symbol.name, "line")
        if line_style is not None:
            _apply_line_style(symbol, line_style, sym_counts)

        counts.update(sym_counts)
        sym_results.append({
            "name": symbol.name,
            "pins_updated": sym_counts["pin"],
            "rects_updated": sym_counts["rect"],
            "lines_updated": sym_counts["line"],
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # sync_pin_text_data=True regenerates PinTextData streams from the updated
    # pin settings so font changes are actually written to the output file.
    schlib.save(output_path, sync_pin_text_data=True)

    return {
        "source": str(input_path),
        "output": str(output_path),
        "symbols": len(sym_results),
        "pins_updated": counts["pin"],
        "rects_updated": counts["rect"],
        "lines_updated": counts["line"],
        "symbol_results": sym_results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _find_schlib_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.iterdir()
        if p.suffix.lower() in {".schlib"}
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply schlib_style.toml style settings to SchLib files. "
            "Per-symbol [SymbolName.*] sections override [default.*] for that symbol."
        ),
    )
    parser.add_argument(
        "target",
        nargs="?",
        metavar="TARGET",
        help=(
            "Path to a .SchLib file or directory of .SchLib files to update. "
            f"Defaults to {_DEFAULT_SCHLIB_DIR.name}."
        ),
    )
    parser.add_argument(
        "--toml",
        metavar="STYLE.toml",
        help=(
            f"Path to schlib_style.toml. Defaults to {_DEFAULT_LAYOUT_TOML}."
        ),
    )
    parser.add_argument(
        "--output",
        metavar="OUTPUT_DIR",
        help=(
            "Directory for updated SchLib files. "
            f"Defaults to {_DEFAULT_OUTPUT_DIR}."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    toml_path = Path(args.toml).resolve() if args.toml else _DEFAULT_LAYOUT_TOML
    target_path = Path(args.target).resolve() if args.target else _DEFAULT_SCHLIB_DIR
    output_dir = Path(args.output).resolve() if args.output else _DEFAULT_OUTPUT_DIR

    if not toml_path.exists():
        print(
            f"schlib_style.toml not found at {toml_path}\n"
            "Run schlib_style_apply_extract.py first to generate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    layout = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    schlib_files = _find_schlib_files(target_path)

    if not schlib_files:
        print(f"No .SchLib files found at {target_path}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        apply_style_to_schlib(p, output_dir / p.name, layout)
        for p in schlib_files
    ]

    manifest = {
        "style_config": str(toml_path),
        "target": str(target_path),
        "output_dir": str(output_dir),
        "schlib_count": len(results),
        "total_pins_updated": sum(r["pins_updated"] for r in results),
        "total_rects_updated": sum(r["rects_updated"] for r in results),
        "total_lines_updated": sum(r["lines_updated"] for r in results),
        "libraries": results,
    }
    manifest_path = output_dir / "schlib_style_apply_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Style config: {toml_path}")
    print(f"Target: {target_path}")
    print(f"Processed: {len(results)} SchLib file(s)")
    print(f"Pins updated:  {manifest['total_pins_updated']}")
    print(f"Rects updated: {manifest['total_rects_updated']}")
    print(f"Lines updated: {manifest['total_lines_updated']}")
    print(f"Wrote files:   {output_dir}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
