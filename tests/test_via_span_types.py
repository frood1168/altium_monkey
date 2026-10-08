"""Via-span types in the three places AD keeps them.

Learned from an AD-saved PcbDoc whose Layer Stack Manager had uVia ticked
(2026-10): a span's type is coded differently in each store, so
`AltiumLayerPair` keeps the Board6 `LAYERPAIR` code (`drill_pair_type_raw`)
apart from the Layer Stack Manager via type (`via_span_type_raw`):

- Board6 `LAYERPAIR<n>`: no type on a via span; 2 + BACKDRILL on a back-drill.
  AD reads 2 as a back-drill whatever BACKDRILL says, so a buried span written
  with 2 showed up as a stray back-drill.
- Board6 `VIATYPE<n>`, after the LAYERPAIR rows: one per via span,
  DRILLPAIRTYPE=1 on a microvia (the uVia box). Absent when there is none.
- `V9_STACKCUSTOMDATA` XML / `.stackupx` `<ViaSpan Type>` and `.stackup`
  `VIASPAN TYPE`: ThruVia 0, BlindVia 1, BuriedVia 2, StackedMicroVia 3,
  named "μVia a:b"; back-drills in their own list with the Back Drills feature.
"""

from __future__ import annotations

import base64
import re
import zlib
from pathlib import Path

from altium_monkey import (
    AltiumLayerStackDocument,
    AltiumPcbDoc,
    AltiumRigidCopperLayerSpec,
    AltiumRigidDielectricLayerSpec,
    AltiumStackupDocument,
    PcbDocBuilder,
)
from altium_monkey.altium_layer_stack_document import (
    LAYER_PAIR_DRILL_PAIR_TYPE_BACKDRILL,
    VIA_SPAN_TYPE_BURIED,
    VIA_SPAN_TYPE_MICROVIA,
    VIA_SPAN_TYPE_THRU,
)
from altium_monkey.altium_ole import AltiumOleFile


def _stack() -> AltiumLayerStackDocument:
    return AltiumLayerStackDocument.from_rigid_stack(
        name="Via span types",
        copper_layers=[
            AltiumRigidCopperLayerSpec(f"L{index}", copper_thickness_mils=0.6)
            for index in range(1, 7)
        ],
        dielectrics_between=[
            AltiumRigidDielectricLayerSpec(
                f"D{index}", thickness_mils=4.0, dielectric_constant=3.5, material="test"
            )
            for index in range(1, 6)
        ],
    )


def _with_spans(document: AltiumLayerStackDocument) -> AltiumLayerStackDocument:
    document = document.with_via_span(
        "TOP", "BOTTOM", pair_index=0, via_span_type_raw=VIA_SPAN_TYPE_THRU
    )
    document = document.with_via_span(
        "TOP", "MID1", pair_index=1, via_span_type_raw=VIA_SPAN_TYPE_MICROVIA
    )
    document = document.with_via_span(
        "MID1", "MID2", pair_index=2, via_span_type_raw=VIA_SPAN_TYPE_MICROVIA
    )
    document = document.with_via_span(
        "MID2", "MID3", pair_index=3, via_span_type_raw=VIA_SPAN_TYPE_BURIED
    )
    return document.with_backdrill_span(
        "MID4",
        "BOTTOM",
        pair_index=4,
        drill_pair_type_raw=LAYER_PAIR_DRILL_PAIR_TYPE_BACKDRILL,
        is_inverted=True,
    )


def _save(document: AltiumLayerStackDocument, path: Path) -> Path:
    builder = PcbDocBuilder()
    builder.set_layer_stack_document(document)
    builder.set_outline_rectangle_mils(0.0, 0.0, 1000.0, 1000.0)
    builder.save(path)
    return path


def _board6(path: Path) -> list[tuple[str, str]]:
    text = AltiumOleFile(str(path)).openstream(["Board6", "Data"]).decode("utf-8", "replace")
    return [
        (key, value.strip())   # the last entry of a segment carries its line end
        for key, value in (item.split("=", 1) for item in text.split("|") if "=" in item)
    ]


