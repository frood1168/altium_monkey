"""
intlib_merge — Combine a directory of IntLib files into a single merged IntLib.

Each source IntLib's embedded SchLib and PcbLib streams are extracted to a
temporary directory, merged using the SchLib/PcbLib merge APIs, and repacked
into a new OLE-format IntLib with compressed source streams.

Usage:
    uv run python examples/intlib_merge/intlib_merge.py <INPUT_DIR> [options]

Options:
    --recurse / -r         Also search subdirectories for .IntLib files
    --output / -o PATH     Output file (default: <INPUT_DIR>/merged.IntLib)
    --name / -n NAME       Base name used for stream filenames inside the output
                           IntLib (default: merged)
    --conflicts MODE       How to handle duplicate symbol/footprint names:
                           rename (default), skip
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import zlib
from pathlib import Path

from altium_monkey import AltiumIntLib, AltiumOleWriter, AltiumPcbLib, AltiumSchLib


_COMPRESSED_PREFIX = 0x02


def _compress_stream(data: bytes) -> bytes:
    """Wrap bytes in Altium's IntLib compression envelope (0x02 prefix + zlib)."""
    return bytes([_COMPRESSED_PREFIX]) + zlib.compress(data)


def _discover_intlibs(root: Path, recurse: bool) -> list[Path]:
    pattern = "**/*.IntLib" if recurse else "*.IntLib"
    return sorted(p for p in root.glob(pattern) if p.is_file())


def _extract_sources(
    intlib_path: Path,
    dest_dir: Path,
) -> tuple[list[Path], list[Path], bytes | None]:
    """Extract SchLib and PcbLib files from one IntLib. Returns (schlibpaths, pcblibpaths, version_bytes)."""
    schlib_files: list[Path] = []
    pcblib_files: list[Path] = []
    version_bytes: bytes | None = None

    with AltiumIntLib(intlib_path) as lib:
        result = lib.extract_sources(dest_dir, write_libpkg=False)
        # Capture Version.Txt from first IntLib that has it
        try:
            version_bytes = lib.read_stream("Version.Txt", decompress=False)
        except Exception:
            pass

        for source in result.sources:
            if source.output_path is None:
                continue
            ext = source.output_path.suffix.casefold()
            if ext == ".schlib":
                schlib_files.append(source.output_path)
            elif ext == ".pcblib":
                pcblib_files.append(source.output_path)

    return schlib_files, pcblib_files, version_bytes


