from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from altium_monkey import (
    AltiumSchDoc,
    AltiumSchLib,
    ColorValue,
    LineWidth,
    PinElectrical,
    PinTextRotation,
    Rotation90,
    SchFontSpec,
    SchPointMils,
    SchRectMils,
    make_sch_pin,
    make_sch_rectangle,
)


SAMPLE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_SCHLIB = OUTPUT_DIR / "schdoc_vertical_pin_svg.SchLib"
OUTPUT_SCHDOC = OUTPUT_DIR / "schdoc_vertical_pin_svg.SchDoc"
OUTPUT_SVG = OUTPUT_DIR / "schdoc_vertical_pin_svg.svg"
OUTPUT_MANIFEST = OUTPUT_DIR / "vertical_pin_svg_manifest.json"
SYMBOL_NAME = "PIN_ROTATION_SYMBOL"
PIN_TEXT_FONT = SchFontSpec(name="Arial", size=10)


PIN_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "up_default",
        "designator": "UPD",
        "name": "UP_DEFAULT",
        "orientation": Rotation90.DEG_90,
        "location": SchPointMils.from_mils(-250, 350),
        "expected_name_rotated": True,
        "expected_designator_rotated": True,
        "uses_custom_pin_text_settings": False,
        "note": "90 degree pin with native/default pin text settings.",
    },
    {
        "id": "down_default",
        "designator": "DND",
        "name": "DOWN_DEFAULT",
        "orientation": Rotation90.DEG_270,
        "location": SchPointMils.from_mils(-50, -350),
        "expected_name_rotated": True,
        "expected_designator_rotated": True,
        "uses_custom_pin_text_settings": False,
        "note": "270 degree pin with native/default pin text settings.",
    },
    {
        "id": "up_component_horizontal",
        "designator": "UCH",
        "name": "UP_COMPONENT_HORIZONTAL",
        "orientation": Rotation90.DEG_90,
        "location": SchPointMils.from_mils(150, 350),
        "name_rotation": PinTextRotation.HORIZONTAL,
        "designator_rotation": PinTextRotation.HORIZONTAL,
        "name_reference_to_component": True,
        "designator_reference_to_component": True,
        "expected_name_rotated": False,
        "expected_designator_rotated": False,
        "uses_custom_pin_text_settings": True,
        "note": "90 degree pin with component-referenced horizontal pin text.",
    },
    {
        "id": "down_component_horizontal",
        "designator": "DCH",
        "name": "DOWN_COMPONENT_HORIZONTAL",
        "orientation": Rotation90.DEG_270,
        "location": SchPointMils.from_mils(350, -350),
        "name_rotation": PinTextRotation.HORIZONTAL,
        "designator_rotation": PinTextRotation.HORIZONTAL,
        "name_reference_to_component": True,
        "designator_reference_to_component": True,
        "expected_name_rotated": False,
        "expected_designator_rotated": False,
        "uses_custom_pin_text_settings": True,
        "note": "270 degree pin with component-referenced horizontal pin text.",
    },
    {
        "id": "right_custom_vertical",
        "designator": "RCV",
        "name": "RIGHT_CUSTOM_VERTICAL",
        "orientation": Rotation90.DEG_0,
        "location": SchPointMils.from_mils(-550, 100),
        "name_rotation": PinTextRotation.VERTICAL,
        "designator_rotation": PinTextRotation.VERTICAL,
        "expected_name_rotated": True,
        "expected_designator_rotated": True,
        "uses_custom_pin_text_settings": True,
        "note": "0 degree pin with explicit vertical name and designator text.",
    },
    {
        "id": "left_custom_vertical",
        "designator": "LCV",
        "name": "LEFT_CUSTOM_VERTICAL",
        "orientation": Rotation90.DEG_180,
        "location": SchPointMils.from_mils(550, -100),
        "name_rotation": PinTextRotation.VERTICAL,
        "designator_rotation": PinTextRotation.VERTICAL,
        "expected_name_rotated": True,
        "expected_designator_rotated": True,
        "uses_custom_pin_text_settings": True,
        "note": "180 degree pin with explicit vertical name and designator text.",
    },
)


