from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Protocol

from altium_monkey import (
    AltiumPcbDoc,
    AltiumPcbLib,
    PcbLayerRef,
    PcbSvgRenderOptions,
)
from altium_monkey.altium_pcb_enums import PCB_USER_MECHANICAL_LAYER_AUTHORING_MAX
from altium_monkey.altium_pcblib_builder import PcbLibBuildProfile


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcb_v7_mechanical_layer_track_rows.PcbDoc"
OUTPUT_PCBLIB = OUTPUT_DIR / "pcb_v7_mechanical_layer_track_rows.PcbLib"
OUTPUT_PCBDOC_SVG = OUTPUT_DIR / "pcbdoc_mechanical_layer_track_rows.svg"
OUTPUT_PCBLIB_SVG = OUTPUT_DIR / "pcblib_mechanical_layer_track_rows.svg"
OUTPUT_MANIFEST = OUTPUT_DIR / "pcb_v7_mechanical_layer_track_rows.json"

SUPPORTED_MAX_MECHANICAL_LAYER = PCB_USER_MECHANICAL_LAYER_AUTHORING_MAX
FOOTPRINT_NAME = "V7_MECHANICAL_LAYER_TRACK_ROWS"
TRACK_LENGTH_MILS = 1000.0
TRACK_WIDTH_MILS = 10.0
TRACK_PITCH_MILS = 20.0
TRACK_START_X_MILS = 100.0
TRACK_START_Y_MILS = 100.0
BOARD_MARGIN_MILS = 100.0


class _MechanicalLayerOwner(Protocol):
    def set_mechanical_layer(
        self,
        layer: int | str,
        *,
        name: str | None = None,
        enabled: bool = True,
    ) -> None: ...


class _LayerTrack(Protocol):
    layer: int
    v7_layer_id: int

    def layer_ref(self) -> PcbLayerRef: ...


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _mechanical_layer_refs() -> tuple[PcbLayerRef, ...]:
    return tuple(
        PcbLayerRef.mechanical(number)
        for number in range(1, SUPPORTED_MAX_MECHANICAL_LAYER + 1)
    )


def _saved_layer_id(ref: PcbLayerRef) -> int:
    if ref.v7_saved_layer_id is None:
        raise RuntimeError(f"{ref.token} does not have a V7 saved-layer id")
    return ref.v7_saved_layer_id


def _mechanical_number(ref: PcbLayerRef) -> int:
    if ref.number is None:
        raise RuntimeError(f"{ref.token} does not have a mechanical number")
    return ref.number


def _display_name(ref: PcbLayerRef) -> str:
    return f"Sample Mechanical {_mechanical_number(ref):02d}"


def _configure_mechanical_layers(owner: _MechanicalLayerOwner) -> None:
    for ref in _mechanical_layer_refs():
        owner.set_mechanical_layer(ref.token, name=_display_name(ref), enabled=True)


def _board_size_mils() -> tuple[float, float]:
    width = (
        TRACK_START_X_MILS
        + TRACK_PITCH_MILS * (SUPPORTED_MAX_MECHANICAL_LAYER - 1)
        + BOARD_MARGIN_MILS
    )
    height = TRACK_START_Y_MILS + TRACK_LENGTH_MILS + BOARD_MARGIN_MILS
    return width, height


def _track_x_mils(index: int) -> float:
    return TRACK_START_X_MILS + TRACK_PITCH_MILS * index


def _add_pcbdoc_track_row(pcbdoc: AltiumPcbDoc) -> None:
    for index, ref in enumerate(_mechanical_layer_refs()):
        x_mils = _track_x_mils(index)
        pcbdoc.add_track(
            (x_mils, TRACK_START_Y_MILS),
            (x_mils, TRACK_START_Y_MILS + TRACK_LENGTH_MILS),
            width_mils=TRACK_WIDTH_MILS,
            layer=ref,
        )


