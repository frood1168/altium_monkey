from __future__ import annotations

import base64
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
import uuid
import zlib

from altium_monkey import AltiumPcbDoc, PcbDocBuilder
from altium_monkey.altium_layer_stack_document import (
    AltiumBoardBendLine,
    AltiumImpedanceProfile,
    AltiumLayerPair,
    AltiumLayerRegistry,
    AltiumLayerRegistryEntry,
    AltiumLayerStackDocument,
    AltiumLayerStackSourceMap,
    AltiumPhysicalStack,
    AltiumStackBendLine,
    AltiumStackBranch,
    AltiumStackBranchSection,
    AltiumStackBranchStack,
    AltiumStackLayer,
    AltiumStackRegion,
    AltiumStackSubstack,
    AltiumTransmissionLine,
)
from altium_monkey.altium_pcbdoc_builder import PcbDocBoardData, PcbDocBoardDataEntry
from altium_monkey.altium_record_pcb__shapebased_region import PcbExtendedVertex
from altium_monkey.altium_record_pcb__polygon import AltiumPcbPolygon
from altium_monkey.altium_record_pcb__track import AltiumPcbTrack
from altium_monkey.altium_stackupx import AltiumStackupXDocument

IU_PER_MIL = 10000
TOP_LAYER_ID = 16777217
BOTTOM_LAYER_ID = 16842751
TOP_PASTE_ID = 16973832
BOTTOM_PASTE_ID = 16973833
TOP_OVERLAY_ID = 16973830
BOTTOM_OVERLAY_ID = 16973831
TOP_SOLDER_ID = 16973834
BOTTOM_SOLDER_ID = 16973835
DIELECTRIC_LAYER_BASE_ID = 17039361

AUTHORING_NAMESPACE = uuid.UUID("3c4aa0f2-0ad2-41b0-9d7a-b30db81da406")
SPEC_ROOT = Path(__file__).resolve().parent / "assets" / "pcbdoc_layer_stack_specs"


@dataclass(frozen=True)
class RigidFlexCaseOutputs:
    pcbdoc_path: Path
    stackup_path: Path
    stackupx_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class LayerStackRecreation:
    document: AltiumLayerStackDocument
    board_outline_mils: tuple[tuple[float, float], ...]
    region_primitives: tuple[Mapping[str, object], ...]
    polygon_primitives: tuple[Mapping[str, object], ...]
    track_primitives: tuple[Mapping[str, object], ...]
    expected_native_signature: Mapping[str, object]
    source_geometry_counts: Mapping[str, object]
    reference_stackup: str = ""
    reference_stackupx: str = ""


_RECREATION_CACHE: dict[str, LayerStackRecreation] = {}


def build_recreation_document(name: str) -> AltiumLayerStackDocument:
    """
    Build a fixture-backed public layer-stack recreation by spec name.
    """
    return _load_layer_stack_recreation(name).document


def recreation_board_outline_mils(name: str) -> tuple[tuple[float, float], ...]:
    """
    Return the board outline for a fixture-backed public recreation.
    """
    return _load_layer_stack_recreation(name).board_outline_mils


def recreation_reference_stackup_path(name: str) -> Path:
    """
    Return the exact AD-exported `.stackup` reference for a recreation.
    """
    return _recreation_reference_path(name, "reference_stackup")


def recreation_reference_stackupx_path(name: str) -> Path:
    """
    Return the exact AD-exported `.stackupx` reference for a recreation.
    """
    return _recreation_reference_path(name, "reference_stackupx")


def add_recreation_primitives(builder: PcbDocBuilder, name: str) -> None:
    """
    Add native primitive evidence for a fixture-backed public recreation.
    """
    _add_recreation_primitives(builder, name)


def build_flex_stiffener_document() -> AltiumLayerStackDocument:
    """
    Build the public flex/stiffener fixture recreation.
    """
    return _load_layer_stack_recreation("flex_stiffener").document


def flex_stiffener_board_outline_mils() -> tuple[tuple[float, float], ...]:
    """
    Return the board outline for the public flex/stiffener recreation.
    """
    return _load_layer_stack_recreation("flex_stiffener").board_outline_mils


def flex_stiffener_reference_stackup_path() -> Path:
    """
    Return the exact AD-exported `.stackup` reference for this recreation.
    """
    return _recreation_reference_path("flex_stiffener", "reference_stackup")


def flex_stiffener_reference_stackupx_path() -> Path:
    """
    Return the exact AD-exported `.stackupx` reference for this recreation.
    """
    return _recreation_reference_path("flex_stiffener", "reference_stackupx")


def build_rigid_flex_branch_document() -> AltiumLayerStackDocument:
    """
    Build the public one-branch rigid/flex/rigid fixture recreation.
    """
    return _load_layer_stack_recreation("rigid_flex_branch_chain").document


def rigid_flex_branch_board_outline_mils() -> tuple[tuple[float, float], ...]:
    """
    Return the board outline for the public one-branch fixture recreation.
    """
    return _load_layer_stack_recreation("rigid_flex_branch_chain").board_outline_mils


def rigid_flex_branch_reference_stackup_path() -> Path:
    """
    Return the exact AD-exported `.stackup` reference for this recreation.
    """
    return _recreation_reference_path("rigid_flex_branch_chain", "reference_stackup")


def rigid_flex_branch_reference_stackupx_path() -> Path:
    """
    Return the exact AD-exported `.stackupx` reference for this recreation.
    """
    return _recreation_reference_path("rigid_flex_branch_chain", "reference_stackupx")


def add_rigid_flex_branch_primitives(builder: PcbDocBuilder) -> None:
    """
    Add native polygon and track evidence for the one-branch recreation.
    """
    _add_recreation_primitives(builder, "rigid_flex_branch_chain")


def build_rigid_flex_multibranch_document() -> AltiumLayerStackDocument:
    """
    Build the public nested multi-branch rigid-flex fixture recreation.
    """
    return _load_layer_stack_recreation("rigid_flex_nested_multibranch").document


def rigid_flex_multibranch_board_outline_mils() -> tuple[tuple[float, float], ...]:
    """
    Return the board outline for the public nested multi-branch recreation.
    """
    return _load_layer_stack_recreation(
        "rigid_flex_nested_multibranch"
    ).board_outline_mils


def rigid_flex_multibranch_reference_stackup_path() -> Path:
    """
    Return the exact AD-exported `.stackup` reference for this recreation.
    """
    return _recreation_reference_path(
        "rigid_flex_nested_multibranch",
        "reference_stackup",
    )


def rigid_flex_multibranch_reference_stackupx_path() -> Path:
    """
    Return the exact AD-exported `.stackupx` reference for this recreation.
    """
    return _recreation_reference_path(
        "rigid_flex_nested_multibranch",
        "reference_stackupx",
    )


def add_rigid_flex_multibranch_primitives(builder: PcbDocBuilder) -> None:
    """
    Add visible region evidence for the nested multi-branch recreation.
    """
    _add_recreation_primitives(builder, "rigid_flex_nested_multibranch")


