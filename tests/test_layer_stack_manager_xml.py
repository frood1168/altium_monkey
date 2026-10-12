"""The Layer Stack Manager XML a PcbDoc embeds, read and written as AD does.

Board6 `V9_STACKCUSTOMDATA` = base64(zlib(XML)). From AD-saved boards (2026-10):

- AD stores '?' + cp1252: Windows' ANSI conversion turns the BOM into '?' and
  best-fits Greek mu (AD's "μVia a:b" span names) to 0xB5. A board with
  microvias used to read as 0 impedance profiles - the bytes were parsed as
  UTF-8 and the error swallowed.
- Board6 `DIELTYPE` <-> layer `TypeId`: 0 dielectric, 1 core, 2 prepreg,
  3 solder mask (a mask row may carry a dielectric name, "F.Mask").
- `<Stack Id>` / `Name` = `V9_SUBSTACK0_ID` / `_NAME`, not the master stack;
  lines' `StackId` and branches' `LayerStackId` point at it.
- `IsSymmetric="True"` while Stack Symmetry is on; left out when off.

Every case here builds the board it checks, so the suite needs no AD-saved file.
"""

from __future__ import annotations

import base64
import logging
import zlib
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from altium_monkey import (
    AltiumLayerStackDocument,
    AltiumPcbDoc,
    AltiumRigidCopperLayerSpec,
    AltiumRigidDielectricLayerSpec,
    PcbDocBuilder,
)
from altium_monkey import altium_layer_stack_document as lsd
from altium_monkey import altium_stackup, altium_stackupx
from altium_monkey.altium_layer_stack_document import (
    VIA_SPAN_TYPE_MICROVIA,
    VIA_SPAN_TYPE_THRU,
    AltiumDielectricLayerKind,
    AltiumImpedanceProfileSpec,
    AltiumTransmissionLineSpec,
)
from altium_monkey.altium_ole import AltiumOleFile
from altium_monkey.altium_stackupx import StackupXLayerType

NS = "{http://altium.com/ns/LayerStackManager}"

TYPE_NAMES = {
    StackupXLayerType.CORE.value: "core",
    StackupXLayerType.PREPREG.value: "prepreg",
    StackupXLayerType.SOLDER_MASK.value: "solder_mask",
    StackupXLayerType.DIELECTRIC.value: "dielectric",
}


def _board6(path: Path) -> dict[str, str]:
    text = AltiumOleFile(str(path)).openstream(["Board6", "Data"]).decode("latin-1")
    return {
        key: value.strip()
        for key, value in (item.split("=", 1) for item in text.split("|") if "=" in item)
    }


def _custom_data_bytes(record: dict[str, str]) -> bytes:
    return zlib.decompress(base64.b64decode(record["V9_STACKCUSTOMDATA"]))


def _xml(data: bytes) -> ET.Element:
    return ET.fromstring(lsd._stack_custom_data_xml_text(data))


def _stack(root: ET.Element) -> ET.Element:
    (stack,) = root.iter(NS + "Stack")
    return stack


def _lsm_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == lsd.__name__]


def test_custom_data_encoding_matches_ads_and_reads_older_boards() -> None:
    data = lsd._stack_custom_data_xml_bytes('<a n="μVia 1:2" m="Ω"/>')

    # BOM -> '?', Greek mu -> 0xB5 (Windows' best fit); no cp1252 byte -> a reference
    assert data == b'?<a n="\xb5Via 1:2" m="&#937;"/>'
    assert ET.fromstring(lsd._stack_custom_data_xml_text(data)).get("m") == "Ω"
    assert lsd._stack_custom_data_xml_text(data) == '<a n="\u00b5Via 1:2" m="&#937;"/>'
    # boards monkey wrote before: bare UTF-8 (and bare cp1252 if not valid UTF-8)
    assert lsd._stack_custom_data_xml_text('<a n="μVia"/>'.encode()) == '<a n="μVia"/>'
    assert lsd._stack_custom_data_xml_text(b'<a n="\xb5Via"/>') == '<a n="\u00b5Via"/>'


def test_unreadable_custom_data_is_reported_not_swallowed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = base64.b64encode(zlib.compress(b"?<StackupDocument Id=")).decode("ascii")

    with caplog.at_level(logging.WARNING):
        assert lsd._stack_custom_data_stackupx({"V9_STACKCUSTOMDATA": token}) is None

    (message,) = _lsm_warnings(caplog)
    assert "V9_STACKCUSTOMDATA" in message


@pytest.mark.parametrize(
    ("dielectric_type", "type_id"),
    [
        (0, StackupXLayerType.DIELECTRIC.value),
        (1, StackupXLayerType.CORE.value),
        (2, StackupXLayerType.PREPREG.value),
        (3, StackupXLayerType.SOLDER_MASK.value),
        (None, StackupXLayerType.DIELECTRIC.value),
    ],
)
def test_every_writer_types_dieltype_as_ad_does(
    dielectric_type: int | None, type_id: str
) -> None:
    row = SimpleNamespace(
        family="dielectric",
        dielectric_type=dielectric_type,
        stackupx_type_id="",
        is_stiffener=None,
        is_adhesive=None,
        legacy_layer_id=None,
    )

    assert altium_stackupx._type_id_for_layer(row) == type_id
    assert altium_stackup._type_id_for_layer(row) == "{" + type_id.upper() + "}"
    assert lsd._semantic_kvl_type_id_for_layer(row) == "{" + type_id.upper() + "}"


