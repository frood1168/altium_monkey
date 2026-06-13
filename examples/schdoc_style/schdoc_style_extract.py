from __future__ import annotations

import argparse
from pathlib import Path

from altium_monkey import (
    AltiumSchArc,
    AltiumSchCrossSheetConnector,
    AltiumSchDesignator,
    AltiumSchDoc,
    AltiumSchHarnessType,
    AltiumSchLabel,
    AltiumSchLine,
    AltiumSchNoErc,
    AltiumSchNote,
    AltiumSchParameter,
    AltiumSchPolyline,
    AltiumSchRectangle,
    AltiumSchSignalHarness,
    ColorValue,
    NoErcSymbol,
    SchHorizontalAlign,
    SchSheetEntryArrowKind,
    TextJustification,
)
from altium_monkey.altium_prjpcb import AltiumPrjPcb



_LINE_WIDTH_NAME: dict[int, str] = {0: "SMALLEST", 1: "SMALL", 2: "MEDIUM", 3: "LARGE"}
_LINE_STYLE_NAME: dict[int, str] = {0: "SOLID", 1: "DASHED", 2: "DOTTED", 3: "DASH_DOT"}
_ARROW_KIND_NAME: dict[int, str] = {
    SchSheetEntryArrowKind.BLOCK_TRIANGLE.value: "BLOCK_TRIANGLE",
    SchSheetEntryArrowKind.TRIANGLE.value: "TRIANGLE",
    SchSheetEntryArrowKind.ARROW.value: "ARROW",
    SchSheetEntryArrowKind.ARROW_TAIL.value: "ARROW_TAIL",
}
_NO_ERC_SYMBOL_NAME: dict[int, str] = {
    int(NoErcSymbol.CROSS_THIN): "CROSS_THIN",
    int(NoErcSymbol.CROSS): "CROSS",
    int(NoErcSymbol.CROSS_SMALL): "CROSS_SMALL",
    int(NoErcSymbol.CHECKBOX): "CHECKBOX",
    int(NoErcSymbol.TRIANGLE): "TRIANGLE",
}

_ALIGNMENT_NAME: dict[int, str] = {
    SchHorizontalAlign.CENTER.value: "CENTER",
    SchHorizontalAlign.LEFT.value: "LEFT",
    SchHorizontalAlign.RIGHT.value: "RIGHT",
}

_JUSTIFICATION_NAME: dict[int, str] = {
    TextJustification.BOTTOM_LEFT.value: "BOTTOM_LEFT",
    TextJustification.BOTTOM_CENTER.value: "BOTTOM_CENTER",
    TextJustification.BOTTOM_RIGHT.value: "BOTTOM_RIGHT",
    TextJustification.CENTER_LEFT.value: "CENTER_LEFT",
    TextJustification.CENTER_CENTER.value: "CENTER_CENTER",
    TextJustification.CENTER_RIGHT.value: "CENTER_RIGHT",
    TextJustification.TOP_LEFT.value: "TOP_LEFT",
    TextJustification.TOP_CENTER.value: "TOP_CENTER",
    TextJustification.TOP_RIGHT.value: "TOP_RIGHT",
}

# Section order matches style.toml
_SECTION_ORDER = [
    "document",
    "wire",
    "net_label",
    "port",
    "power_port",
    "cross_sheet_connector",
    "note",
    "text_string",
    "no_erc",
    "signal_harness",
    "harness_connector",
    "harness_entry",
    "harness_type",
    "sheet_symbol",
    "sheet_entry",
    "component.designator",
    "component.parameter",
    "component.graphics",
]


def _toml_value(val: object) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        return f'"{val}"'
    return str(val)