def _merge_pcblibs(
    pcblib_paths: list[Path],
    output_path: Path,
) -> tuple[int, int]:
    """Merge PcbLib files into output_path. Returns (added_count, skipped_count)."""
    merged = AltiumPcbLib()
    seen: set[str] = set()
    added = 0
    skipped = 0

    for path in pcblib_paths:
        try:
            src = AltiumPcbLib.from_file(path)
        except Exception as exc:
            print(f"  Warning: could not read {path.name}: {exc}", file=sys.stderr)
            continue

        for fp in src.footprints:
            name = fp.name or ""
            if name in seen:
                # Always skip PcbLib duplicates — renaming would break SchLib
                # cross-references stored inside the symbol parameters.
                skipped += 1
                continue
            seen.add(name)
            merged.add_existing_footprint(fp)
            added += 1

    merged.save(output_path)
    return added, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge a directory of .IntLib files into a single combined IntLib. "
            "Duplicate symbol/footprint names are renamed by default."
        ),
    )
    parser.add_argument("input_dir", metavar="INPUT_DIR",
                        help="Directory containing .IntLib files to merge.")
    parser.add_argument("--recurse", "-r", action="store_true",
                        help="Recurse into subdirectories.")
    parser.add_argument("--output", "-o", metavar="OUTPUT.IntLib",
                        help="Output path (default: <INPUT_DIR>/merged.IntLib).")
    parser.add_argument("--name", "-n", default="merged", metavar="NAME",
                        help="Base name for embedded stream files (default: merged).")
    parser.add_argument("--conflicts", choices=("rename", "skip"), default="rename",
                        help="Duplicate name handling: rename (default) or skip.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.is_dir():
        print(f"Not a directory: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve() if args.output else input_dir / "merged.IntLib"
    base_name = args.name

    intlib_files = _discover_intlibs(input_dir, args.recurse)
    if not intlib_files:
        print(f"No .IntLib files found in: {input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Input dir:  {input_dir}")
    print(f"IntLib files: {len(intlib_files)}")
    for p in intlib_files:
        rel = p.relative_to(input_dir) if p.is_relative_to(input_dir) else p
        print(f"  {rel}")
    print()

    with tempfile.TemporaryDirectory(prefix="intlib_merge_") as tmp:
        tmp_path = Path(tmp)
        all_schlib_paths: list[Path] = []
        all_pcblib_paths: list[Path] = []
        captured_version: bytes | None = None

        for idx, intlib_path in enumerate(intlib_files):
            sub_dir = tmp_path / f"src_{idx:04d}"
            sub_dir.mkdir()
            print(f"Extracting [{idx + 1}/{len(intlib_files)}] {intlib_path.name} ...")
            try:
                sch_paths, pcb_paths, ver_bytes = _extract_sources(intlib_path, sub_dir)
            except Exception as exc:
                print(f"  Error: {exc}", file=sys.stderr)
                continue

            all_schlib_paths.extend(sch_paths)
            all_pcblib_paths.extend(pcb_paths)
            if captured_version is None and ver_bytes:
                captured_version = ver_bytes

            print(f"  {len(sch_paths)} SchLib, {len(pcb_paths)} PcbLib stream(s)")

        print()
        print(f"Total SchLib streams: {len(all_schlib_paths)}")
        print(f"Total PcbLib streams: {len(all_pcblib_paths)}")

        merged_schlib_path: Path | None = None
        merged_schlib_count = 0
        if all_schlib_paths:
            merged_schlib_path = tmp_path / f"{base_name}.SchLib"
            print(f"\nMerging {len(all_schlib_paths)} SchLib stream(s)...")
            merged_schlib = AltiumSchLib.merge(
                all_schlib_paths,
                merged_schlib_path,
                handle_conflicts=args.conflicts,
                verbose=False,
            )
            merged_schlib_count = len(merged_schlib.symbols)
            print(f"  {merged_schlib_count} symbols in merged SchLib")

        merged_pcblib_path: Path | None = None
        merged_pcblib_count = 0
        merged_pcblib_skipped = 0
        if all_pcblib_paths:
            merged_pcblib_path = tmp_path / f"{base_name}.PcbLib"
            print(f"\nMerging {len(all_pcblib_paths)} PcbLib stream(s)...")
            merged_pcblib_count, merged_pcblib_skipped = _merge_pcblibs(
                all_pcblib_paths, merged_pcblib_path
            )
            print(f"  {merged_pcblib_count} footprints in merged PcbLib"
                  + (f" ({merged_pcblib_skipped} duplicates skipped)" if merged_pcblib_skipped else ""))

        # Pack into IntLib OLE container
        print(f"\nBuilding {output_path.name}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer = AltiumOleWriter()

        if merged_schlib_path and merged_schlib_path.exists():
            schlib_bytes = merged_schlib_path.read_bytes()
            writer.add_stream(f"SchLib/{base_name}.SchLib", _compress_stream(schlib_bytes))

        if merged_pcblib_path and merged_pcblib_path.exists():
            pcblib_bytes = merged_pcblib_path.read_bytes()
            writer.add_stream(f"PCBLib/{base_name}.PcbLib", _compress_stream(pcblib_bytes))

        if captured_version is not None:
            writer.add_stream("Version.Txt", captured_version)

        writer.write(output_path)

    size_kb = output_path.stat().st_size / 1024
    print(f"\nWrote: {output_path}")
    print(f"Size:       {size_kb:,.1f} KB")
    print(f"Symbols:    {merged_schlib_count}")
    print(f"Footprints: {merged_pcblib_count}"
          + (f" ({merged_pcblib_skipped} duplicates skipped)" if merged_pcblib_skipped else ""))


if __name__ == "__main__":
    main()