def test_layer_type_reads_back_as_ads_dieltype() -> None:
    assert altium_stackupx._dielectric_type_from_type_id(StackupXLayerType.DIELECTRIC) == 0
    assert altium_stackupx._dielectric_type_from_type_id(StackupXLayerType.CORE) == 1
    assert altium_stackupx._dielectric_type_from_type_id(StackupXLayerType.PREPREG) == 2
    assert int(AltiumDielectricLayerKind.CORE) == 1
    assert int(AltiumDielectricLayerKind.PREPREG) == 2


def _authored(top_prepreg_mils: float) -> AltiumLayerStackDocument:
    prepreg = int(AltiumDielectricLayerKind.PREPREG)
    document = AltiumLayerStackDocument.from_rigid_stack(
        name="LSM XML",
        copper_layers=[
            AltiumRigidCopperLayerSpec(f"L{index}", copper_thickness_mils=0.6)
            for index in range(1, 5)
        ],
        dielectrics_between=[
            AltiumRigidDielectricLayerSpec(
                "PP1", top_prepreg_mils, 3.5, "test", dielectric_type=prepreg
            ),
            AltiumRigidDielectricLayerSpec(
                "CORE", 20.0, 4.2, "test", dielectric_type=int(AltiumDielectricLayerKind.CORE)
            ),
            AltiumRigidDielectricLayerSpec("PP2", 4.0, 3.5, "test", dielectric_type=prepreg),
        ],
        impedance_profiles=[
            AltiumImpedanceProfileSpec(
                name="SE50",
                impedance="50ohm",
                tolerance="10%",
                transmission_lines=(
                    AltiumTransmissionLineSpec(
                        layer="L1",
                        bottom_reference="L2",
                        width="5mil",
                        tl_type_name="Surface Microstrip",
                        use_solder_mask=True,
                    ),
                ),
            )
        ],
    )
    document = document.with_via_span(
        "TOP", "BOTTOM", pair_index=0, via_span_type_raw=VIA_SPAN_TYPE_THRU
    )
    return document.with_via_span(
        "TOP", "MID1", pair_index=1, via_span_type_raw=VIA_SPAN_TYPE_MICROVIA
    )


@pytest.mark.parametrize(("top_prepreg_mils", "is_symmetric"), [(4.0, "True"), (3.0, None)])
def test_authored_board_embeds_the_xml_as_ad_does(
    tmp_path: Path,
    top_prepreg_mils: float,
    is_symmetric: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "lsm.PcbDoc"
    builder = PcbDocBuilder()
    builder.set_layer_stack_document(_authored(top_prepreg_mils))
    builder.set_outline_rectangle_mils(0.0, 0.0, 1000.0, 1000.0)
    builder.save(path)

    record = _board6(path)
    data = _custom_data_bytes(record)
    assert data.startswith(b"?<StackupDocument")
    assert b'AutoName="\xb5Via 1:2"' in data
    root = _xml(data)
    substack_id = record["V9_SUBSTACK0_ID"].strip("{}").lower()
    assert substack_id != record["V9_MASTERSTACK_ID"].strip("{}").lower()
    stack = _stack(root)
    assert (stack.get("Id"), stack.get("Name")) == (substack_id, record["V9_SUBSTACK0_NAME"])
    # symmetry claimed only for a stack that mirrors; AD leaves it out when off
    assert stack.get("IsSymmetric") == is_symmetric
    assert {line.get("StackId") for line in root.iter(NS + "TransmissionLine")} == {substack_id}
    types = {
        layer.get("Name"): TYPE_NAMES.get(layer.get("TypeId"))
        for layer in stack.iter(NS + "Layer")
    }
    assert [types["PP1"], types["CORE"], types["PP2"]] == ["prepreg", "core", "prepreg"]
    assert [name for name, kind in types.items() if kind == "solder_mask"] == [
        "Top Solder",
        "Bottom Solder",
    ]
    dieltypes = {
        record[f"V9_STACK_LAYER{index}_NAME"]: record.get(f"V9_STACK_LAYER{index}_DIELTYPE")
        for index in range(len(types) + 2)
        if f"V9_STACK_LAYER{index}_NAME" in record
    }
    assert [dieltypes["PP1"], dieltypes["CORE"], dieltypes["PP2"]] == ["2", "1", "2"]

    with caplog.at_level(logging.WARNING):
        back = AltiumLayerStackDocument.from_pcbdoc(AltiumPcbDoc.from_file(path))
    assert [profile.name for profile in back.impedance_profiles] == ["SE50"]
    assert not _lsm_warnings(caplog)