def _svg_text_element(svg: str, text: str) -> str:
    match = re.search(rf"<text\b[^>]*>{re.escape(text)}</text>", svg)
    if match is None:
        raise AssertionError(f"SVG text element not found for {text!r}")
    return match.group(0)


def _has_rotate_transform(svg_text_element: str) -> bool:
    return 'transform="rotate(' in svg_text_element


def build_schlib(output_path: Path = OUTPUT_SCHLIB) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schlib = AltiumSchLib()
    symbol = schlib.add_symbol(SYMBOL_NAME)
    symbol.set_description("Vertical pin SVG proof symbol")
    symbol.add_object(
        make_sch_rectangle(
            bounds_mils=SchRectMils.from_corners_mils(-450, 250, 450, -250),
            color=ColorValue.from_hex("#000000"),
            fill_color=ColorValue.from_hex("#FFF4CC"),
            line_width=LineWidth.SMALL,
            fill_background=True,
            transparent_fill=False,
        )
    )

    for case in PIN_CASES:
        pin_kwargs: dict[str, Any] = {}
        if bool(case.get("uses_custom_pin_text_settings", False)):
            pin_kwargs["name_font"] = PIN_TEXT_FONT
            pin_kwargs["designator_font"] = PIN_TEXT_FONT
        symbol.add_pin(
            make_sch_pin(
                designator=str(case["designator"]),
                name=str(case["name"]),
                location_mils=case["location"],
                orientation=case["orientation"],
                length_mils=140,
                electrical_type=PinElectrical.PASSIVE,
                owner_part_id=1,
                owner_part_display_mode=0,
                name_rotation=case.get("name_rotation"),
                designator_rotation=case.get("designator_rotation"),
                name_reference_to_component=bool(
                    case.get("name_reference_to_component", False)
                ),
                designator_reference_to_component=bool(
                    case.get("designator_reference_to_component", False)
                ),
                **pin_kwargs,
            )
        )

    symbol.add_designator("U?", 0, 350)
    symbol.add_parameter("Comment", "Vertical pin SVG proof", x=0, y=-350)
    schlib.save(output_path)
    return output_path