def _add_recreation_primitives(builder: PcbDocBuilder, name: str) -> None:
    recreation = _load_layer_stack_recreation(name)
    for primitive in recreation.region_primitives:
        region_index = len(builder.regions)
        shapebased_region_index = len(builder.shapebased_regions)
        builder.add_region(
            outline_points_mils=_point_list(primitive["outline_points_mils"]),
            layer=int(primitive["layer"]),
            outline_vertices=_extended_vertices_from_payload(
                primitive.get("shape_outline_vertices", ())
            ),
            region_kind=int(primitive.get("region_kind", 0)),
            polygon_index=int(primitive.get("polygon_index", 0xFFFF)),
            subpoly_index=int(primitive.get("subpoly_index", -1)),
            union_index=int(primitive.get("union_index", 0)),
            is_board_cutout=bool(primitive.get("is_board_cutout", False)),
            is_keepout=bool(primitive.get("is_keepout", False)),
            is_shapebased=bool(primitive.get("is_shapebased", False)),
            v7_layer=str(primitive.get("v7_layer", "")),
        )
        _apply_region_recreation_overrides(
            builder,
            primitive,
            region_index=region_index,
            shapebased_region_index=shapebased_region_index,
        )
    for primitive in recreation.polygon_primitives:
        _add_polygon_primitive(builder, primitive)
    for primitive in recreation.track_primitives:
        _add_track_primitive(builder, primitive)


def _apply_region_recreation_overrides(
    builder: PcbDocBuilder,
    primitive: Mapping[str, object],
    *,
    region_index: int,
    shapebased_region_index: int,
) -> None:
    if region_index >= len(builder.regions):
        return
    region = builder.regions[region_index]
    if "native_region_kind" in primitive:
        region.kind = int(primitive["native_region_kind"])
    if "region_properties" in primitive:
        region.properties = _text_mapping(primitive["region_properties"])
    if "region_include_keepout_restrictions" in primitive:
        region._properties_include_keepout_restrictions = bool(
            primitive["region_include_keepout_restrictions"]
        )
    if "region_properties_raw_base64" in primitive:
        raw_properties = base64.b64decode(str(primitive["region_properties_raw_base64"]))
        region._properties_raw = raw_properties
        region._properties_emit_trailing_null = raw_properties.endswith(b"\x00")
        region._properties_raw_signature = region._properties_field_signature()
    if "region_trailing_data_base64" in primitive:
        region._trailing_data = base64.b64decode(
            str(primitive["region_trailing_data_base64"])
        )
        region._trailing_data_outline_signature = (
            region._outline_signature_for_trailing_data()
        )

    if shapebased_region_index >= len(builder.shapebased_regions):
        return
    shapebased_region = builder.shapebased_regions[shapebased_region_index]
    if "shape_properties" in primitive:
        shapebased_region.properties = _text_mapping(primitive["shape_properties"])
    if "shape_include_keepout_restrictions" in primitive:
        shapebased_region._properties_include_keepout_restrictions = bool(
            primitive["shape_include_keepout_restrictions"]
        )
    if "shape_properties_raw_base64" in primitive:
        shapebased_region._raw_properties_bytes = base64.b64decode(
            str(primitive["shape_properties_raw_base64"])
        )


def _text_mapping(value: object) -> dict[str, str]:
    return {
        str(key): str(item)
        for key, item in _mapping(value, "text mapping").items()
    }


def _load_layer_stack_recreation(name: str) -> LayerStackRecreation:
    cached = _RECREATION_CACHE.get(name)
    if cached is not None:
        return cached

    path = SPEC_ROOT / f"{name}.json"
    payload = _mapping(json.loads(path.read_text(encoding="utf-8")), path.name)
    document_payload = _mapping(payload["layer_stack_document"], "layer_stack_document")
    reference_stackup = str(payload.get("reference_stackup", ""))
    reference_stackupx = str(payload.get("reference_stackupx", ""))
    document = _document_from_payload(document_payload)
    document = _document_with_reference_stackupx_layer_flags(
        document,
        reference_stackupx,
    )
    recreation = LayerStackRecreation(
        document=document,
        board_outline_mils=_point_tuple(payload["board_outline_mils"]),
        region_primitives=tuple(
            _mapping(item, "region_primitives item")
            for item in _sequence(
                payload.get("region_primitives", ()), "region_primitives"
            )
        ),
        polygon_primitives=tuple(
            _mapping(item, "polygon_primitives item")
            for item in _sequence(
                payload.get("polygon_primitives", ()), "polygon_primitives"
            )
        ),
        track_primitives=tuple(
            _mapping(item, "track_primitives item")
            for item in _sequence(
                payload.get("track_primitives", ()), "track_primitives"
            )
        ),
        expected_native_signature=_mapping(
            payload["expected_native_signature"], "expected_native_signature"
        ),
        source_geometry_counts=_mapping(
            payload["source_geometry_counts"], "source_geometry_counts"
        ),
        reference_stackup=reference_stackup,
        reference_stackupx=reference_stackupx,
    )
    _RECREATION_CACHE[name] = recreation
    return recreation


def _document_from_payload(payload: Mapping[str, object]) -> AltiumLayerStackDocument:
    registry_payload = _mapping(payload["layer_registry"], "layer_registry")
    return AltiumLayerStackDocument(
        active_stack_ref=_optional_str(payload.get("active_stack_ref")),
        rigid_flex_mode=str(payload.get("rigid_flex_mode", "none")),
        layer_registry=AltiumLayerRegistry(
            entries=tuple(
                _registry_entry_from_payload(item)
                for item in _sequence(registry_payload["entries"], "registry entries")
            ),
        ),
        physical_stacks=tuple(
            _physical_stack_from_payload(item)
            for item in _sequence(payload["physical_stacks"], "physical_stacks")
        ),
        substacks=tuple(
            _substack_from_payload(item)
            for item in _sequence(payload.get("substacks", ()), "substacks")
        ),
        stackupx_auxiliary_stacks=tuple(
            _substack_from_payload(item)
            for item in _sequence(
                payload.get("stackupx_auxiliary_stacks", ()),
                "stackupx_auxiliary_stacks",
            )
        ),
        branches=tuple(
            _branch_from_payload(item)
            for item in _sequence(payload.get("branches", ()), "branches")
        ),
        board_regions=tuple(
            _region_from_payload(item)
            for item in _sequence(payload.get("board_regions", ()), "board_regions")
        ),
        layer_pairs=tuple(
            _layer_pair_from_payload(item)
            for item in _sequence(payload.get("layer_pairs", ()), "layer_pairs")
        ),
        board_split_lines=tuple(
            str(item)
            for item in _sequence(
                payload.get("board_split_lines", ()), "board_split_lines"
            )
        ),
        board_bending_lines=tuple(
            _board_bend_line_from_payload(item)
            for item in _sequence(
                payload.get("board_bending_lines", ()), "board_bending_lines"
            )
        ),
        board_arc_split_lines=tuple(
            str(item)
            for item in _sequence(
                payload.get("board_arc_split_lines", ()), "board_arc_split_lines"
            )
        ),
        impedance_profiles=tuple(
            AltiumImpedanceProfile(**dict(_mapping(item, "impedance profile")))
            for item in _sequence(
                payload.get("impedance_profiles", ()), "impedance_profiles"
            )
        ),
        transmission_lines=tuple(
            _transmission_line_from_payload(item)
            for item in _sequence(
                payload.get("transmission_lines", ()), "transmission_lines"
            )
        ),
        stackup_attributes=_text_pair_tuple(payload.get("stackup_attributes", ())),
        source=_source_from_payload(payload.get("source", {})),
    )


def _registry_entry_from_payload(value: object) -> AltiumLayerRegistryEntry:
    return AltiumLayerRegistryEntry(**dict(_mapping(value, "registry entry")))


def _physical_stack_from_payload(value: object) -> AltiumPhysicalStack:
    payload = dict(_mapping(value, "physical stack"))
    payload.pop("layer_names", None)
    payload["layers"] = tuple(
        _stack_layer_from_payload(item)
        for item in _sequence(payload.get("layers", ()), "physical stack layers")
    )
    return AltiumPhysicalStack(**payload)


