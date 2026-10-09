"""
ViaInstancing: AD's grouped second copy of the vias, kept beside Vias6.

AD writes every via a second time, grouped under a template via, and on load
takes each via's diameter, hole and layer span from its group's template, not
from Vias6. A via edited in Vias6 alone therefore opens unchanged: on
an imported HDI board, 27,305 vias moved onto blind/buried spans in Vias6
all came back TOP-BOTTOM after an AD load and save.

Layout, read off 19 AD-saved boards (41 to 29,093 vias), every byte accounted
for:

- Header: u32 number of groups.
- Data: the groups, then u32 0.
- group: 0x03, u32 length, the template (the full Vias6 payload of the
  group's first via), u32 n, then n instances.
- instance: u32 Vias6 index, u32 64, via[0:21] + via[31:74] (position, net,
  plane and mask settings), then a tail: u32 0, 13 fixed bytes, u32 m and,
  when m > 0, a u32 byte length and a UTF-16 layer-hash string of m entries.
- A group's vias agree in every byte outside the instance body and the
  unique id / signature pair. AD sometimes keeps two groups that agree, and
  does not order groups by index, so a group cannot be derived from Vias6
  alone; the rebuild keeps AD's groups.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

VIA_INSTANCING_STREAM_NAMES = frozenset(
    {
        "ViaInstancing/Header",
        "ViaInstancing/Data",
    }
)

_RECORD_TYPE_VIA = 0x03
_INSTANCE_BODY_LENGTH = 64
_TAIL_FIXED = bytes(4) + bytes.fromhex("09000000000000000000000001")
_DEFAULT_TAIL = _TAIL_FIXED + bytes(4)        # a via AD has not instanced yet: no layer hash


@dataclass
class ViaInstancingGroup:
    """One template and its instances: (Vias6 index, instance body, tail)."""

    template: bytes
    instances: list[tuple[int, bytes, bytes]] = field(default_factory=list)


def split_via_records(data: bytes) -> list[bytes]:
    """Vias6/Data payloads, one per via (type byte 0x03, u32 length, payload)."""
    payloads: list[bytes] = []
    pos = 0
    while pos < len(data):
        if data[pos] != _RECORD_TYPE_VIA or pos + 5 > len(data):
            raise ValueError(f"Vias6/Data: no via record at offset {pos}")
        length = struct.unpack_from("<I", data, pos + 1)[0]
        if pos + 5 + length > len(data):
            raise ValueError(f"Vias6/Data: record at offset {pos} runs past the stream")
        payloads.append(data[pos + 5 : pos + 5 + length])
        pos += 5 + length
    return payloads


def parse_via_instancing(data: bytes) -> list[ViaInstancingGroup]:
    """Parse ViaInstancing/Data; ValueError on anything outside the known layout."""

    def u32(at: int) -> int:
        if at + 4 > len(data):
            raise ValueError(f"ViaInstancing/Data: truncated at offset {at}")
        return struct.unpack_from("<I", data, at)[0]

    groups: list[ViaInstancingGroup] = []
    pos = 0
    while pos < len(data) and data[pos] == _RECORD_TYPE_VIA:
        length = u32(pos + 1)
        group = ViaInstancingGroup(template=data[pos + 5 : pos + 5 + length])
        pos += 5 + length
        count = u32(pos)
        pos += 4
        for _ in range(count):
            index, body_length = u32(pos), u32(pos + 4)
            if body_length != _INSTANCE_BODY_LENGTH:
                raise ValueError(f"ViaInstancing/Data: instance body of {body_length} bytes at {pos}")
            body = data[pos + 8 : pos + 8 + body_length]
            pos += 8 + body_length
            tail_start = pos
            if data[pos : pos + len(_TAIL_FIXED)] != _TAIL_FIXED:
                raise ValueError(f"ViaInstancing/Data: unknown instance tail at offset {pos}")
            pos += len(_TAIL_FIXED)
            hash_entries = u32(pos)
            pos += 4
            if hash_entries:
                pos += 4 + u32(pos)
            group.instances.append((index, body, data[tail_start:pos]))
        groups.append(group)
    if data[pos:] != bytes(4):
        raise ValueError(f"ViaInstancing/Data: unexpected bytes after the groups at offset {pos}")
    return groups


def _unique_id_offset(payload: bytes) -> int | None:
    """Offset of the 16-byte unique id: after the stack table, its marker and the mask byte."""
    if len(payload) < 254:
        return None
    count, stride = struct.unpack_from("<II", payload, 246)
    offset = 254 + count * stride + 4 + 1
    return offset if offset + 32 <= len(payload) else None


def _instance_body(payload: bytes) -> bytes:
    return payload[0:21] + payload[31:74]


def _template_key(payload: bytes) -> bytes:
    """The bytes a group's vias share: all but the instance body and the unique id / signature."""
    offset = _unique_id_offset(payload)
    if offset is None:
        raise ValueError("via record too short to instance")
    return payload[21:31] + payload[74:offset] + payload[offset + 32 :]