def test_pcbdoc_keeps_layer_pairs_untyped_and_flags_microvias_in_viatype_rows(
    tmp_path: Path,
) -> None:
    rows = _board6(_save(_with_spans(_stack()), tmp_path / "spans.PcbDoc"))
    record = dict(rows)

    # LAYERPAIR: only the back-drill carries a type
    for index in range(4):
        assert f"LAYERPAIR{index}DRILLPAIRTYPE" not in record
    assert record["LAYERPAIR4DRILLPAIRTYPE"] == "2"
    assert record["LAYERPAIR4BACKDRILL"] == "TRUE"

    # VIATYPE: one row per via span, uVia flagged; none for the back-drill
    assert [record.get(f"VIATYPE{index}DRILLPAIRTYPE") for index in range(4)] == [
        None,
        "1",
        "1",
        None,
    ]
    assert (record["VIATYPE1LOW"], record["VIATYPE1HIGH"]) == ("TOP", "MID1")
    assert "VIATYPE4LOW" not in record

    # the VIATYPE rows follow the LAYERPAIR rows, in one block
    keys = [key for key, _ in rows]
    block = [index for index, key in enumerate(keys) if key.startswith(("LAYERPAIR", "VIATYPE"))]
    assert block == list(range(block[0], block[-1] + 1))
    assert keys[block[-1]].startswith("VIATYPE")

    # every span names the board's substack, not the master stack
    substack = record["V9_SUBSTACK0_ID"]
    assert substack != record["V9_MASTERSTACK_ID"]
    for index in range(5):
        assert record[f"LAYERPAIR{index}SUBSTACK_0"] == substack
    for index in range(4):
        assert record[f"VIATYPE{index}SUBSTACK_0"] == substack

    # the Layer Stack Manager XML (.stackupx, and V9_STACKCUSTOMDATA when a
    # PcbDoc embeds it) types each span
    xmls = [_with_spans(_stack()).to_stackupx().to_bytes().decode("utf-8-sig")]
    if "V9_STACKCUSTOMDATA" in record:
        xmls.append(
            zlib.decompress(base64.b64decode(record["V9_STACKCUSTOMDATA"])).decode("utf-8-sig")
        )
    for xml in xmls:
        spans = re.findall(r'<ViaSpan [^>]*AutoName="([^"]+)" Type="([^"]+)"', xml)
        assert spans == [
            ("Thru 1:6", "ThruVia"),
            ("μVia 1:2", "StackedMicroVia"),
            ("μVia 2:3", "StackedMicroVia"),
            ("Buried 3:4", "BuriedVia"),
        ]


def test_pcbdoc_read_back_finds_the_microvias(tmp_path: Path) -> None:
    path = _save(_with_spans(_stack()), tmp_path / "spans.PcbDoc")
    pairs = AltiumLayerStackDocument.from_pcbdoc(AltiumPcbDoc.from_file(path)).layer_pairs

    assert [pair.is_microvia for pair in pairs] == [False, True, True, False, False]
    assert [pair.is_backdrill for pair in pairs] == [False, False, False, False, True]
    assert pairs[1].via_span_type_raw == VIA_SPAN_TYPE_MICROVIA


def test_board_without_microvias_has_no_viatype_rows(tmp_path: Path) -> None:
    document = _stack().with_via_span(
        "MID2", "MID3", pair_index=1, via_span_type_raw=VIA_SPAN_TYPE_BURIED
    )
    rows = _board6(_save(document, tmp_path / "plain.PcbDoc"))

    assert not [key for key, _ in rows if key.startswith("VIATYPE")]
    assert "LAYERPAIR1DRILLPAIRTYPE" not in dict(rows)


def test_stackup_writes_lsm_types_and_reads_them_back_without_leaking_into_layerpair(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spans.stackup"
    AltiumStackupDocument.from_layer_stack_document(_with_spans(_stack())).write(path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM, as AD writes it
    record = AltiumStackupDocument.from_file(path).to_record_mapping()
    spans = sorted(
        (record[key], record[key[: -len("NAME")] + "TYPE"])
        for key in record
        if key.startswith("VIASPAN_V8_") and key.endswith("NAME")
    )
    assert spans == [("Buried 3:4", "2"), ("Thru 1:6", "0"), ("μVia 1:2", "3"), ("μVia 2:3", "3")]
    assert [record[key] for key in record if key.startswith("DRILLPAIR_V8_") and key.endswith("NAME")] == [
        "BD 5:6"
    ]
    features = [record[key] for key in record if re.fullmatch(r"FEATURE_\d+NAME", key)]
    assert features[-1] == "Back Drills"

    pairs = AltiumLayerStackDocument.from_stackup(path).layer_pairs
    # the LSM type reaches the LAYERPAIR code only for thru (0), where they agree
    spans_back = [(p.via_span_type_raw, p.drill_pair_type_raw) for p in pairs if not p.is_backdrill]
    assert sorted(spans_back, key=str) == [(0, 0), (2, None), (3, None), (3, None)]
    assert [p.drill_pair_type_raw for p in pairs if p.is_backdrill] == [2]

    # a PcbDoc written from the read-back stack: no stray back-drill, uVia kept
    rows = dict(_board6(_save(AltiumLayerStackDocument.from_stackup(path), tmp_path / "re.PcbDoc")))
    buried = next(
        key[: -len("LOW")]
        for key, value in rows.items()
        if re.fullmatch(r"LAYERPAIR\d+LOW", key) and value == "MID2"
    )
    assert f"{buried}DRILLPAIRTYPE" not in rows
    assert sum(1 for key, value in rows.items() if re.fullmatch(r"VIATYPE\d+DRILLPAIRTYPE", key) and value == "1") == 2
