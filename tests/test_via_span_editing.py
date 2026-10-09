"""Via spans edited on a PcbDoc loaded from disk (not built in this session).

An imported board (Allegro HDI through KiCad) arrives
with one TOP-BOTTOM drill pair and every via through. Declaring the real spans
and moving each via onto its span must change Board6 (LAYERPAIR / VIATYPE
rows only) and Vias6, nothing else.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from altium_monkey import (
    AltiumLayerStackDocument,
    AltiumPcbDoc,
    AltiumRigidCopperLayerSpec,
    AltiumRigidDielectricLayerSpec,
    PcbDocBuilder,
)
from altium_monkey.altium_layer_stack_document import (
    VIA_SPAN_TYPE_BURIED,
    VIA_SPAN_TYPE_MICROVIA,
    VIA_SPAN_TYPE_THRU,
)


def _board(path: Path) -> Path:
    stack = AltiumLayerStackDocument.from_rigid_stack(
        name="Via span editing",
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
    ).with_via_span("TOP", "BOTTOM", pair_index=0, via_span_type_raw=VIA_SPAN_TYPE_THRU)
    builder = PcbDocBuilder()
    builder.set_layer_stack_document(stack)
    builder.set_outline_rectangle_mils(0.0, 0.0, 1000.0, 1000.0)
    for x in (100.0, 200.0, 300.0):
        builder.add_via(position_mils=(x, 100.0), diameter_mils=10.0, hole_size_mils=5.0)
    builder.save(path)
    return path


def _board6(doc: AltiumPcbDoc) -> list[tuple[str, str]]:
    body = doc._raw_streams["Board6/Data"][4:].decode("latin-1").rstrip("\x00\r\n")
    return [tuple(entry.split("=", 1)) for entry in body.split("|") if "=" in entry]


def _is_pair_row(key: str) -> bool:
    return key.upper().startswith(("LAYERPAIR", "VIATYPE"))


def test_declared_spans_and_via_spans_survive_a_save_and_nothing_else_moves(tmp_path: Path) -> None:
    source = AltiumPcbDoc.from_file(_board(tmp_path / "plain.PcbDoc"))
    before = dict(source._raw_streams)
    rows_before = _board6(source)

    micro = source.add_via_span("TOP", "MID1", via_span_type_raw=VIA_SPAN_TYPE_MICROVIA)
    buried = source.add_via_span("MID1", "MID4", via_span_type_raw=VIA_SPAN_TYPE_BURIED)
    assert (micro.pair_index, buried.pair_index) == (1, 2)
    source.set_via_layer_span(source.vias[0], "TOP", "MID1")
    source.set_via_layer_span(source.vias[1], "MID1", "MID4")
    source.save(tmp_path / "spans.PcbDoc")

    saved = AltiumPcbDoc.from_file(tmp_path / "spans.PcbDoc")
    spans = [(p.low_layer_token, p.high_layer_token, p.via_span_type_raw == VIA_SPAN_TYPE_MICROVIA)
             for p in saved.via_spans()]
    assert spans == [("TOP", "BOTTOM", False), ("TOP", "MID1", True), ("MID1", "MID4", False)]
    assert [(v.layer_start, v.layer_end) for v in saved.vias] == [(1, 2), (2, 5), (1, 32)]

    rows = _board6(saved)
    record = dict(rows)
    assert [record.get(f"VIATYPE{i}DRILLPAIRTYPE") for i in range(3)] == [None, "1", None]
    assert all(f"LAYERPAIR{i}DRILLPAIRTYPE" not in record for i in range(3))
    # every other Board6 key, in its order, untouched; the segment ends ('\r') all still there
    assert [r for r in rows if not _is_pair_row(r[0])] == [r for r in rows_before if not _is_pair_row(r[0])]
    assert saved._raw_streams["Board6/Data"].count(b"\r") == before["Board6/Data"].count(b"\r")
    changed = {name for name in set(before) | set(saved._raw_streams)
               if before.get(name) != saved._raw_streams.get(name)}
    assert changed <= {"Board6/Data", "Vias6/Data"}


def test_rewriting_the_same_spans_is_byte_identical(tmp_path: Path) -> None:
    doc = AltiumPcbDoc.from_file(_board(tmp_path / "plain.PcbDoc"))
    raw = doc._raw_streams["Board6/Data"]
    doc.set_via_spans(doc.via_spans())
    assert doc._raw_streams["Board6/Data"] == raw


def test_a_via_cannot_take_an_undeclared_span(tmp_path: Path) -> None:
    doc = AltiumPcbDoc.from_file(_board(tmp_path / "plain.PcbDoc"))
    with pytest.raises(ValueError, match="no via span"):
        doc.set_via_layer_span(doc.vias[0], "TOP", "MID2")


def test_boards_embedding_the_stack_xml_are_refused(tmp_path: Path) -> None:
    doc = AltiumPcbDoc.from_file(_board(tmp_path / "plain.PcbDoc"))
    body = doc._raw_streams["Board6/Data"][4:]
    body = body.replace(b"|RECORD=", b"|V9_STACKCUSTOMDATA=eJwDAAAAAAE=|RECORD=", 1)
    doc._raw_streams["Board6/Data"] = struct.pack("<I", len(body)) + body
    with pytest.raises(NotImplementedError, match="V9_STACKCUSTOMDATA"):
        doc.add_via_span("TOP", "MID1", via_span_type_raw=VIA_SPAN_TYPE_MICROVIA)