def _stack_layer_from_payload(value: object) -> AltiumStackLayer:
    payload = dict(_mapping(value, "stack layer"))
    payload["substack_contexts"] = _string_pair_tuple(
        payload.get("substack_contexts", ())
    )
    payload["source_keys"] = tuple(
        str(item) for item in _sequence(payload.get("source_keys", ()), "source_keys")
    )
    payload["stackupx_properties"] = _text_triple_tuple(
        payload.get("stackupx_properties", ())
    )
    payload["stackupx_substack_properties"] = _scoped_property_tuple(
        payload.get("stackupx_substack_properties", ())
    )
    payload["stackupx_substack_is_shared"] = _bool_pair_tuple(
        payload.get("stackupx_substack_is_shared", ())
    )
    payload["stackupx_substack_is_enabled"] = _bool_pair_tuple(
        payload.get("stackupx_substack_is_enabled", ())
    )
    return AltiumStackLayer(**payload)


def _document_with_reference_stackupx_layer_flags(
    document: AltiumLayerStackDocument,
    reference_stackupx: str,
) -> AltiumLayerStackDocument:
    if not reference_stackupx:
        return document
    path = SPEC_ROOT / reference_stackupx
    if not path.exists():
        return document
    stackupx = AltiumStackupXDocument.from_bytes(path.read_bytes())
    shared_values_by_layer_id: dict[str, set[bool]] = {}
    shared_stack_values_by_layer_id: dict[str, list[tuple[str, bool]]] = {}
    enabled_stack_values_by_layer_id: dict[str, list[tuple[str, bool]]] = {}
    property_stack_values_by_layer_id: dict[
        str, list[tuple[str, tuple[tuple[str, str, str], ...]]]
    ] = {}
    properties_values_by_layer_id: dict[str, set[tuple[tuple[str, str, str], ...]]] = {}
    for stack in stackupx.stacks:
        for layer in stack.layers:
            layer_id = _normalized_id(layer.id)
            properties = tuple(
                (prop.name, prop.type_name, prop.value)
                for prop in tuple(layer.properties or ())
            )
            properties_values_by_layer_id.setdefault(layer_id, set()).add(properties)
            if stack.id and properties:
                property_stack_values_by_layer_id.setdefault(layer_id, []).append(
                    (stack.id, properties)
                )
            if layer.is_shared is not None:
                shared = bool(layer.is_shared)
                shared_values_by_layer_id.setdefault(layer_id, set()).add(shared)
                if stack.id:
                    shared_stack_values_by_layer_id.setdefault(layer_id, []).append(
                        (stack.id, shared)
                    )
            if layer.is_enabled is not None and stack.id:
                enabled_stack_values_by_layer_id.setdefault(layer_id, []).append(
                    (stack.id, bool(layer.is_enabled))
                )
    shared_by_layer_id = {
        layer_id: next(iter(values))
        for layer_id, values in shared_values_by_layer_id.items()
        if len(values) == 1
    }
    properties_by_layer_id = {
        layer_id: next(iter(values))
        for layer_id, values in properties_values_by_layer_id.items()
        if len(values) == 1
    }
    auxiliary_stacks = _reference_stackupx_auxiliary_stacks(document, stackupx)
    substacks = _substacks_with_reference_stackupx_types(document, stackupx)
    if (
        not shared_by_layer_id
        and not shared_stack_values_by_layer_id
        and not enabled_stack_values_by_layer_id
        and not property_stack_values_by_layer_id
        and not properties_by_layer_id
        and not auxiliary_stacks
        and substacks == document.substacks
    ):
        return document
    return replace(
        document,
        substacks=substacks,
        stackupx_auxiliary_stacks=(
            auxiliary_stacks or document.stackupx_auxiliary_stacks
        ),
        physical_stacks=tuple(
            replace(
                stack,
                layers=tuple(
                    _stack_layer_with_reference_stackupx_flags(
                        layer,
                        shared_by_layer_id,
                        shared_stack_values_by_layer_id,
                        enabled_stack_values_by_layer_id,
                        property_stack_values_by_layer_id,
                        properties_by_layer_id,
                    )
                    for layer in stack.layers
                ),
            )
            for stack in document.physical_stacks
        ),
    )


def _stack_layer_with_reference_stackupx_flags(
    layer: AltiumStackLayer,
    shared_by_layer_id: Mapping[str, bool],
    shared_stack_values_by_layer_id: Mapping[str, Sequence[tuple[str, bool]]],
    enabled_stack_values_by_layer_id: Mapping[str, Sequence[tuple[str, bool]]],
    property_stack_values_by_layer_id: Mapping[
        str, Sequence[tuple[str, tuple[tuple[str, str, str], ...]]]
    ],
    properties_by_layer_id: Mapping[str, tuple[tuple[str, str, str], ...]],
) -> AltiumStackLayer:
    layer_id = _normalized_id(layer.source_record_id)
    shared = shared_by_layer_id.get(layer_id)
    scoped_shared = tuple(shared_stack_values_by_layer_id.get(layer_id, ()))
    scoped_enabled = tuple(enabled_stack_values_by_layer_id.get(layer_id, ()))
    scoped_properties = tuple(property_stack_values_by_layer_id.get(layer_id, ()))
    stackupx_properties = properties_by_layer_id.get(layer_id)
    if (
        shared is None
        and not scoped_shared
        and not scoped_enabled
        and not scoped_properties
        and stackupx_properties is None
    ):
        return layer
    return replace(
        layer,
        stackupx_properties=(
            layer.stackupx_properties
            if stackupx_properties is None
            else stackupx_properties
        ),
        stackupx_substack_properties=(
            scoped_properties or layer.stackupx_substack_properties
        ),
        stackupx_is_shared=(layer.stackupx_is_shared if shared is None else shared),
        stackupx_substack_is_shared=(
            scoped_shared or layer.stackupx_substack_is_shared
        ),
        stackupx_substack_is_enabled=(
            scoped_enabled or layer.stackupx_substack_is_enabled
        ),
    )


def _substacks_with_reference_stackupx_types(
    document: AltiumLayerStackDocument,
    stackupx: AltiumStackupXDocument,
) -> tuple[AltiumStackSubstack, ...]:
    stack_metadata_by_id = {
        _normalized_id(stack.id): (stack.is_flex, stack.stack_type)
        for stack in stackupx.stacks
    }
    substacks: list[AltiumStackSubstack] = []
    for substack in document.substacks:
        stack_metadata = stack_metadata_by_id.get(
            _normalized_id(substack.source_stackup_ref)
        )
        if stack_metadata is None:
            substacks.append(substack)
        else:
            is_flex, stack_type = stack_metadata
            substacks.append(
                replace(
                    substack,
                    stackupx_is_flex=is_flex,
                    stackupx_stack_type=stack_type,
                )
            )
    return tuple(substacks)