def _add_pcblib_track_row(pcblib: AltiumPcbLib) -> None:
    footprint = pcblib.add_footprint(FOOTPRINT_NAME)
    for index, ref in enumerate(_mechanical_layer_refs()):
        x_mils = _track_x_mils(index)
        footprint.add_track(
            (x_mils, TRACK_START_Y_MILS),
            (x_mils, TRACK_START_Y_MILS + TRACK_LENGTH_MILS),
            width_mils=TRACK_WIDTH_MILS,
            layer=ref,
        )


def _pcbdoc_display_names(pcbdoc: AltiumPcbDoc) -> dict[str, str]:
    board = pcbdoc.board
    if board is None:
        raise RuntimeError("PcbDoc does not have a board record")
    return {
        ref.token: str(board.v9_layer_cache.get(_saved_layer_id(ref), ""))
        for ref in _mechanical_layer_refs()
    }


def _pcblib_display_names(pcblib_path: Path) -> dict[str, str]:
    profile = PcbLibBuildProfile.from_pcblib(pcblib_path)
    layer_table = profile.library_data.layer_table
    names: dict[str, str] = {}
    for ref in _mechanical_layer_refs():
        if ref.legacy_layer_id is not None:
            entry = layer_table.legacy_layer(ref.legacy_layer_id)
        else:
            entry = layer_table.v7_layer_by_layer_id(_saved_layer_id(ref))
        if entry is None:
            raise RuntimeError(f"{ref.token} missing from PcbLib layer table")
        names[ref.token] = entry.name
    return names


