"""Extract symbol style settings from a reference SchLib to schlib_style.toml.

Run against a SchLib where symbols have been manually styled (pin visibility,
fonts, body rectangle color/line width) to capture those settings as a reusable
template.  The generated TOML is then applied to other libraries via
schlib_style_apply.py.

Usage:
    uv run python examples/schlib_style_apply/schlib_style_apply_extract.py [REFERENCE.SchLib]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from altium_monkey import AltiumSchLib, AltiumSchPin, LineWidth
from altium_monkey.altium_sch_enums import PinItemMode


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
_DEFAULT_REF_SCHLIB = ASSETS_DIR / "schlib" / "IIM-42352.SchLib"
_DEFAULT_OUTPUT = SAMPLE_DIR / "clean" / "schlib_style.toml"

_LINE_WIDTH_NAME = {0: "SMALLEST", 1: "SMALL", 2: "MEDIUM", 3: "LARGE"}


# ---------------------------------------------------------------------------
# Color helpers — Altium stores colors as Win32 BGR integers (0x00BBGGRR).
# The TOML uses "#RRGGBB" hex strings for readability.
# ---------------------------------------------------------------------------

def _bgr_to_hex(bgr: int | None) -> str:
    bgr = int(bgr or 0)
    r = (bgr >> 0) & 0xFF
    g = (bgr >> 8) & 0xFF
    b = (bgr >> 16) & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def _toml_key(k: str) -> str:
    return k if re.match(r"^[A-Za-z0-9_-]+$", k) else f'"{k}"'


# ---------------------------------------------------------------------------
# Per-symbol style extractors
# ---------------------------------------------------------------------------

def _extract_pin_style(symbol: Any, fm: Any) -> dict[str, Any] | None:
    """Return dominant pin style across all pins in a symbol, or None if no pins."""
    pins = list(symbol.pins)
    if not pins:
        return None

    total = len(pins)
    show_name = sum(1 for p in pins if p.show_name) > total // 2
    show_desig = sum(1 for p in pins if p.show_designator) > total // 2

    result: dict[str, Any] = {
        "show_name": show_name,
        "show_designator": show_desig,
    }

    # Font: first pin with a custom name font
    for pin in pins:
        if (
            pin.name_settings.font_mode == PinItemMode.CUSTOM
            and pin.name_settings.font_id is not None
            and fm is not None
        ):
            fid = pin.name_settings.font_id
            result["name_font"] = fm.get_font_name(fid)
            result["name_font_size"] = fm.get_font_size(fid)
            break

    # Font: first pin with a custom designator font
    for pin in pins:
        if (
            pin.designator_settings.font_mode == PinItemMode.CUSTOM
            and pin.designator_settings.font_id is not None
            and fm is not None
        ):
            fid = pin.designator_settings.font_id
            result["designator_font"] = fm.get_font_name(fid)
            result["designator_font_size"] = fm.get_font_size(fid)
            break

    return result


def _extract_rect_style(symbol: Any) -> dict[str, Any] | None:
    """Return style from the first (body) rectangle in a symbol, or None."""
    rects = list(symbol.rectangles)
    if not rects:
        return None
    r = rects[0]
    return {
        "border_color": _bgr_to_hex(getattr(r, "color", 0)),
        "fill_color": _bgr_to_hex(getattr(r, "area_color", 0xFFFFFF)),
        "line_width": _LINE_WIDTH_NAME.get(getattr(r, "line_width", LineWidth.SMALL).value, "SMALL"),
        "is_solid": bool(getattr(r, "is_solid", True)),
    }


def _extract_line_style(symbol: Any) -> dict[str, Any] | None:
    """Return style from the first line or polyline in a symbol, or None."""
    objs = list(symbol.lines) + list(symbol.polylines)
    if not objs:
        return None
    obj = objs[0]
    return {
        "color": _bgr_to_hex(getattr(obj, "color", 0)),
        "line_width": _LINE_WIDTH_NAME.get(getattr(obj, "line_width", LineWidth.SMALLEST).value, "SMALLEST"),
    }


def _symbol_style(symbol: Any, fm: Any) -> dict[str, Any]:
    return {
        "pin": _extract_pin_style(symbol, fm),
        "body_rect": _extract_rect_style(symbol),
        "line": _extract_line_style(symbol),
    }


# ---------------------------------------------------------------------------
# TOML generation
# ---------------------------------------------------------------------------

def _pin_lines(s: dict[str, Any]) -> list[str]:
    lines = [
        f"show_name = {str(s['show_name']).lower()}",
        f"show_designator = {str(s['show_designator']).lower()}",
    ]
    if "name_font" in s:
        lines += [
            f'name_font = "{s["name_font"]}"',
            f"name_font_size = {s['name_font_size']}",
        ]
    if "designator_font" in s:
        lines += [
            f'designator_font = "{s["designator_font"]}"',
            f"designator_font_size = {s['designator_font_size']}",
        ]
    return lines


def _rect_lines(s: dict[str, Any]) -> list[str]:
    return [
        f'border_color = "{s["border_color"]}"',
        f'fill_color = "{s["fill_color"]}"',
        f'line_width = "{s["line_width"]}"',
        f"is_solid = {str(s['is_solid']).lower()}",
    ]


def _line_style_lines(s: dict[str, Any]) -> list[str]:
    return [
        f'color = "{s["color"]}"',
        f'line_width = "{s["line_width"]}"',
    ]


def _generate_toml(
    styles: dict[str, dict],
    default_name: str,
    header: list[str],
) -> str:
    lines: list[str] = list(header) + [""]

    # Write [default] section using the nominated reference symbol
    default_style = styles.get(default_name, {})

    lines.append("[default.pin]")
    if default_style.get("pin"):
        lines.extend(_pin_lines(default_style["pin"]))
    else:
        lines += ["show_name = true", "show_designator = true"]
    lines.append("")

    if default_style.get("body_rect"):
        lines.append("[default.body_rect]")
        lines.extend(_rect_lines(default_style["body_rect"]))
        lines.append("")

    if default_style.get("line"):
        lines.append("[default.line]")
        lines.extend(_line_style_lines(default_style["line"]))
        lines.append("")

    # Per-symbol sections — all symbols from the reference
    for sym_name, style in sorted(styles.items()):
        wrote_any = False

        if style.get("pin"):
            lines.append(f"[{_toml_key(sym_name)}.pin]")
            lines.extend(_pin_lines(style["pin"]))
            lines.append("")
            wrote_any = True

        if style.get("body_rect"):
            lines.append(f"[{_toml_key(sym_name)}.body_rect]")
            lines.extend(_rect_lines(style["body_rect"]))
            lines.append("")
            wrote_any = True

        if style.get("line"):
            lines.append(f"[{_toml_key(sym_name)}.line]")
            lines.extend(_line_style_lines(style["line"]))
            lines.append("")
            wrote_any = True

        if not wrote_any:
            # Symbol has no pins/rects/lines — note it for awareness
            lines.append(f"# {sym_name}: no pins, rectangles, or lines found in reference")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract symbol style settings from a reference SchLib into "
            "schlib_style.toml. Edit the TOML then apply it with "
            "schlib_style_apply.py."
        ),
    )
    parser.add_argument(
        "schlib",
        nargs="?",
        metavar="REFERENCE.SchLib",
        help=(
            "Reference SchLib with symbols manually styled. "
            "Writes schlib_style.toml to <schlib_dir>/clean/. "
            f"Defaults to {_DEFAULT_REF_SCHLIB.name}."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.schlib:
        ref_path = Path(args.schlib).resolve()
        output_toml = ref_path.parent / "clean" / "schlib_style.toml"
    else:
        ref_path = _DEFAULT_REF_SCHLIB
        output_toml = _DEFAULT_OUTPUT

    schlib = AltiumSchLib(ref_path)
    fm = getattr(schlib, "font_manager", None)

    symbols = list(schlib.symbols)
    styles: dict[str, dict] = {sym.name: _symbol_style(sym, fm) for sym in symbols}
    default_name = symbols[0].name if symbols else ""

    total_pins = sum(1 for s in styles.values() if s.get("pin"))
    total_rects = sum(1 for s in styles.values() if s.get("body_rect"))
    total_lines = sum(1 for s in styles.values() if s.get("line"))

    header = [
        "# Generated by schlib_style_apply_extract.py",
        f"# Reference SchLib: {ref_path}",
        f"# Symbols: {len(styles)}  (with pins: {total_pins}  with body rect: {total_rects}  with lines: {total_lines})",
        "#",
        "# Structure:",
        "#   [default.pin]        — pin show_name/show_designator and font applied to",
        "#                          all symbols not explicitly listed below",
        "#   [default.body_rect]  — border/fill color and line width for all body rects",
        "#   [default.line]       — color and line width for all lines/polylines",
        "#   [SymbolName.pin]     — per-symbol pin style (overrides default)",
        "#   [SymbolName.body_rect] — per-symbol rect style (overrides default)",
        "#   [SymbolName.line]    — per-symbol line style (overrides default)",
        "#",
        "# Colors: \"#RRGGBB\" hex strings (converted from Altium Win32 BGR format).",
        "# line_width: SMALLEST | SMALL | MEDIUM | LARGE",
        "# Omit name_font / designator_font to leave pin text font unchanged.",
    ]

    output_toml.parent.mkdir(parents=True, exist_ok=True)
    output_toml.write_text(
        _generate_toml(styles, default_name, header), encoding="utf-8"
    )

    print(f"Reference SchLib: {ref_path}")
    print(f"Symbols: {len(styles)}")
    print(f"  With pins: {total_pins}  body rects: {total_rects}  lines: {total_lines}")
    print(f"Wrote: {output_toml}")


if __name__ == "__main__":
    main()