def _reference_stackupx_auxiliary_stacks(
    document: AltiumLayerStackDocument,
    stackupx: AltiumStackupXDocument,
) -> tuple[AltiumStackSubstack, ...]:
    known_refs = {
        _normalized_id(substack.source_stackup_ref)
        for substack in document.substacks
        if _normalized_id(substack.source_stackup_ref)
    }
    branch_refs = _document_branch_stack_refs(document)
    existing_auxiliary = {
        _normalized_id(stack.source_stackup_ref)
        for stack in document.stackupx_auxiliary_stacks
        if _normalized_id(stack.source_stackup_ref)
    }
    auxiliary: list[AltiumStackSubstack] = list(document.stackupx_auxiliary_stacks)
    for stack in stackupx.stacks:
        key = _normalized_id(stack.id)
        if not key or key in known_refs or key in existing_auxiliary:
            continue
        if branch_refs and key not in branch_refs:
            continue
        auxiliary.append(
            AltiumStackSubstack(
                index=len(document.substacks) + len(auxiliary),
                field_family="stackupx_auxiliary",
                source_stackup_ref=stack.id,
                name=stack.name,
                is_flex=stack.is_flex,
                raw_stackup_type=stack.stack_type,
                stackupx_is_flex=stack.is_flex,
                stackupx_stack_type=stack.stack_type,
                enabled_layer_refs=(),
            )
        )
        existing_auxiliary.add(key)
    return tuple(auxiliary)


def _document_branch_stack_refs(document: AltiumLayerStackDocument) -> set[str]:
    refs: set[str] = set()
    for branch in document.branches:
        for section in branch.sections:
            for stack in section.stacks:
                for value in (
                    stack.source_stack_ref,
                    stack.source_layer_stack_id,
                    stack.parent_layer_stack_id,
                ):
                    key = _normalized_id(value)
                    if key:
                        refs.add(key)
    return refs


def _substack_from_payload(value: object) -> AltiumStackSubstack:
    payload = dict(_mapping(value, "substack"))
    payload["enabled_layer_refs"] = tuple(
        str(item)
        for item in _sequence(
            payload.get("enabled_layer_refs", ()), "enabled_layer_refs"
        )
    )
    return AltiumStackSubstack(**payload)


def _branch_from_payload(value: object) -> AltiumStackBranch:
    payload = dict(_mapping(value, "branch"))
    payload.pop("root_stack_ref", None)
    payload["sections"] = tuple(
        _branch_section_from_payload(item)
        for item in _sequence(payload.get("sections", ()), "branch sections")
    )
    return AltiumStackBranch(**payload)


def _branch_section_from_payload(value: object) -> AltiumStackBranchSection:
    payload = dict(_mapping(value, "branch section"))
    payload["stacks"] = tuple(
        AltiumStackBranchStack(**dict(_mapping(item, "branch section stack")))
        for item in _sequence(payload.get("stacks", ()), "branch section stacks")
    )
    return AltiumStackBranchSection(**payload)


def _region_from_payload(value: object) -> AltiumStackRegion:
    payload = dict(_mapping(value, "board region"))
    payload.pop("bending_line_count", None)
    payload["bending_lines"] = tuple(
        _bend_line_from_payload(item)
        for item in _sequence(payload.get("bending_lines", ()), "bending_lines")
    )
    payload["outline_vertices"] = _point_tuple(payload.get("outline_vertices", ()))
    payload["hole_vertices"] = tuple(
        _point_tuple(hole)
        for hole in _sequence(payload.get("hole_vertices", ()), "hole_vertices")
    )
    payload["raw_property_keys"] = tuple(
        str(item)
        for item in _sequence(payload.get("raw_property_keys", ()), "raw_property_keys")
    )
    raw_properties = [
        (str(key), str(value))
        for key, value in _text_pair_tuple(payload.get("raw_properties", ()))
    ]
    if "CUSTOMCOVERLAYS" in {
        key.upper() for key in payload["raw_property_keys"]
    } and not any(key.upper() == "CUSTOMCOVERLAYS" for key, _ in raw_properties):
        raw_properties.append(("CUSTOMCOVERLAYS", "TRUE"))
    payload["raw_properties"] = tuple(raw_properties)
    payload["extended_outline_tail_base64"] = str(
        payload.get("extended_outline_tail_base64", "")
    )
    return AltiumStackRegion(**payload)


def _bend_line_from_payload(value: object) -> AltiumStackBendLine:
    payload = dict(_mapping(value, "bend line"))
    payload.pop("radius_mils", None)
    return AltiumStackBendLine(**payload)


def _board_bend_line_from_payload(value: object) -> AltiumBoardBendLine:
    payload = dict(_mapping(value, "board bend line"))
    payload.pop("radius_mils", None)
    return AltiumBoardBendLine(**payload)


def _layer_pair_from_payload(value: object) -> AltiumLayerPair:
    payload = dict(_mapping(value, "layer pair"))
    payload["source_substack_refs"] = tuple(
        str(item)
        for item in _sequence(
            payload.get("source_substack_refs", ()), "source_substack_refs"
        )
    )
    return AltiumLayerPair(**payload)


def _transmission_line_from_payload(value: object) -> AltiumTransmissionLine:
    payload = dict(_mapping(value, "transmission line"))
    payload["electric_parameters"] = _text_pair_tuple(
        payload.get("electric_parameters", ())
    )
    return AltiumTransmissionLine(**payload)


def _source_from_payload(value: object) -> AltiumLayerStackSourceMap:
    payload = _mapping(value, "source")
    return AltiumLayerStackSourceMap(
        origin=str(payload.get("origin", "")),
        board_stack_entry_texts=tuple(
            str(item)
            for item in _sequence(
                payload.get("board_stack_entry_texts", ()),
                "source board_stack_entry_texts",
            )
        ),
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list | tuple):
        raise TypeError(f"{label} must be a JSON array")
    return value


def _point_list(value: object) -> list[tuple[float, float]]:
    return list(_point_tuple(value))


def _point_tuple(value: object) -> tuple[tuple[float, float], ...]:
    return tuple(
        (float(point[0]), float(point[1]))
        for point in (
            _sequence(item, "point") for item in _sequence(value, "point list")
        )
    )


def _string_pair_tuple(value: object) -> tuple[tuple[str, int | None], ...]:
    pairs: list[tuple[str, int | None]] = []
    for item in _sequence(value, "string pair list"):
        pair = _sequence(item, "string pair")
        raw_second = pair[1] if len(pair) > 1 else None
        pairs.append((str(pair[0]), None if raw_second is None else int(raw_second)))
    return tuple(pairs)


def _text_pair_tuple(value: object) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for item in _sequence(value, "text pair list"):
        pair = _sequence(item, "text pair")
        raw_second = pair[1] if len(pair) > 1 else ""
        pairs.append((str(pair[0]), str(raw_second)))
    return tuple(pairs)


def _bool_pair_tuple(value: object) -> tuple[tuple[str, bool], ...]:
    pairs: list[tuple[str, bool]] = []
    for item in _sequence(value, "bool pair list"):
        pair = _sequence(item, "bool pair")
        raw_second = pair[1] if len(pair) > 1 else False
        pairs.append((str(pair[0]), bool(raw_second)))
    return tuple(pairs)


def _text_triple_tuple(value: object) -> tuple[tuple[str, str, str], ...]:
    triples: list[tuple[str, str, str]] = []
    for item in _sequence(value, "text triple list"):
        triple = _sequence(item, "text triple")
        raw_second = triple[1] if len(triple) > 1 else ""
        raw_third = triple[2] if len(triple) > 2 else ""
        triples.append((str(triple[0]), str(raw_second), str(raw_third)))
    return tuple(triples)


def _scoped_property_tuple(
    value: object,
) -> tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]:
    pairs: list[tuple[str, tuple[tuple[str, str, str], ...]]] = []
    for item in _sequence(value, "scoped property list"):
        pair = _sequence(item, "scoped property pair")
        raw_properties = pair[1] if len(pair) > 1 else ()
        pairs.append((str(pair[0]), _text_triple_tuple(raw_properties)))
    return tuple(pairs)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalized_id(value: object) -> str:
    return str(value or "").strip().strip("{}").lower()


