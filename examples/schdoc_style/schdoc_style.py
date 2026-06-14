from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from collections import Counter
from filecmp import cmp as files_equal
from pathlib import Path
from typing import TypeVar

from altium_monkey import (
    AltiumSchArc,
    AltiumSchCrossSheetConnector,
    AltiumSchDesignator,
    AltiumSchDoc,
    AltiumSchEllipse,
    AltiumSchHarnessType,
    AltiumSchLabel,
    AltiumSchLine,
    AltiumSchNoErc,
    AltiumSchNote,
    AltiumSchParameter,
    AltiumSchPolygon,
    AltiumSchPolyline,
    AltiumSchRectangle,
    AltiumSchSignalHarness,
    ColorValue,
    LineStyle,
    LineWidth,
    NoErcSymbol,
    SchFontSpec,
    SchHorizontalAlign,
    SchSheetEntryArrowKind,
    TextJustification,
)
from altium_monkey.altium_prjpcb import AltiumPrjPcb



T = TypeVar("T")

_LINE_WIDTH_MAP: dict[str, LineWidth] = {
    "SMALLEST": LineWidth.SMALLEST,
    "SMALL": LineWidth.SMALL,
    "MEDIUM": LineWidth.MEDIUM,
    "LARGE": LineWidth.LARGE,
}

_LINE_STYLE_MAP: dict[str, LineStyle] = {
    "SOLID": LineStyle.SOLID,
    "DASHED": LineStyle.DASHED,
    "DOTTED": LineStyle.DOTTED,
    "DASH_DOT": LineStyle.DASH_DOT,
}

_ARROW_KIND_MAP: dict[str, int] = {
    "BLOCK_TRIANGLE": SchSheetEntryArrowKind.BLOCK_TRIANGLE.value,
    "TRIANGLE": SchSheetEntryArrowKind.TRIANGLE.value,
    "ARROW": SchSheetEntryArrowKind.ARROW.value,
    "ARROW_TAIL": SchSheetEntryArrowKind.ARROW_TAIL.value,
}

_NO_ERC_SYMBOL_MAP: dict[str, NoErcSymbol] = {
    "CROSS_THIN": NoErcSymbol.CROSS_THIN,
    "CROSS": NoErcSymbol.CROSS,
    "CROSS_SMALL": NoErcSymbol.CROSS_SMALL,
    "CHECKBOX": NoErcSymbol.CHECKBOX,
    "TRIANGLE": NoErcSymbol.TRIANGLE,
}

_ALIGNMENT_MAP: dict[str, SchHorizontalAlign] = {
    "CENTER": SchHorizontalAlign.CENTER,
    "LEFT": SchHorizontalAlign.LEFT,
    "RIGHT": SchHorizontalAlign.RIGHT,
}

_JUSTIFICATION_MAP: dict[str, int] = {
    "BOTTOM_LEFT": TextJustification.BOTTOM_LEFT.value,
    "BOTTOM_CENTER": TextJustification.BOTTOM_CENTER.value,
    "BOTTOM_RIGHT": TextJustification.BOTTOM_RIGHT.value,
    "CENTER_LEFT": TextJustification.CENTER_LEFT.value,
    "CENTER_CENTER": TextJustification.CENTER_CENTER.value,
    "CENTER_RIGHT": TextJustification.CENTER_RIGHT.value,
    "TOP_LEFT": TextJustification.TOP_LEFT.value,
    "TOP_CENTER": TextJustification.TOP_CENTER.value,
    "TOP_RIGHT": TextJustification.TOP_RIGHT.value,
}


def _color(hex_str: str) -> int:
    return ColorValue.from_hex(hex_str).win32


def _has_font_keys(cfg: dict) -> bool:
    return any(k in cfg for k in ("font_name", "font_size", "bold", "italic"))


def _resolve_font(record: object, cfg: dict, *, default_size: int = 10) -> SchFontSpec:
    current = getattr(record, "font", None)
    return SchFontSpec(
        name=cfg.get("font_name", current.name if current else "Arial"),
        size=cfg.get("font_size", current.size if current else default_size),
        bold=cfg.get("bold", current.bold if current else False),
        italic=cfg.get("italic", current.italic if current else False),
        underline=current.underline if current else False,
        strikeout=current.strikeout if current else False,
    )