class StyleCollector:
    """
    Accumulates per-section, per-property style values across all SchDocs.

    For each property, the first-seen value becomes the canonical entry.
    Any additional distinct values are tracked as conflicts and emitted as
    TOML comments when the file is generated.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, list]] = {s: {} for s in _SECTION_ORDER}

    def record(self, section: str, prop: str, value: object) -> None:
        if value is None:
            return
        values = self._data.setdefault(section, {}).setdefault(prop, [])
        if value not in values:
            values.append(value)

    def record_font(self, section: str, record: object) -> None:
        font = getattr(record, "font", None)
        if font is None:
            return
        self.record(section, "font_name", font.name)
        self.record(section, "font_size", font.size)
        self.record(section, "bold", font.bold)
        self.record(section, "italic", font.italic)

    def record_color(self, section: str, record: object, attr: str, key: str) -> None:
        val = getattr(record, attr, None)
        if val is not None:
            self.record(section, key, ColorValue.from_win32(val).hex)

    def record_line_width(self, section: str, record: object) -> None:
        val = getattr(record, "line_width", None)
        if val is not None:
            name = _LINE_WIDTH_NAME.get(int(val))
            if name is not None:
                self.record(section, "line_width", name)

    def record_line_style(self, section: str, record: object) -> None:
        val = getattr(record, "line_style", None)
        if val is not None:
            name = _LINE_STYLE_NAME.get(int(val))
            if name is not None:
                self.record(section, "line_style", name)

    def to_toml(self, header_lines: list[str]) -> str:
        lines: list[str] = list(header_lines) + [""]

        for section in _SECTION_ORDER:
            props = self._data.get(section, {})
            if not props:
                continue

            # Suppress uniformly-false flags (italic, underline, strikeout) — noise reduction.
            effective: list[tuple[str, list]] = [
                (prop, values)
                for prop, values in props.items()
                if not (prop in ("italic", "underline", "strikeout") and values == [False])
            ]
            if not effective:
                continue

            lines.append(f"[{section}]")
            for prop, values in effective:
                lines.append(f"{prop} = {_toml_value(values[0])}")

            conflicts = [
                f"# {prop} = {_toml_value(val)}"
                for prop, values in effective
                for val in values[1:]
            ]
            if conflicts:
                lines.append("# Conflicts found:")
                lines.extend(conflicts)

            lines.append("")

        return "\n".join(lines)


def _extract_from_schdoc(schdoc: AltiumSchDoc, c: StyleCollector) -> None:
    if schdoc.sheet is not None:
        c.record_color("document", schdoc.sheet, "area_color", "background_color")
        info = schdoc.font_manager.get_font_info(schdoc.sheet.system_font)
        if info:
            c.record("document", "system_font_name", info["name"])
            c.record("document", "system_font_size", info["size"])

    for wire in schdoc.wires:
        c.record_color("wire", wire, "color", "color")

    for net_label in schdoc.net_labels:
        c.record_font("net_label", net_label)
        c.record_color("net_label", net_label, "color", "color")

    for port in schdoc.ports:
        c.record_font("port", port)
        c.record_color("port", port, "color", "color")
        c.record_color("port", port, "area_color", "area_color")
        c.record_color("port", port, "text_color", "text_color")
        c.record("port", "width_mils", port.width_mils)
        c.record("port", "height_mils", port.height_mils)
        al_name = _ALIGNMENT_NAME.get(int(port.alignment))
        if al_name is not None:
            c.record("port", "alignment", al_name)

    for power_port in schdoc.power_ports:
        c.record_font("power_port", power_port)
        c.record_color("power_port", power_port, "color", "color")

    for connector in schdoc.cross_sheet_connectors:
        if not isinstance(connector, AltiumSchCrossSheetConnector):
            continue
        c.record_font("cross_sheet_connector", connector)
        c.record_color("cross_sheet_connector", connector, "color", "color")
        jv_name = _JUSTIFICATION_NAME.get(int(getattr(connector, "justification", 0)))
        if jv_name is not None:
            c.record("cross_sheet_connector", "justification", jv_name)

    for note in schdoc.objects.of_type(AltiumSchNote):
        c.record_font("note", note)
        c.record_color("note", note, "area_color", "area_color")

    for text_string in schdoc.objects.of_type(AltiumSchLabel):
        if type(text_string) is not AltiumSchLabel:
            continue
        c.record_font("text_string", text_string)

    for no_erc in schdoc.objects.of_type(AltiumSchNoErc):
        c.record_color("no_erc", no_erc, "color", "color")
        symbol_name = _NO_ERC_SYMBOL_NAME.get(int(no_erc.symbol))
        if symbol_name is not None:
            c.record("no_erc", "symbol", symbol_name)

    for signal_harness in schdoc.objects.of_type(AltiumSchSignalHarness):
        c.record_color("signal_harness", signal_harness, "color", "color")
        c.record_line_width("signal_harness", signal_harness)

    for connector in schdoc.harness_connectors:
        c.record_color("harness_connector", connector, "color", "color")
        c.record_color("harness_connector", connector, "area_color", "area_color")
        c.record("harness_connector", "width_mils", connector.xsize)
        c.record("harness_connector", "height_mils", connector.ysize)

    for entry in schdoc.harness_entries:
        c.record_font("harness_entry", entry)
        c.record_color("harness_entry", entry, "text_color", "text_color")

    for harness_type in schdoc.objects.of_type(AltiumSchHarnessType):
        c.record_font("harness_type", harness_type)
        c.record_color("harness_type", harness_type, "color", "color")

    for sheet_symbol in schdoc.sheet_symbols:
        c.record_color("sheet_symbol", sheet_symbol, "area_color", "area_color")
        c.record_line_width("sheet_symbol", sheet_symbol)
        c.record("sheet_symbol", "width_mils", getattr(sheet_symbol, "x_size", None))
        c.record("sheet_symbol", "height_mils", getattr(sheet_symbol, "y_size", None))

        for entry in getattr(sheet_symbol, "entries", []):
            c.record_font("sheet_entry", entry)
            c.record_color("sheet_entry", entry, "color", "color")
            c.record_color("sheet_entry", entry, "area_color", "area_color")
            c.record_color("sheet_entry", entry, "text_color", "text_color")
            ak = _ARROW_KIND_NAME.get(int(getattr(entry, "arrow_kind", -1)))
            if ak is not None:
                c.record("sheet_entry", "arrow_kind", ak)

    for component in schdoc.components:
        for parameter in getattr(component, "parameters", []):
            if isinstance(parameter, AltiumSchDesignator):
                c.record_font("component.designator", parameter)
                c.record_color("component.designator", parameter, "color", "color")
            elif isinstance(parameter, AltiumSchParameter) and not parameter.is_hidden:
                c.record_font("component.parameter", parameter)
                c.record_color("component.parameter", parameter, "color", "color")

        for graphic in getattr(component, "graphics", []):
            if isinstance(graphic, AltiumSchRectangle):
                bounds = graphic.bounds_mils
                if bounds.width_mils > 100 or bounds.height_mils > 100:
                    c.record_color("component.graphics", graphic, "color", "color")
                    c.record_color("component.graphics", graphic, "area_color", "area_color")
                    c.record_line_width("component.graphics", graphic)
                    c.record_line_style("component.graphics", graphic)
            elif isinstance(graphic, AltiumSchLine | AltiumSchArc | AltiumSchPolyline):
                c.record_color("component.graphics", graphic, "color", "color")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract current schematic styles from an Altium project into a style.toml seed file.",
    )
    parser.add_argument(
        "project",
        metavar="PROJECT.PrjPcb",
        help="Path to the .PrjPcb file. Writes extracted styles to <project_dir>/clean/style.toml.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    prjpcb_path = Path(args.project).resolve()
    output_style = prjpcb_path.parent / "clean" / "style.toml"

    project = AltiumPrjPcb(prjpcb_path)
    schdoc_paths = project.get_reachable_schdoc_paths()
    if not schdoc_paths:
        raise RuntimeError(f"No SchDoc files found in project: {prjpcb_path}")

    collector = StyleCollector()
    for path in schdoc_paths:
        schdoc = AltiumSchDoc(path)
        _extract_from_schdoc(schdoc, collector)

    header = [
        "# Generated by schdoc_style_extract.py",
        f"# Source project: {prjpcb_path}",
        f"# SchDocs analyzed: {len(schdoc_paths)}",
        "#",
        "# For each property the first value seen across all elements is written",
        "# uncommented. Additional distinct values are captured as comments.",
        "# Edit as needed, then run schdoc_style.py with the same project path.",
    ]

    output_style.parent.mkdir(parents=True, exist_ok=True)
    output_style.write_text(collector.to_toml(header), encoding="utf-8")

    print(f"Loaded project: {prjpcb_path}")
    print(f"SchDocs analyzed: {len(schdoc_paths)}")
    print(f"Wrote: {output_style}")


if __name__ == "__main__":
    main()
