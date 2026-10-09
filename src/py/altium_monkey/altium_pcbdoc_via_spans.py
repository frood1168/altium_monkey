"""
Via spans (drill pairs) and via layer spans on a PcbDoc loaded from disk.

The authoring builder can declare spans on a board it builds, but on a loaded
board it rewrites unrelated streams. These helpers touch only what a span
lives in:

- Board6/Data `LAYERPAIR<n>` rows (untyped for via spans, typed for
  back-drills) and `VIATYPE<n>` rows (one per via span, `DRILLPAIRTYPE=1` on
  a microvia), written by the same serializers as the builder, in place of
  the old rows. Every other Board6 key and its order are kept.
- A via's `layer_start` / `layer_end`, checked against the declared spans.

A board whose Board6 embeds the Layer Stack Manager XML
(`V9_STACKCUSTOMDATA`, AD-saved boards) also types its spans there; editing
that XML is not implemented, so such boards are refused rather than left
inconsistent.
"""

from __future__ import annotations

import re
import struct
from typing import TYPE_CHECKING, Sequence

from .altium_board import AltiumBoard
from .altium_pcb_layer_ref import PcbLayerRef

if TYPE_CHECKING:
    from .altium_layer_stack_document import AltiumLayerPair
    from .altium_pcbdoc import AltiumPcbDoc
    from .altium_record_pcb__via import AltiumPcbVia

BOARD6_DATA = "Board6/Data"
_PAIR_ROW = re.compile(r"^(?:LAYERPAIR|VIATYPE)\d+", re.IGNORECASE)
_TERMINATOR = "\x00\r\n"


def via_spans(doc: "AltiumPcbDoc") -> tuple["AltiumLayerPair", ...]:
    """The board's drill pairs, typed (`via_span_type_raw` 3 = microvia)."""
    from .altium_layer_stack_document import AltiumLayerStackDocument

    return tuple(AltiumLayerStackDocument.from_pcbdoc(doc).layer_pairs)


def set_via_spans(doc: "AltiumPcbDoc", pairs: Sequence["AltiumLayerPair"]) -> None:
    """Replace the board's drill pairs; only the LAYERPAIR/VIATYPE rows of Board6 change."""
    from .altium_layer_stack_document import (
        _add_authored_layer_pair_values,
        _add_authored_via_type_values,
    )
    from .altium_pcbdoc_builder import _parse_text_records

    raw = doc._raw_streams.get(BOARD6_DATA)
    if not raw:
        raise ValueError("board has no Board6/Data stream")
    length = struct.unpack("<I", raw[:4])[0]
    if length != len(raw) - 4:
        raise ValueError("Board6/Data holds more than one record; refusing to edit it")
    body = raw[4:].decode("latin-1")         # byte-for-byte round trip
    text = body.rstrip(_TERMINATOR)
    terminator = body[len(text):]
    if "|V9_STACKCUSTOMDATA=" in text:
        raise NotImplementedError(
            "Board6 embeds the Layer Stack Manager XML (V9_STACKCUSTOMDATA), which also types the "
            "via spans; editing it is not implemented"
        )
    indices = [pair.pair_index for pair in pairs]
    if len(set(indices)) != len(indices):
        raise ValueError(f"duplicate drill-pair indices: {indices}")

    rows: dict[str, str] = {}
    for pair in pairs:
        _add_authored_layer_pair_values(rows, pair)
    _add_authored_via_type_values(rows, list(pairs))

    # Board6 is one record of several '\r'-ended segments; the pair rows close a segment, so the last of them
    # carries the segment end. Keys already present keep their order (the builder and AD order them
    # differently), new ones follow, LAYERPAIR rows before VIATYPE rows; the segment end stays on the block's
    # last entry. An unchanged set of spans is therefore byte-identical.
    entries = text.split("|")
    kept: list[str] = []
    old: list[str] = []
    insert_at: int | None = None
    for entry in entries:
        if _PAIR_ROW.match(entry.split("=", 1)[0]):
            if insert_at is None:
                insert_at = len(kept)
            old.append(entry)
            continue
        kept.append(entry)
    if insert_at is None:
        raise ValueError("Board6 declares no drill pair (LAYERPAIR rows) to edit")
    segment_end = old[-1][len(old[-1].rstrip("\r\n")):]
    old_keys = [entry.split("=", 1)[0] for entry in old]
    ordered: list[str] = []
    for family in ("LAYERPAIR", "VIATYPE"):
        ordered += [key for key in old_keys if key.upper().startswith(family) and key in rows]
        ordered += [key for key in rows if key.upper().startswith(family) and key not in old_keys]
    block = [f"{key}={rows[key]}" for key in ordered]
    block[-1] += segment_end
    new_entries = kept[:insert_at] + block + kept[insert_at:]
    new_body = ("|".join(new_entries) + terminator).encode("latin-1")
    new_raw = struct.pack("<I", len(new_body)) + new_body
    doc._raw_streams[BOARD6_DATA] = new_raw
    records = _parse_text_records(new_raw)
    if records:
        doc.board = AltiumBoard.from_record(records[0])


def add_via_span(
    doc: "AltiumPcbDoc",
    low_layer: object,
    high_layer: object,
    *,
    via_span_type_raw: int | None = None,
    drill_guide: bool | None = False,
    drill_drawing: bool | None = False,
) -> "AltiumLayerPair":
    """Declare one more via span (drill pair) on the board and return it."""
    from .altium_layer_stack_document import AltiumLayerStackDocument

    stack = AltiumLayerStackDocument.from_pcbdoc(doc)
    before = {pair.pair_index for pair in stack.layer_pairs}
    stack = stack.with_via_span(
        low_layer,
        high_layer,
        via_span_type_raw=via_span_type_raw,
        drill_guide=drill_guide,
        drill_drawing=drill_drawing,
    )
    set_via_spans(doc, stack.layer_pairs)
    return next(pair for pair in stack.layer_pairs if pair.pair_index not in before)


def _legacy_signal_id(layer: object) -> int:
    ref = PcbLayerRef.from_legacy(layer) if isinstance(layer, int) else PcbLayerRef.parse(str(layer))
    if ref.legacy_layer_id is None:
        raise ValueError(f"{layer!r} is not a signal layer with a legacy id")
    return int(ref.legacy_layer_id)


def set_via_layer_span(
    doc: "AltiumPcbDoc",
    via: "AltiumPcbVia",
    low_layer: object,
    high_layer: object,
) -> None:
    """Give a via the span low..high; that span must be declared on the board (not as a back-drill)."""
    low, high = _legacy_signal_id(low_layer), _legacy_signal_id(high_layer)
    declared = {
        (_legacy_signal_id(pair.low_layer_token), _legacy_signal_id(pair.high_layer_token))
        for pair in via_spans(doc)
        if not pair.is_backdrill
    }
    if (low, high) not in declared:
        raise ValueError(
            f"no via span {low_layer}-{high_layer} declared on the board; declared: {sorted(declared)}"
        )
    via.layer_start = low
    via.layer_end = high