def _objects_of_exact_type(schdoc: AltiumSchDoc, record_type: type[T]) -> list[T]:
    return [obj for obj in schdoc.objects.of_type(record_type) if type(obj) is record_type]


def _apply_document_style(schdoc: AltiumSchDoc, cfg: dict) -> Counter[str]:
    counts: Counter[str] = Counter()
    doc_cfg = cfg.get("document", {})
    if not doc_cfg or schdoc.sheet is None:
        return counts
    if "background_color" in doc_cfg:
        schdoc.sheet.area_color = _color(doc_cfg["background_color"])
        counts["document_background"] += 1
    if "system_font_name" in doc_cfg or "system_font_size" in doc_cfg:
        current_info = schdoc.font_manager.get_font_info(schdoc.sheet.system_font)
        name = doc_cfg.get("system_font_name", current_info["name"] if current_info else "Arial")
        size = doc_cfg.get("system_font_size", current_info["size"] if current_info else 10)
        schdoc.sheet.system_font = schdoc.font_manager.get_or_create_font(
            font_name=name, font_size=size
        )
        counts["document_system_font"] += 1
    return counts


def _apply_component_style(
    component: object,
    designator_cfg: dict,
    parameter_cfg: dict,
    graphics_cfg: dict,
    counts: Counter[str],
) -> None:
    for parameter in getattr(component, "parameters", []):
        if isinstance(parameter, AltiumSchDesignator):
            if _has_font_keys(designator_cfg):
                parameter.font = _resolve_font(parameter, designator_cfg)
            if "color" in designator_cfg:
                parameter.color = _color(designator_cfg["color"])
            counts["component_designators"] += 1
        elif isinstance(parameter, AltiumSchParameter) and not parameter.is_hidden:
            if _has_font_keys(parameter_cfg):
                parameter.font = _resolve_font(parameter, parameter_cfg)
            if "color" in parameter_cfg:
                parameter.color = _color(parameter_cfg["color"])
            counts["component_parameters"] += 1

    for graphic in getattr(component, "graphics", []):
        if isinstance(graphic, AltiumSchRectangle):
            bounds = graphic.bounds_mils
            if bounds.width_mils > 100 or bounds.height_mils > 100:
                if "color" in graphics_cfg:
                    graphic.color = _color(graphics_cfg["color"])
                if "area_color" in graphics_cfg:
                    graphic.area_color = _color(graphics_cfg["area_color"])
                    graphic.is_solid = True
                    graphic.transparent = False
                if "line_width" in graphics_cfg:
                    lw = _LINE_WIDTH_MAP.get(graphics_cfg["line_width"].upper())
                    if lw is not None:
                        graphic.line_width = lw
                if "line_style" in graphics_cfg:
                    ls = _LINE_STYLE_MAP.get(graphics_cfg["line_style"].upper())
                    if ls is not None:
                        graphic.line_style = ls
                counts["component_body_rectangles"] += 1
        elif isinstance(graphic, AltiumSchLine | AltiumSchPolyline | AltiumSchArc):
            if "color" in graphics_cfg:
                graphic.color = _color(graphics_cfg["color"])
            counts["component_graphics"] += 1
        elif isinstance(graphic, AltiumSchPolygon):
            if "color" in graphics_cfg:
                graphic.color = _color(graphics_cfg["color"])
            counts["component_graphics"] += 1
        elif isinstance(graphic, AltiumSchEllipse):
            if "color" in graphics_cfg:
                graphic.color = _color(graphics_cfg["color"])
            counts["component_graphics"] += 1


