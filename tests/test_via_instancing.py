"""ViaInstancing kept in step with Vias6 on save.

AD keeps a grouped second copy of the vias (ViaInstancing) and on load takes
each via's diameter, hole and span from its group's template, not from Vias6:
an imported HDI board's re-spanned vias all reopened TOP-BOTTOM because the
copy passed through stale. No repo asset carries the stream, so these tests
write one by hand from the layout AD uses, independently of the rebuild code.
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path

from altium_monkey import (
    AltiumLayerStackDocument,
    AltiumPcbDoc,
    AltiumRigidCopperLayerSpec,
    AltiumRigidDielectricLayerSpec,
    PcbDocBuilder,
)
from altium_monkey.altium_layer_stack_document import (
    VIA_SPAN_TYPE_MICROVIA,
    VIA_SPAN_TYPE_THRU,
)
from altium_monkey.altium_pcbdoc_via_instancing import (
    parse_via_instancing,
    split_via_records,
)

_TAIL = bytes(4) + bytes.fromhex("09000000000000000000000001")
_HASH = "SerializeLayerHash.Version=2,ClassName=CustomLayerHash,16777219=1,\x00".encode("utf-16-le")
_HASH_TAIL = _TAIL + struct.pack("<II", 1, len(_HASH)) + _HASH


def _ad_style_instancing(vias_data: bytes, tails: dict[int, bytes]) -> bytes:
    """One group (template = first via), one instance per via, as AD writes it."""
    vias = split_via_records(vias_data)
    out = b"\x03" + struct.pack("<I", len(vias[0])) + vias[0] + struct.pack("<I", len(vias))
    for index, via in enumerate(vias):
        body = via[0:21] + via[31:74]
        out += struct.pack("<II", index, len(body)) + body + tails.get(index, _TAIL + bytes(4))
    return out + bytes(4)


def _ad_saved_board(tmp_path: Path) -> Path:
    stack = AltiumLayerStackDocument.from_rigid_stack(
        name="Via instancing",
        copper_layers=[
            AltiumRigidCopperLayerSpec(f"L{index}", copper_thickness_mils=0.6)
            for index in range(1, 5)
        ],
        dielectrics_between=[
            AltiumRigidDielectricLayerSpec(
                f"D{index}", thickness_mils=4.0, dielectric_constant=3.5, material="test"
            )
            for index in range(1, 4)
        ],
    ).with_via_span("TOP", "BOTTOM", pair_index=0, via_span_type_raw=VIA_SPAN_TYPE_THRU)
    builder = PcbDocBuilder()
    builder.set_layer_stack_document(stack)
    builder.set_outline_rectangle_mils(0.0, 0.0, 1000.0, 1000.0)
    for x in (100.0, 200.0, 300.0):
        builder.add_via(position_mils=(x, 100.0), diameter_mils=10.0, hole_size_mils=5.0)
    plain = tmp_path / "plain.PcbDoc"
    builder.save(plain)

    doc = AltiumPcbDoc.from_file(plain)
    vias_data = doc._raw_streams["Vias6/Data"]
    doc._raw_streams["ViaInstancing/Header"] = struct.pack("<I", 1)
    doc._raw_streams["ViaInstancing/Data"] = _ad_style_instancing(vias_data, {1: _HASH_TAIL})
    path = tmp_path / "ad_saved.PcbDoc"
    doc.save(path)
    return path


def test_an_unedited_board_keeps_its_via_instancing_byte_for_byte(tmp_path: Path) -> None:
    source = AltiumPcbDoc.from_file(_ad_saved_board(tmp_path))
    source.save(tmp_path / "resaved.PcbDoc")
    saved = AltiumPcbDoc.from_file(tmp_path / "resaved.PcbDoc")
    for name in ("ViaInstancing/Header", "ViaInstancing/Data", "Vias6/Data"):
        assert saved._raw_streams[name] == source._raw_streams[name]


def test_a_new_via_span_reaches_the_template_ad_reads(tmp_path: Path) -> None:
    doc = AltiumPcbDoc.from_file(_ad_saved_board(tmp_path))
    doc.add_via_span("TOP", "MID1", via_span_type_raw=VIA_SPAN_TYPE_MICROVIA)
    doc.set_via_layer_span(doc.vias[1], "TOP", "MID1")
    doc.save(tmp_path / "micro.PcbDoc")

    saved = AltiumPcbDoc.from_file(tmp_path / "micro.PcbDoc")
    vias = split_via_records(saved._raw_streams["Vias6/Data"])
    groups = parse_via_instancing(saved._raw_streams["ViaInstancing/Data"])
    assert struct.unpack("<I", saved._raw_streams["ViaInstancing/Header"])[0] == len(groups) == 2
    # the thru group keeps vias 0 and 2; via 1 splits off behind it, its template on TOP-MID1
    assert [[index for index, _, _ in group.instances] for group in groups] == [[0, 2], [1]]
    assert [tuple(group.template[29:31]) for group in groups] == [(1, 32), (1, 2)]
    for group in groups:
        for index, body, _ in group.instances:
            assert body == vias[index][0:21] + vias[index][31:74]
            assert group.template[21:31] == vias[index][21:31]   # diameter, hole, span
    # the via's own tail (its layer hash) went with it
    assert groups[1].instances[0][2] == _HASH_TAIL


def test_an_unreadable_via_instancing_is_left_out_rather_than_left_stale(
    tmp_path: Path, caplog
) -> None:
    doc = AltiumPcbDoc.from_file(_ad_saved_board(tmp_path))
    doc._raw_streams["ViaInstancing/Data"] = b"\x03\x01\x00"      # not the known layout
    doc.add_via_span("TOP", "MID1", via_span_type_raw=VIA_SPAN_TYPE_MICROVIA)
    doc.set_via_layer_span(doc.vias[0], "TOP", "MID1")
    with caplog.at_level(logging.WARNING):
        doc.save(tmp_path / "dropped.PcbDoc")
    saved = AltiumPcbDoc.from_file(tmp_path / "dropped.PcbDoc")
    assert "ViaInstancing/Data" not in saved._raw_streams
    assert "ViaInstancing/Header" not in saved._raw_streams
    assert (saved.vias[0].layer_start, saved.vias[0].layer_end) == (1, 2)
    assert "ViaInstancing left out" in caplog.text