def build_schdoc(
    schlib_path: Path = OUTPUT_SCHLIB,
    output_path: Path = OUTPUT_SCHDOC,
) -> AltiumSchDoc:
    schdoc = AltiumSchDoc()
    component = schdoc.add_component_from_library(
        library_path=schlib_path,
        symbol_name=SYMBOL_NAME,
        designator="U1",
        x=3000,
        y=3000,
    )
    component.design_item_id = SYMBOL_NAME
    component.set_designator_style(
        x=3000,
        y=3350,
        font_name="Arial",
        font_size=12,
        bold=True,
    )
    component.set_comment_style(
        x=3000,
        y=2650,
        font_name="Arial",
        font_size=10,
        bold=False,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    schdoc.save(output_path)
    return AltiumSchDoc(output_path)


def write_svg_proof(schdoc: AltiumSchDoc) -> dict[str, Any]:
    svg = schdoc.to_svg(include_border=False)
    OUTPUT_SVG.write_text(svg, encoding="utf-8")
    schdoc_json = schdoc.to_json()
    pin_json_records = [
        item
        for item in schdoc_json.get("Objects", [])
        if item.get("ObjectType") == "Pin"
    ]
    pin_json_by_name = {str(item.get("Name", "")): item for item in pin_json_records}
    component = schdoc.components[0]

    cases: list[dict[str, Any]] = []
    for case in PIN_CASES:
        name_element = _svg_text_element(svg, str(case["name"]))
        designator_element = _svg_text_element(svg, str(case["designator"]))
        name_rotated = _has_rotate_transform(name_element)
        designator_rotated = _has_rotate_transform(designator_element)
        pin_record = pin_json_by_name.get(str(case["name"]), {})
        custom_pin_record_keys = [
            key
            for key in pin_record
            if str(key).startswith(
                ("Name_Custom", "Designator_Custom", "PinName_", "PinDesignator_")
            )
        ]
        cases.append(
            {
                "id": case["id"],
                "pin_orientation": case["orientation"].name,
                "pin_name": case["name"],
                "pin_designator": case["designator"],
                "uses_custom_pin_text_settings": bool(
                    case["uses_custom_pin_text_settings"]
                ),
                "pin_record_has_custom_text_fields": bool(custom_pin_record_keys),
                "name_rotated": name_rotated,
                "designator_rotated": designator_rotated,
                "expected_name_rotated": case["expected_name_rotated"],
                "expected_designator_rotated": case["expected_designator_rotated"],
                "name_matches_expected": name_rotated == case["expected_name_rotated"],
                "designator_matches_expected": designator_rotated
                == case["expected_designator_rotated"],
                "note": case["note"],
            }
        )

    vertical_default_cases = [
        item for item in cases if item["id"] in {"up_default", "down_default"}
    ]
    component_horizontal_cases = [
        item
        for item in cases
        if item["id"] in {"up_component_horizontal", "down_component_horizontal"}
    ]
    custom_vertical_cases = [
        item
        for item in cases
        if item["id"] in {"right_custom_vertical", "left_custom_vertical"}
    ]
    manifest = {
        "schema": "altium_monkey.examples.schdoc_vertical_pin_svg.a0",
        "schlib": OUTPUT_SCHLIB.relative_to(SAMPLE_DIR).as_posix(),
        "schdoc": OUTPUT_SCHDOC.relative_to(SAMPLE_DIR).as_posix(),
        "svg": OUTPUT_SVG.relative_to(SAMPLE_DIR).as_posix(),
        "symbol_name": SYMBOL_NAME,
        "placed_component": {
            "lib_reference": component.lib_reference,
            "source_library_name": component.source_library_name,
            "design_item_id": component.design_item_id,
            "pin_count": len(component.pins),
        },
        "placed_pin_record_count": len(pin_json_records),
        "placed_pin_records_are_text": all(
            "BinaryData" not in item for item in pin_json_records
        ),
        "case_count": len(cases),
        "cases": cases,
        "vertical_pin_names_rotated": all(
            item["name_rotated"] for item in vertical_default_cases
        ),
        "vertical_pin_designators_rotated": all(
            item["designator_rotated"] for item in vertical_default_cases
        ),
        "component_horizontal_names_not_rotated": all(
            not item["name_rotated"] for item in component_horizontal_cases
        ),
        "component_horizontal_designators_not_rotated": all(
            not item["designator_rotated"] for item in component_horizontal_cases
        ),
        "custom_vertical_names_rotated": all(
            item["name_rotated"] for item in custom_vertical_cases
        ),
        "custom_vertical_designators_rotated": all(
            item["designator_rotated"] for item in custom_vertical_cases
        ),
        "all_cases_match_expected": all(
            item["name_matches_expected"] and item["designator_matches_expected"]
            for item in cases
        ),
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    schlib_path = build_schlib()
    schdoc = build_schdoc(schlib_path)
    manifest = write_svg_proof(schdoc)
    print(f"Wrote {OUTPUT_SCHLIB.relative_to(SAMPLE_DIR)}")
    print(f"Wrote {OUTPUT_SCHDOC.relative_to(SAMPLE_DIR)}")
    print(f"Wrote {OUTPUT_SVG.relative_to(SAMPLE_DIR)}")
    print(f"Wrote {OUTPUT_MANIFEST.relative_to(SAMPLE_DIR)}")
    print(f"Vertical pin SVG proof: {manifest['all_cases_match_expected']}")


if __name__ == "__main__":
    main()