def _track_rows(
    tracks: Iterable[_LayerTrack],
    *,
    display_names: dict[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, (track, expected_ref) in enumerate(
        zip(tracks, _mechanical_layer_refs(), strict=True)
    ):
        actual_ref = track.layer_ref()
        expected_saved_layer_id = _saved_layer_id(expected_ref)
        rows.append(
            {
                "index": index,
                "mechanical_number": _mechanical_number(expected_ref),
                "token": actual_ref.token,
                "expected_token": expected_ref.token,
                "display_name": display_names[actual_ref.token],
                "expected_display_name": _display_name(expected_ref),
                "legacy_layer_id": expected_ref.legacy_layer_id,
                "stored_legacy_layer_id": int(track.layer),
                "v7_saved_layer_id": int(track.v7_layer_id),
                "expected_v7_saved_layer_id": expected_saved_layer_id,
                "v7_only": expected_ref.legacy_layer_id is None,
                "matches_expected": actual_ref == expected_ref
                and int(track.v7_layer_id) == expected_saved_layer_id
                and display_names[actual_ref.token] == _display_name(expected_ref),
            }
        )
    return rows


def _write_pcbdoc(pcbdoc_path: Path) -> AltiumPcbDoc:
    pcbdoc = AltiumPcbDoc()
    _configure_mechanical_layers(pcbdoc)
    board_width, board_height = _board_size_mils()
    pcbdoc.set_outline_rectangle_mils(0.0, 0.0, board_width, board_height)
    pcbdoc.set_origin_to_outline_lower_left()
    _add_pcbdoc_track_row(pcbdoc)
    pcbdoc.save(pcbdoc_path)
    return AltiumPcbDoc.from_file(pcbdoc_path)


def _write_pcblib(pcblib_path: Path) -> AltiumPcbLib:
    pcblib = AltiumPcbLib()
    _configure_mechanical_layers(pcblib)
    _add_pcblib_track_row(pcblib)
    pcblib.save(pcblib_path)
    return AltiumPcbLib.from_file(pcblib_path)


def _render_svgs(
    *,
    pcbdoc: AltiumPcbDoc,
    pcblib: AltiumPcbLib,
    pcbdoc_svg_path: Path,
    pcblib_svg_path: Path,
) -> None:
    options = PcbSvgRenderOptions(
        visible_layers=_mechanical_layer_refs(),
        include_render_layer_metadata=True,
    )
    pcbdoc_svg_path.write_text(pcbdoc.to_svg(options), encoding="utf-8")
    footprint = pcblib.footprints[0]
    pcblib_svg_path.write_text(footprint.to_svg(options), encoding="utf-8")


def _write_manifest(
    *,
    pcbdoc_path: Path,
    pcblib_path: Path,
    pcbdoc_svg_path: Path,
    pcblib_svg_path: Path,
    manifest_path: Path,
    pcbdoc: AltiumPcbDoc,
    pcblib: AltiumPcbLib,
) -> Path:
    pcbdoc_tracks = _track_rows(
        pcbdoc.tracks,
        display_names=_pcbdoc_display_names(pcbdoc),
    )
    pcblib_tracks = _track_rows(
        pcblib.footprints[0].tracks,
        display_names=_pcblib_display_names(pcblib_path),
    )
    manifest = {
        "schema": "altium_monkey.examples.pcb_v7_mechanical_layer_track_rows.a0",
        "supported_mechanical_layer_count": SUPPORTED_MAX_MECHANICAL_LAYER,
        "track_geometry_mils": {
            "length": TRACK_LENGTH_MILS,
            "width": TRACK_WIDTH_MILS,
            "pitch": TRACK_PITCH_MILS,
        },
        "outputs": {
            "pcbdoc": _relative_to_examples(pcbdoc_path),
            "pcblib": _relative_to_examples(pcblib_path),
            "pcbdoc_svg": _relative_to_examples(pcbdoc_svg_path),
            "pcblib_svg": _relative_to_examples(pcblib_svg_path),
            "manifest": _relative_to_examples(manifest_path),
        },
        "pcbdoc": {
            "track_count": len(pcbdoc_tracks),
            "tracks": pcbdoc_tracks,
            "all_tracks_match_expected": all(
                row["matches_expected"] for row in pcbdoc_tracks
            ),
        },
        "pcblib": {
            "footprint_name": pcblib.footprints[0].name,
            "track_count": len(pcblib_tracks),
            "tracks": pcblib_tracks,
            "all_tracks_match_expected": all(
                row["matches_expected"] for row in pcblib_tracks
            ),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def build_sample(output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pcbdoc_path = output_dir / OUTPUT_PCBDOC.name
    pcblib_path = output_dir / OUTPUT_PCBLIB.name
    pcbdoc_svg_path = output_dir / OUTPUT_PCBDOC_SVG.name
    pcblib_svg_path = output_dir / OUTPUT_PCBLIB_SVG.name
    manifest_path = output_dir / OUTPUT_MANIFEST.name

    pcbdoc = _write_pcbdoc(pcbdoc_path)
    pcblib = _write_pcblib(pcblib_path)
    _render_svgs(
        pcbdoc=pcbdoc,
        pcblib=pcblib,
        pcbdoc_svg_path=pcbdoc_svg_path,
        pcblib_svg_path=pcblib_svg_path,
    )
    _write_manifest(
        pcbdoc_path=pcbdoc_path,
        pcblib_path=pcblib_path,
        pcbdoc_svg_path=pcbdoc_svg_path,
        pcblib_svg_path=pcblib_svg_path,
        manifest_path=manifest_path,
        pcbdoc=pcbdoc,
        pcblib=pcblib,
    )
    return pcbdoc_path, pcblib_path, pcbdoc_svg_path, pcblib_svg_path, manifest_path


def main() -> None:
    pcbdoc_path, pcblib_path, pcbdoc_svg_path, pcblib_svg_path, manifest_path = (
        build_sample()
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"Wrote {pcbdoc_path}")
    print(f"Wrote {pcblib_path}")
    print(f"Wrote {pcbdoc_svg_path}")
    print(f"Wrote {pcblib_svg_path}")
    print(f"Wrote {manifest_path}")
    print(f"Mechanical layers: {manifest['supported_mechanical_layer_count']}")
    print(
        "PcbDoc tracks match expected layers: "
        f"{manifest['pcbdoc']['all_tracks_match_expected']}"
    )
    print(
        "PcbLib tracks match expected layers: "
        f"{manifest['pcblib']['all_tracks_match_expected']}"
    )


if __name__ == "__main__":
    main()