def style_schdoc(input_path: Path, output_path: Path, style: dict) -> dict[str, object]:
    schdoc = AltiumSchDoc(input_path)
    counts: Counter[str] = Counter()
    counts.update(_apply_document_style(schdoc, style))

    wire_cfg = style.get("wire", {})
    for wire in schdoc.wires:
        if "color" in wire_cfg:
            wire.color = _color(wire_cfg["color"])
        counts["wires"] += 1

    net_label_cfg = style.get("net_label", {})
    for net_label in schdoc.net_labels:
        if _has_font_keys(net_label_cfg):
            net_label.font = _resolve_font(net_label, net_label_cfg)
        if "color" in net_label_cfg:
            net_label.color = _color(net_label_cfg["color"])
        counts["net_labels"] += 1

    port_cfg = style.get("port", {})
    for port in schdoc.ports:
        if _has_font_keys(port_cfg):
            port.font = _resolve_font(port, port_cfg)
        if "color" in port_cfg:
            port.color = _color(port_cfg["color"])
        if "area_color" in port_cfg:
            port.area_color = _color(port_cfg["area_color"])
        if "text_color" in port_cfg:
            port.text_color = _color(port_cfg["text_color"])
        if "width_mils" in port_cfg or "height_mils" in port_cfg:
            port.auto_size = False
        if "width_mils" in port_cfg:
            port.width_mils = port_cfg["width_mils"]
        if "height_mils" in port_cfg:
            port.height_mils = port_cfg["height_mils"]
        if "alignment" in port_cfg:
            al = _ALIGNMENT_MAP.get(port_cfg["alignment"].upper())
            if al is not None:
                port.alignment = al
        if "cross_reference" in port_cfg:
            port.cross_reference = bool(port_cfg["cross_reference"])
        counts["ports"] += 1

    power_port_cfg = style.get("power_port", {})
    for power_port in schdoc.power_ports:
        if _has_font_keys(power_port_cfg):
            power_port.font = _resolve_font(power_port, power_port_cfg)
        if "color" in power_port_cfg:
            power_port.color = _color(power_port_cfg["color"])
        counts["power_ports"] += 1

    cross_sheet_cfg = style.get("cross_sheet_connector", {})
    for connector in schdoc.cross_sheet_connectors:
        if not isinstance(connector, AltiumSchCrossSheetConnector):
            continue
        if _has_font_keys(cross_sheet_cfg):
            connector.font = _resolve_font(connector, cross_sheet_cfg)
        if "color" in cross_sheet_cfg:
            connector.color = _color(cross_sheet_cfg["color"])
        if "justification" in cross_sheet_cfg:
            jv = _JUSTIFICATION_MAP.get(cross_sheet_cfg["justification"].upper())
            if jv is not None:
                connector.justification = jv
        counts["cross_sheet_connectors"] += 1

    note_cfg = style.get("note", {})
    for note in schdoc.objects.of_type(AltiumSchNote):
        if _has_font_keys(note_cfg):
            note.font = _resolve_font(note, note_cfg)
        if "area_color" in note_cfg:
            note.area_color = _color(note_cfg["area_color"])
            note.is_solid = True
        counts["notes"] += 1

    text_string_cfg = style.get("text_string", {})
    for text_string in _objects_of_exact_type(schdoc, AltiumSchLabel):
        if _has_font_keys(text_string_cfg):
            text_string.font = _resolve_font(text_string, text_string_cfg)
        counts["text_strings"] += 1

    no_erc_cfg = style.get("no_erc", {})
    for no_erc in schdoc.objects.of_type(AltiumSchNoErc):
        if "color" in no_erc_cfg:
            no_erc.color = _color(no_erc_cfg["color"])
        if "symbol" in no_erc_cfg:
            symbol_value = _NO_ERC_SYMBOL_MAP.get(no_erc_cfg["symbol"].upper())
            if symbol_value is not None:
                no_erc.symbol = symbol_value
        counts["no_ercs"] += 1

    signal_harness_cfg = style.get("signal_harness", {})
    for signal_harness in schdoc.objects.of_type(AltiumSchSignalHarness):
        if "color" in signal_harness_cfg:
            signal_harness.color = _color(signal_harness_cfg["color"])
        if "line_width" in signal_harness_cfg:
            lw = _LINE_WIDTH_MAP.get(signal_harness_cfg["line_width"].upper())
            if lw is not None:
                signal_harness.line_width = lw
        counts["signal_harnesses"] += 1

    harness_connector_cfg = style.get("harness_connector", {})
    for connector in schdoc.harness_connectors:
        if "color" in harness_connector_cfg:
            connector.color = _color(harness_connector_cfg["color"])
        if "area_color" in harness_connector_cfg:
            connector.area_color = _color(harness_connector_cfg["area_color"])
        counts["harness_connectors"] += 1

    harness_entry_cfg = style.get("harness_entry", {})
    for entry in schdoc.harness_entries:
        if _has_font_keys(harness_entry_cfg):
            entry.font = _resolve_font(entry, harness_entry_cfg)
        if "text_color" in harness_entry_cfg:
            entry.text_color = _color(harness_entry_cfg["text_color"])
        counts["harness_entries"] += 1

    harness_type_cfg = style.get("harness_type", {})
    for harness_type in schdoc.objects.of_type(AltiumSchHarnessType):
        if _has_font_keys(harness_type_cfg):
            harness_type.font = _resolve_font(harness_type, harness_type_cfg)
        if "color" in harness_type_cfg:
            harness_type.color = _color(harness_type_cfg["color"])
        counts["harness_types"] += 1

    sheet_symbol_cfg = style.get("sheet_symbol", {})
    sheet_entry_cfg = style.get("sheet_entry", {})
    for sheet_symbol in schdoc.sheet_symbols:
        if "color" in sheet_symbol_cfg:
            sheet_symbol.color = _color(sheet_symbol_cfg["color"])
        if "area_color" in sheet_symbol_cfg:
            sheet_symbol.area_color = _color(sheet_symbol_cfg["area_color"])
        if "line_width" in sheet_symbol_cfg:
            lw = _LINE_WIDTH_MAP.get(sheet_symbol_cfg["line_width"].upper())
            if lw is not None:
                sheet_symbol.line_width = lw
        counts["sheet_symbols"] += 1

        for entry in getattr(sheet_symbol, "entries", []):
            if _has_font_keys(sheet_entry_cfg):
                entry.font = _resolve_font(entry, sheet_entry_cfg)
            if "color" in sheet_entry_cfg:
                entry.color = _color(sheet_entry_cfg["color"])
            if "area_color" in sheet_entry_cfg:
                entry.area_color = _color(sheet_entry_cfg["area_color"])
            if "text_color" in sheet_entry_cfg:
                entry.text_color = _color(sheet_entry_cfg["text_color"])
            if "arrow_kind" in sheet_entry_cfg:
                ak = _ARROW_KIND_MAP.get(sheet_entry_cfg["arrow_kind"].upper())
                if ak is not None:
                    entry.arrow_kind = ak
            counts["sheet_entries"] += 1

    component_cfg = style.get("component", {})
    designator_cfg = component_cfg.get("designator", {})
    parameter_cfg = component_cfg.get("parameter", {})
    graphics_cfg = component_cfg.get("graphics", {})
    for component in schdoc.components:
        _apply_component_style(component, designator_cfg, parameter_cfg, graphics_cfg, counts)
        counts["components"] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    schdoc.save(output_path)

    return {
        "source": str(input_path),
        "output": str(output_path),
        "mutations": dict(sorted(counts.items())),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply a style.toml config to every SchDoc in an Altium project.",
    )
    parser.add_argument(
        "project",
        metavar="PROJECT.PrjPcb",
        help="Path to the .PrjPcb file. Reads examples/assets/style.toml and writes styled SchDocs to <project_dir>/clean/.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    prjpcb_path = Path(args.project).resolve()
    style_path = Path(__file__).parent.parent / "assets" / "style.toml"
    output_dir = prjpcb_path.parent / "clean"

    if not style_path.exists():
        print(
            f"style.toml not found at {style_path}\n"
            "Run schdoc_style_extract.py first to generate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    style = tomllib.loads(style_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)

    project = AltiumPrjPcb(prjpcb_path)
    schdoc_paths = project.get_reachable_schdoc_paths()
    if not schdoc_paths:
        raise RuntimeError(f"No SchDoc files found in project: {prjpcb_path}")

    project_dir = prjpcb_path.parent
    output_prjpcb = output_dir / prjpcb_path.name
    documents = [
        style_schdoc(p, output_dir / p.relative_to(project_dir), style)
        for p in schdoc_paths
    ]

    if not output_prjpcb.exists() or not files_equal(prjpcb_path, output_prjpcb, shallow=False):
        shutil.copy2(prjpcb_path, output_prjpcb)

    manifest = {
        "source_project": str(prjpcb_path),
        "output_project": str(output_prjpcb),
        "style_config": str(style_path),
        "document_count": len(documents),
        "documents": documents,
    }
    manifest_path = output_dir / "schdoc_style_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    totals: Counter[str] = Counter()
    for doc in documents:
        totals.update(doc.get("mutations", {}))

    print(f"Loaded project: {prjpcb_path}")
    print(f"Style config: {style_path}")
    print(f"Styled SchDocs: {len(documents)}")
    if totals:
        summary = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(totals.items()) if v)
        print(f"Mutations: {summary}")
    print(f"Wrote SchDocs: {output_dir}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