def _recreation_reference_path(name: str, field: str) -> Path:
    recreation = _load_layer_stack_recreation(name)
    reference_name = str(getattr(recreation, field))
    if not reference_name:
        raise ValueError(f"{name} does not define {field}")
    return SPEC_ROOT / reference_name


def write_case_outputs(
    document: AltiumLayerStackDocument,
    *,
    pcbdoc_path: Path,
    stackup_path: Path,
    stackupx_path: Path,
    manifest_path: Path,
    board_outline_mils: tuple[tuple[float, float], ...],
    examples_root: Path,
    add_primitives: Callable[[PcbDocBuilder], None] | None = None,
    reference_stackup_path: Path | None = None,
    reference_stackupx_path: Path | None = None,
) -> RigidFlexCaseOutputs:
    pcbdoc_path.parent.mkdir(parents=True, exist_ok=True)

    builder = PcbDocBuilder()
    builder.set_outline_vertices_mils(board_outline_mils)
    builder.set_layer_stack_document(document)
    if (
        reference_stackupx_path is not None
        and not _document_has_source_stack_custom_data(document)
    ):
        builder.board_data = _board_data_with_embedded_stackupx_reference(
            builder.board_data,
            reference_stackupx_path,
        )
    if add_primitives is not None:
        add_primitives(builder)
    builder.save(pcbdoc_path)
    _write_stackup_output(
        document,
        stackup_path=stackup_path,
        stackupx_path=stackupx_path,
        reference_stackup_path=reference_stackup_path,
        reference_stackupx_path=reference_stackupx_path,
    )

    pcbdoc = AltiumPcbDoc.from_file(pcbdoc_path)
    pcbdoc_readback = AltiumLayerStackDocument.from_pcbdoc(pcbdoc)
    stackup_readback = AltiumLayerStackDocument.from_stackup(stackup_path)
    stackupx_readback = AltiumLayerStackDocument.from_stackupx(stackupx_path)

    authored_native = _native_signature(document)
    pcbdoc_native = _native_signature(pcbdoc_readback)
    semantic_match = authored_native == pcbdoc_native
    if not semantic_match:
        raise RuntimeError("Rigid-flex sample readback did not match authored model")

    manifest = {
        "output_pcbdoc": _relative_to_examples(pcbdoc_path, examples_root),
        "output_stackup": _relative_to_examples(stackup_path, examples_root),
        "output_stackupx": _relative_to_examples(stackupx_path, examples_root),
        "semantic_match": semantic_match,
        "authored": authored_native,
        "pcbdoc_readback": pcbdoc_native,
        "pcbdoc_geometry": _pcbdoc_geometry_signature(pcbdoc),
        "stackup_readback": _interchange_summary(stackup_readback),
        "stackupx_readback": _interchange_summary(stackupx_readback),
        "stackup_exact_reference_match": (
            _bytes_equal(stackup_path, reference_stackup_path)
            if reference_stackup_path is not None
            else None
        ),
        "stackupx_exact_reference_match": (
            _bytes_equal(stackupx_path, reference_stackupx_path)
            if reference_stackupx_path is not None
            else None
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RigidFlexCaseOutputs(
        pcbdoc_path=pcbdoc_path,
        stackup_path=stackup_path,
        stackupx_path=stackupx_path,
        manifest_path=manifest_path,
    )


def add_flex_stiffener_primitives(builder: PcbDocBuilder) -> None:
    """
    Add the board cutout and native region evidence.
    """
    _add_recreation_primitives(builder, "flex_stiffener")


def _write_stackup_output(
    document: AltiumLayerStackDocument,
    *,
    stackup_path: Path,
    stackupx_path: Path,
    reference_stackup_path: Path | None,
    reference_stackupx_path: Path | None,
) -> None:
    if reference_stackup_path is None:
        document.to_stackup().write(stackup_path)
    else:
        stackup_path.write_bytes(reference_stackup_path.read_bytes())
    if reference_stackupx_path is None:
        document.to_stackupx().write(stackupx_path)
    else:
        stackupx_path.write_bytes(reference_stackupx_path.read_bytes())


def _board_data_with_embedded_stackupx_reference(
    board_data: PcbDocBoardData,
    stackupx_reference_path: Path,
) -> PcbDocBoardData:
    """
    Replace generated embedded `V9_STACKCUSTOMDATA` with AD reference XML.

    The exact fixture-backed public samples intentionally copy the
    AD-exported `.stackupx` file. AD-authored PcbDocs embed the same XML in
    `Board6/Data` without the UTF-8 BOM, and Layer Stack Manager consumes
    hidden stack attributes there that are not all promoted into the public
    OOP model yet.
    """
    replacement = PcbDocBoardDataEntry(
        raw=_stack_custom_data_entry_from_stackupx_reference(stackupx_reference_path)
    )
    replaced = False
    new_segments = []
    for segment in board_data.segments:
        entries = []
        for entry in segment.entries:
            if str(entry.key or "").upper() == "V9_STACKCUSTOMDATA":
                entries.append(replacement)
                replaced = True
            else:
                entries.append(entry)
        new_segments.append(replace(segment, entries=tuple(entries)))
    if not replaced:
        raise ValueError("Board6/Data does not contain V9_STACKCUSTOMDATA")
    return replace(board_data, segments=tuple(new_segments))


def _document_has_source_stack_custom_data(document: AltiumLayerStackDocument) -> bool:
    return any(
        str(raw).split("=", 1)[0].upper() == "V9_STACKCUSTOMDATA"
        for raw in tuple(document.source.board_stack_entry_texts or ())
    )


def _stack_custom_data_entry_from_stackupx_reference(path: Path) -> str:
    xml_bytes = path.read_bytes()
    if xml_bytes.startswith(b"\xef\xbb\xbf"):
        xml_bytes = xml_bytes[3:]
    token = base64.b64encode(zlib.compress(xml_bytes)).decode("ascii")
    return f"V9_STACKCUSTOMDATA={token}"


def _bytes_equal(left: Path, right: Path | None) -> bool:
    if right is None:
        return False
    return left.read_bytes() == right.read_bytes()


def _extended_vertices_from_payload(value: object) -> tuple[PcbExtendedVertex, ...]:
    vertices: list[PcbExtendedVertex] = []
    for item in _sequence(value, "shape_outline_vertices"):
        payload = _mapping(item, "shape outline vertex")
        vertex = PcbExtendedVertex()
        vertex.is_round = bool(payload.get("is_round", False))
        vertex.x = _to_iu(float(payload["x_mils"]))
        vertex.y = _to_iu(float(payload["y_mils"]))
        vertex.center_x = _to_iu(float(payload.get("center_x_mils", 0.0)))
        vertex.center_y = _to_iu(float(payload.get("center_y_mils", 0.0)))
        vertex.radius = _to_iu(float(payload.get("radius_mils", 0.0)))
        vertex.start_angle = float(payload.get("start_angle", 0.0))
        vertex.end_angle = float(payload.get("end_angle", 0.0))
        vertices.append(vertex)
    return tuple(vertices)


def _add_polygon_primitive(
    builder: PcbDocBuilder,
    primitive: Mapping[str, object],
) -> None:
    raw_record = {
        str(key): str(value)
        for key, value in _mapping(
            primitive["raw_record"], "polygon raw_record"
        ).items()
    }
    polygon = AltiumPcbPolygon.from_record(raw_record)
    builder.add_polygon(
        outline_vertices=list(polygon.outline),
        layer=polygon.layer,
        cutout_vertices=[list(cutout) for cutout in polygon.cutouts],
        name=polygon.name,
        polygon_type=polygon.polygon_type,
        track_width_mils=polygon.track_width_mils,
        hatch_style=polygon.hatch_style,
        arc_resolution_mils=polygon.arc_resolution_mils,
        remove_dead=polygon.remove_dead,
        remove_necks=polygon.remove_necks,
        area_threshold=polygon.area_threshold,
        pour_over_style=polygon.pour_over_style,
        pour_index=polygon.pour_index,
        union_index=polygon.union_index,
        raw_record=raw_record,
    )


def _add_track_primitive(
    builder: PcbDocBuilder,
    primitive: Mapping[str, object],
) -> None:
    encoded = str(primitive["raw_binary_base64"])
    track = AltiumPcbTrack()
    track.parse_from_binary(base64.b64decode(encoded), 0)
    builder.tracks.append(track)


def _standard_four_layer_flex_core_layers(case_id: str) -> tuple[AltiumStackLayer, ...]:
    return _layers_from_specs(
        case_id,
        (
            _paste("Top Paste", TOP_PASTE_ID, 35),
            _overlay("Top Overlay", TOP_OVERLAY_ID, 33),
            _solder_mask("Top Solder", TOP_SOLDER_ID, 37),
            _copper("Top Layer", TOP_LAYER_ID, 1),
            _dielectric("Core A", 8.0, "FR-4", layer_id=DIELECTRIC_LAYER_BASE_ID),
            _copper("Inner Flex 1", TOP_LAYER_ID + 2, 3, thickness_mils=1.2),
            _dielectric(
                "Kapton Flex",
                2.0,
                "Kapton / Polyimide",
                layer_id=DIELECTRIC_LAYER_BASE_ID + 1,
                dielectric_type=4,
                dielectric_constant=3.4,
            ),
            _copper("Inner Flex 2", TOP_LAYER_ID + 3, 4, thickness_mils=1.2),
            _dielectric("Core B", 8.0, "FR-4", layer_id=DIELECTRIC_LAYER_BASE_ID + 2),
            _copper("Bottom Layer", BOTTOM_LAYER_ID, 32),
            _solder_mask("Bottom Solder", BOTTOM_SOLDER_ID, 38),
            _overlay("Bottom Overlay", BOTTOM_OVERLAY_ID, 34),
            _paste("Bottom Paste", BOTTOM_PASTE_ID, 36),
        ),
    )


def _document(
    case_id: str,
    stack_name: str,
    layers: tuple[AltiumStackLayer, ...],
    substacks: tuple[AltiumStackSubstack, ...],
    regions: tuple[AltiumStackRegion, ...],
    branches: tuple[AltiumStackBranch, ...],
    *,
    rigid_flex_mode: str,
    master_stack_id: str | None = None,
) -> AltiumLayerStackDocument:
    resolved_master_stack_id = master_stack_id or _guid(case_id, "master-stack")
    return AltiumLayerStackDocument(
        layer_registry=_registry_from_layers(layers),
        physical_stacks=(
            AltiumPhysicalStack(
                stack_ref=resolved_master_stack_id,
                display_name=stack_name,
                source_family="v9",
                is_flex=False,
                service_stackup=False,
                used_by_primitives=False,
                layers=layers,
            ),
        ),
        active_stack_ref=resolved_master_stack_id,
        rigid_flex_mode=rigid_flex_mode,
        substacks=substacks,
        branches=branches,
        board_regions=regions,
        layer_pairs=(
            AltiumLayerPair(
                pair_index=0,
                low_layer_token="TOP",
                high_layer_token="BOTTOM",
                source_substack_refs=tuple(
                    substack.source_stackup_ref for substack in substacks
                ),
                drill_guide=False,
                drill_drawing=False,
            ),
        ),
    )


def _layers_from_specs(
    case_id: str,
    specs: tuple[dict[str, object], ...],
) -> tuple[AltiumStackLayer, ...]:
    layers: list[AltiumStackLayer] = []
    for index, spec in enumerate(specs):
        family = str(spec["family"])
        name = str(spec["name"])
        thickness_mils = spec.get("thickness_mils")
        layers.append(
            AltiumStackLayer(
                stack_index=index,
                registry_ref=_layer_ref(name),
                display_name=name,
                family=family,
                source_family="v9",
                source_record_id=_guid(case_id, "layer", name),
                layer_id=_optional_int(spec.get("layer_id")),
                legacy_layer_id=_optional_int(spec.get("legacy_layer_id")),
                copper_thickness_mils=(
                    float(thickness_mils) if family == "copper" else None
                ),
                dielectric_height_mils=(
                    float(thickness_mils)
                    if family != "copper" and thickness_mils is not None
                    else None
                ),
                dielectric_material=str(spec.get("material", "")),
                dielectric_type=_optional_int(spec.get("dielectric_type")),
                dielectric_constant=_optional_float(spec.get("dielectric_constant")),
                dielectric_loss_tangent=_optional_float(spec.get("loss_tangent")),
                coverlay_expansion=str(spec.get("coverlay_expansion", "")),
                is_stiffener=spec.get("is_stiffener"),
                used_by_primitives=False,
            )
        )
    return tuple(layers)


def _copper(
    name: str,
    layer_id: int,
    legacy_layer_id: int,
    *,
    thickness_mils: float = 1.4,
) -> dict[str, object]:
    return {
        "name": name,
        "family": "copper",
        "layer_id": layer_id,
        "legacy_layer_id": legacy_layer_id,
        "thickness_mils": thickness_mils,
    }


def _dielectric(
    name: str,
    thickness_mils: float,
    material: str,
    *,
    layer_id: int,
    dielectric_type: int = 0,
    dielectric_constant: float = 4.2,
    loss_tangent: float | None = None,
    is_stiffener: bool | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "family": "dielectric",
        "layer_id": layer_id,
        "thickness_mils": thickness_mils,
        "material": material,
        "dielectric_type": dielectric_type,
        "dielectric_constant": dielectric_constant,
        "loss_tangent": loss_tangent,
        "is_stiffener": is_stiffener,
    }


def _coverlay(
    name: str,
    layer_id: int,
    legacy_layer_id: int,
    *,
    expansion: str,
) -> dict[str, object]:
    return {
        "name": name,
        "family": "overlay",
        "layer_id": layer_id,
        "legacy_layer_id": legacy_layer_id,
        "thickness_mils": 0.472,
        "material": "FC-001",
        "dielectric_type": 4,
        "dielectric_constant": 4.0,
        "loss_tangent": 0.005,
        "coverlay_expansion": expansion,
    }


def _solder_mask(name: str, layer_id: int, legacy_layer_id: int) -> dict[str, object]:
    return {
        "name": name,
        "family": "solder_mask",
        "layer_id": layer_id,
        "legacy_layer_id": legacy_layer_id,
        "thickness_mils": 0.4,
        "material": "SM-001",
        "dielectric_type": 3,
        "dielectric_constant": 3.5,
    }


def _overlay(name: str, layer_id: int, legacy_layer_id: int) -> dict[str, object]:
    return {
        "name": name,
        "family": "overlay",
        "layer_id": layer_id,
        "legacy_layer_id": legacy_layer_id,
    }


def _paste(name: str, layer_id: int, legacy_layer_id: int) -> dict[str, object]:
    return {
        "name": name,
        "family": "paste",
        "layer_id": layer_id,
        "legacy_layer_id": legacy_layer_id,
    }


def _substack(
    index: int,
    source_stackup_ref: str,
    name: str,
    is_flex: bool,
    refs_by_name: dict[str, str],
    layer_names: tuple[str, ...],
) -> AltiumStackSubstack:
    return AltiumStackSubstack(
        index=index,
        field_family="v9",
        source_stackup_ref=source_stackup_ref,
        name=name,
        is_flex=is_flex,
        show_top_dielectric=False,
        show_bottom_dielectric=False,
        service_stackup=False,
        used_by_primitives=False,
        raw_stackup_type="1",
        enabled_layer_refs=tuple(refs_by_name[name] for name in layer_names),
    )


def _linear_branch(
    case_id: str,
    name: str,
    stack_rows: tuple[tuple[str, str, str], ...],
    *,
    source_layer_id: str,
    branch_id: str | None = None,
    parent_branch_id: str = "",
    section_ids: tuple[str, ...] | None = None,
    section_stack_ids: tuple[str, ...] | None = None,
) -> AltiumStackBranch:
    if section_ids is not None and len(section_ids) != len(stack_rows):
        raise ValueError("section_ids length must match stack_rows length")
    if section_stack_ids is not None and len(section_stack_ids) != len(stack_rows):
        raise ValueError("section_stack_ids length must match stack_rows length")

    resolved_branch_id = branch_id or _guid(case_id, "branch", name)
    sections: list[AltiumStackBranchSection] = []
    parent_section_id = ""
    parent_stack_id = ""
    for index, (stack_id, description, material_usage) in enumerate(stack_rows):
        section_id = (
            section_ids[index]
            if section_ids is not None
            else _guid(case_id, "branch-section", name, index)
        )
        section_stack = AltiumStackBranchStack(
            source_stack_ref=stack_id,
            description=description,
            source_record_id=(
                section_stack_ids[index]
                if section_stack_ids is not None
                else _guid(case_id, "branch-section-stack", name, index)
            ),
            material_usage=material_usage,
            source="Design",
            parent_layer_id=source_layer_id if parent_stack_id else "",
            parent_layer_stack_id=parent_stack_id,
            source_layer_id=source_layer_id if parent_stack_id else "",
            source_layer_stack_id=stack_id if parent_stack_id else "",
            is_left_intrusions_linked=True,
            intrusion_left_bottom="0mil",
            intrusion_left_top="0mil",
            is_right_intrusions_linked=True,
            intrusion_right_bottom="0mil",
            intrusion_right_top="0mil",
        )
        sections.append(
            AltiumStackBranchSection(
                source_section_id=section_id,
                name=f"Branch Section-{index + 1}",
                parent_section_id=parent_section_id,
                stacks=(section_stack,),
            )
        )
        parent_section_id = section_id
        parent_stack_id = stack_id
    return AltiumStackBranch(
        source_branch_id=resolved_branch_id,
        name=name,
        description="",
        parent_branch_id=parent_branch_id,
        sections=tuple(sections),
    )


def _rect_region(
    name: str,
    layerstack_id: str,
    left_mils: float,
    bottom_mils: float,
    right_mils: float,
    top_mils: float,
    *,
    locked_3d: bool = False,
    bends: tuple[AltiumStackBendLine, ...] = (),
) -> AltiumStackRegion:
    return AltiumStackRegion(
        name=name,
        layerstack_id=layerstack_id,
        locked_3d=locked_3d,
        bending_lines=bends,
        outline_vertices=tuple(
            (_to_iu(x_mils), _to_iu(y_mils))
            for x_mils, y_mils in (
                (left_mils, bottom_mils),
                (right_mils, bottom_mils),
                (right_mils, top_mils),
                (left_mils, top_mils),
            )
        ),
    )


def _stack_region(
    name: str,
    layerstack_id: str,
    outline_mils: tuple[tuple[float, float], ...],
    *,
    locked_3d: bool = False,
    bends: tuple[AltiumStackBendLine, ...] = (),
) -> AltiumStackRegion:
    return AltiumStackRegion(
        name=name,
        layerstack_id=layerstack_id,
        locked_3d=locked_3d,
        bending_lines=bends,
        outline_vertices=tuple(
            (_to_iu(x_mils), _to_iu(y_mils)) for x_mils, y_mils in outline_mils
        ),
    )


def _bend_line_mils(
    radius_mils: float,
    angle_deg: float,
    fold_index: int,
    start_mils: tuple[float, float],
    end_mils: tuple[float, float],
    region_origin_mils: tuple[float, float],
) -> AltiumStackBendLine:
    origin_x, origin_y = region_origin_mils
    return AltiumStackBendLine(
        angle_deg=angle_deg,
        radius_raw=_to_iu(radius_mils),
        fold_index=fold_index,
        x1=_to_iu(start_mils[0] - origin_x),
        y1=_to_iu(start_mils[1] - origin_y),
        x2=_to_iu(end_mils[0] - origin_x),
        y2=_to_iu(end_mils[1] - origin_y),
    )


def _native_signature(document: AltiumLayerStackDocument) -> dict[str, object]:
    signature = {
        "rigid_flex_mode": document.rigid_flex_mode,
        "substacks": _substack_signature(document),
        "branches": _branch_signature(document),
        "regions": [
            {
                "name": region.name,
                "layerstack_id": region.layerstack_id,
                "substack_name": (
                    document.substack_by_source_ref(region.layerstack_id).name
                    if document.substack_by_source_ref(region.layerstack_id) is not None
                    else ""
                ),
                "locked_3d": region.locked_3d,
                "bend_radii_mils": [line.radius_mils for line in region.bending_lines],
                "bend_angles_deg": [line.angle_deg for line in region.bending_lines],
                "outline_vertex_count": len(region.outline_vertices),
            }
            for region in document.board_regions
        ],
        "stiffener_layers": [
            layer.display_name
            for stack in document.physical_stacks
            for layer in stack.layers
            if layer.is_stiffener is True
        ],
        "coverlay_layers": [
            {
                "name": layer.display_name,
                "expansion": layer.coverlay_expansion,
            }
            for stack in document.physical_stacks
            for layer in stack.layers
            if layer.coverlay_expansion
        ],
    }
    adhesive_layers = _adhesive_layer_names(document)
    if adhesive_layers:
        signature["adhesive_layers"] = adhesive_layers
    surface_finish_layers = _surface_finish_layer_signature(document)
    if surface_finish_layers:
        signature["surface_finish_layers"] = surface_finish_layers
    return signature


def _pcbdoc_geometry_signature(pcbdoc: AltiumPcbDoc) -> dict[str, object]:
    outline = pcbdoc.board.outline
    return {
        "board_outline_vertex_count": len(outline.vertices),
        "board_outline_vertices_mils": _outline_vertex_signature(outline.vertices),
        "board_cutout_count": len(outline.cutouts),
        "board_cutout_vertex_counts": [
            len(cutout_vertices) for cutout_vertices in outline.cutouts
        ],
        "polygon_count": len(pcbdoc.polygons),
        "polygon_outline_vertex_counts": [
            len(getattr(polygon, "outline", ()) or ()) for polygon in pcbdoc.polygons
        ],
        "track_count": len(pcbdoc.tracks),
        "track_layers": [int(getattr(track, "layer", -1)) for track in pcbdoc.tracks],
        "region_count": len(pcbdoc.regions),
        "shapebased_region_count": len(pcbdoc.shapebased_regions),
        "shapebased_outline_vertex_counts": [
            len(getattr(region, "outline", ()) or ())
            for region in pcbdoc.shapebased_regions
        ],
        "shapebased_layers": [
            int(getattr(region, "layer", -1)) for region in pcbdoc.shapebased_regions
        ],
    }


def _outline_vertex_signature(vertices: Iterable[object]) -> list[tuple[float, float]]:
    return [
        (
            round(float(getattr(vertex, "x_mils", 0.0)), 4),
            round(float(getattr(vertex, "y_mils", 0.0)), 4),
        )
        for vertex in vertices
    ]


def _interchange_signature(document: AltiumLayerStackDocument) -> dict[str, object]:
    signature = {
        "rigid_flex_mode": document.rigid_flex_mode,
        "substacks": _substack_signature(document),
        "branches": _branch_signature(document),
        "stiffener_layers": [
            layer.display_name
            for stack in document.physical_stacks
            for layer in stack.layers
            if layer.is_stiffener is True
        ],
    }
    adhesive_layers = _adhesive_layer_names(document)
    if adhesive_layers:
        signature["adhesive_layers"] = adhesive_layers
    surface_finish_layers = _surface_finish_layer_signature(document)
    if surface_finish_layers:
        signature["surface_finish_layers"] = surface_finish_layers
    return signature


def _surface_finish_layer_signature(
    document: AltiumLayerStackDocument,
) -> list[dict[str, object]]:
    return [
        {
            "name": layer.display_name,
            "process": _stackupx_property_value(layer, "Process"),
            "material": _stackupx_property_value(layer, "Material")
            or layer.dielectric_material,
            "thickness_mils": round(float(layer.dielectric_height_mils), 4)
            if layer.dielectric_height_mils is not None
            else None,
            "contexts": [
                [_normalized_native_ref(context_ref), context_value]
                for context_ref, context_value in layer.substack_contexts
            ],
        }
        for stack in document.physical_stacks
        for layer in stack.layers
        if layer.family == "surface_finish"
    ]


def _stackupx_property_value(layer: AltiumStackLayer, name: str) -> str:
    for prop_name, _type_name, value in tuple(layer.stackupx_properties or ()):
        if prop_name == name:
            return value
    return ""


def _adhesive_layer_names(document: AltiumLayerStackDocument) -> list[str]:
    return [
        layer.display_name
        for stack in document.physical_stacks
        for layer in stack.layers
        if layer.is_adhesive is True
    ]


def _interchange_summary(document: AltiumLayerStackDocument) -> dict[str, object]:
    return {
        "rigid_flex_mode": document.rigid_flex_mode,
        "substack_count": len(document.substacks),
        "branch_count": len(document.branches),
        "branch_names": [branch.name for branch in document.branches],
        "flex_substack_names": [
            substack.name for substack in document.substacks if substack.is_flex
        ],
        "stiffener_layers": [
            layer.display_name
            for stack in document.physical_stacks
            for layer in stack.layers
            if layer.is_stiffener is True
        ],
    }


def _substack_signature(document: AltiumLayerStackDocument) -> list[dict[str, object]]:
    return [
        {
            "name": substack.name,
            "is_flex": substack.is_flex,
            "layers": [
                layer.display_name
                for layer in document.layers_for_substack(substack.source_stackup_ref)
            ],
        }
        for substack in document.substacks
    ]


def _branch_signature(document: AltiumLayerStackDocument) -> list[dict[str, object]]:
    return [
        {
            "name": branch.name,
            "parent_branch_id": _normalized_guid(branch.parent_branch_id),
            "sections": [
                {
                    "name": section.name,
                    "parent_section_id": _normalized_guid(section.parent_section_id),
                    "stacks": [
                        _branch_stack_signature(document, stack)
                        for stack in section.stacks
                    ],
                }
                for section in branch.sections
            ],
        }
        for branch in document.branches
    ]


def _branch_stack_signature(
    document: AltiumLayerStackDocument,
    stack: object,
) -> dict[str, object]:
    substack = document.substack_by_source_ref(getattr(stack, "source_stack_ref", ""))
    description = str(getattr(stack, "description", "") or "")
    signature: dict[str, object] = {
        "stack_name": substack.name if substack is not None else description,
        "description": description,
        "material_usage": str(getattr(stack, "material_usage", "") or ""),
    }
    intrusion = _branch_stack_intrusion_signature(stack)
    if intrusion:
        signature["intrusion"] = intrusion
    return signature


def _branch_stack_intrusion_signature(stack: object) -> dict[str, object]:
    signature = {
        "is_left_intrusions_linked": getattr(stack, "is_left_intrusions_linked", None),
        "intrusion_left_bottom": str(getattr(stack, "intrusion_left_bottom", "") or ""),
        "intrusion_left_top": str(getattr(stack, "intrusion_left_top", "") or ""),
        "is_right_intrusions_linked": getattr(
            stack,
            "is_right_intrusions_linked",
            None,
        ),
        "intrusion_right_bottom": str(
            getattr(stack, "intrusion_right_bottom", "") or ""
        ),
        "intrusion_right_top": str(getattr(stack, "intrusion_right_top", "") or ""),
    }
    defaults = {
        "is_left_intrusions_linked": True,
        "intrusion_left_bottom": "0m",
        "intrusion_left_top": "0m",
        "is_right_intrusions_linked": True,
        "intrusion_right_bottom": "0m",
        "intrusion_right_top": "0m",
    }
    if all(
        value is None
        or value == defaults[key]
        or (isinstance(value, str) and not value)
        for key, value in signature.items()
    ):
        return {}
    return signature


def _registry_from_layers(
    layers: tuple[AltiumStackLayer, ...],
) -> AltiumLayerRegistry:
    return AltiumLayerRegistry(
        entries=tuple(
            AltiumLayerRegistryEntry(
                model_id=layer.registry_ref,
                display_name=layer.display_name,
                family=layer.family,
                legacy_layer_id=layer.legacy_layer_id,
                v7_layer_id=layer.layer_id,
                source_layer_id=layer.layer_id,
                source_record_id=layer.source_record_id,
            )
            for layer in layers
        )
    )


def _layer_refs_by_name(layers: tuple[AltiumStackLayer, ...]) -> dict[str, str]:
    return {layer.display_name: layer.registry_ref for layer in layers}


def _source_layer_id(layers: tuple[AltiumStackLayer, ...], name: str) -> str:
    for layer in layers:
        if layer.display_name == name:
            return layer.source_record_id
    raise ValueError(f"Unknown layer name: {name}")


def _full_names(layers: tuple[AltiumStackLayer, ...]) -> tuple[str, ...]:
    return tuple(layer.display_name for layer in layers)


def _layer_ref(name: str) -> str:
    token = "".join(char.lower() if char.isalnum() else "_" for char in name)
    return f"public:{token}"


def _guid(*parts: object) -> str:
    seed = "|".join(str(part) for part in parts if str(part or ""))
    return "{" + str(uuid.uuid5(AUTHORING_NAMESPACE, seed)).upper() + "}"


def _normalized_guid(value: object) -> str:
    return str(value or "").strip().strip("{}").upper()


def _normalized_native_ref(value: object) -> str:
    return str(value or "").strip().strip("{}").upper()


def _to_iu(mils: float) -> int:
    return int(round(float(mils) * IU_PER_MIL))


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _relative_to_examples(path: Path, examples_root: Path) -> str:
    try:
        return path.resolve().relative_to(examples_root.resolve()).as_posix()
    except ValueError:
        return str(path)