def _old_to_new(old: list[bytes], new: list[bytes]) -> dict[int, int] | None:
    """Map old Vias6 indices to new ones by unique id, or by position when ids cannot tell vias apart."""

    def ids(payloads: list[bytes]) -> list[bytes] | None:
        found = []
        for payload in payloads:
            offset = _unique_id_offset(payload)
            if offset is None:
                return None
            found.append(payload[offset : offset + 16])
        usable = len(set(found)) == len(found) and bytes(16) not in found
        return found if usable else None

    old_ids, new_ids = ids(old), ids(new)
    if old_ids is not None and new_ids is not None:
        where = {uid: index for index, uid in enumerate(new_ids)}
        return {index: where[uid] for index, uid in enumerate(old_ids) if uid in where}
    if len(old) == len(new):
        return {index: index for index in range(len(old))}
    return None


def rebuild_via_instancing(
    old_data: bytes,
    old_vias_data: bytes,
    new_vias_data: bytes,
) -> tuple[bytes, int] | None:
    """
    ViaInstancing/Data for the new Vias6, and its group count.

    AD's groups, their order, each via's place and tail are kept; instance
    bodies and templates come from the new Vias6, and a group whose vias no
    longer agree is split (the split-off part follows its group). Vias AD
    never instanced join new groups at the end. Unchanged vias give the old
    bytes back. None when old and new vias cannot be matched up.
    """
    groups = parse_via_instancing(old_data)
    old = split_via_records(old_vias_data)
    new = split_via_records(new_vias_data)
    covered = sorted(index for group in groups for index, _, _ in group.instances)
    if covered != list(range(len(old))):
        raise ValueError("ViaInstancing does not cover each Vias6 record exactly once")
    if old == new:
        return old_data, len(groups)
    if not new:
        return None
    new_index = _old_to_new(old, new)
    if new_index is None:
        return None

    parts: list[list[tuple[int, bytes]]] = []
    placed: set[int] = set()
    for group in groups:
        split: dict[bytes, list[tuple[int, bytes]]] = {}
        for old_index, _body, tail in group.instances:
            index = new_index.get(old_index)
            if index is None:              # the via was deleted
                continue
            split.setdefault(_template_key(new[index]), []).append((index, tail))
            placed.add(index)
        parts.extend(split.values())
    unplaced: dict[bytes, list[tuple[int, bytes]]] = {}
    for index, payload in enumerate(new):
        if index not in placed:
            unplaced.setdefault(_template_key(payload), []).append((index, _DEFAULT_TAIL))
    parts.extend(unplaced.values())

    out = bytearray()
    for members in parts:
        template = new[members[0][0]]
        out += bytes([_RECORD_TYPE_VIA]) + struct.pack("<I", len(template)) + template
        out += struct.pack("<I", len(members))
        for index, tail in members:
            body = _instance_body(new[index])
            out += struct.pack("<II", index, len(body)) + body + tail
    out += bytes(4)
    return bytes(out), len(parts)
