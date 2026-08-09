"""Apply the RfBoard sheet-symbol colour scheme.

Two channels:
  border colour + line width  ->  PROVENANCE (praline/hackrf-pro vs yours)
  fill colour                 ->  subsystem lane + position in its signal chain

Dry-run by default. Pass --write to emit files; --in-place to overwrite sources
(only ever do that on a clean git tree / with a backup).
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from altium_monkey import AltiumSchDoc, ColorValue, LineWidth

ROOT = Path(r"C:\Workspace\!__Balboa\!__Altium\RfBoard")

PRALINE_BORDER = "#1A5FA0"   # cool  - upstream, kept intact
MINE_BORDER = "#A8492E"      # warm  - yours

# sheet-symbol NAME -> (fill, family).  Keyed by the sheet symbol's name label.
SCHEME: dict[str, tuple[str, str]] = {
    # --- Rfboard_Top.SchDoc -------------------------------------------------
    "U_Rfboard_Praline":       ("#EEC6D3", "mine"),
    "U_Rfboard_Rffe-Mux":      ("#E2A48F", "mine"),
    "U_Rfboard_Power":         ("#C56F55", "mine"),
    # --- Praline\Rfboard_Praline.SchDoc ------------------------------------
    "Switch Control":          ("#5590CD", "praline"),
    "U_Rfboard_Control-Logic": ("#EEC6D3", "mine"),
    "U_Rfboard_Sdr-Afe":       ("#E2A48F", "mine"),
    "U_Rfboard_Sdr-Rffe":      ("#C56F55", "mine"),
    # --- Rfboard_Sdr-Rffe.SchDoc  (RF chain: antenna -> IF) ----------------
    "RF Front End":            ("#A9CBEA", "praline"),
    "Mixer":                   ("#7FAEDC", "praline"),
    "Image Reject Filters":    ("#5590CD", "praline"),
    "U_mixer-rxtx":            ("#2B72BE", "praline"),
    # --- Rfboard_Sdr-Afe.SchDoc   (conversion: clock -> fabric) -----------
    "Clock Generator":         ("#9FD8CE", "praline"),
    "IF Transceiver":          ("#6FC4B5", "praline"),
    "ADC, DAC":                ("#42AC9A", "praline"),
    "FPGA":                    ("#1E9280", "praline"),
    # --- Rfboard_Control-Logic.SchDoc ---------------------------------------
    "Microcontroller":         ("#A9CBEA", "praline"),
    "Power":                   ("#6C9FD4", "praline"),
    "USB":                     ("#3372B5", "praline"),
    # --- Rfboard_Mux.SchDoc -------------------------------------------------
    "U_Rfboard_Mux-Ctrl":      ("#EEC6D3", "mine"),
    "U_Rfboard_Mux":           ("#E2A48F", "mine"),
}

FAMILY = {
    "praline": (PRALINE_BORDER, LineWidth.MEDIUM),
    "mine": (MINE_BORDER, LineWidth.SMALL),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write *_recolored.SchDoc")
    ap.add_argument("--in-place", action="store_true", help="overwrite the source files")
    args = ap.parse_args()

    docs = sorted(
        p
        for p in ROOT.rglob("*.SchDoc")
        if not any(
            s in p.parts
            for s in ("history", "Project Logs for RfBoard", "Project Outputs for RfBoard")
        )
    )

    total, unmatched = 0, []
    for path in docs:
        doc = AltiumSchDoc(path)
        syms = [o for o in doc.objects if type(o).__name__ == "AltiumSchSheetSymbol"]
        if not syms:
            continue

        touched = 0
        print(f"\n{path.relative_to(ROOT)}")
        for s in syms:
            name = getattr(s.sheet_name, "text", None)
            entry = SCHEME.get(name)
            if entry is None:
                unmatched.append((path.name, name))
                print(f"  !! no scheme entry for {name!r} - left unchanged")
                continue
            fill, family = entry
            border, width = FAMILY[family]
            print(
                f"  {name:<26} fill #{'':.0}{fill[1:]}  border {border}  "
                f"{width.name:<6} [{family}]"
            )
            s.area_color = ColorValue.from_hex(fill).win32
            s.color = ColorValue.from_hex(border).win32
            s.line_width = width
            s.is_solid = True
            touched += 1
        total += touched

        if args.write or args.in_place:
            if args.in_place:
                backup = path.with_suffix(path.suffix + ".bak")
                if not backup.exists():
                    shutil.copy2(path, backup)
                out = path
            else:
                out = path.with_name(path.stem + "_recolored" + path.suffix)
            doc.save(out)
            print(f"  -> wrote {out.name}")

    print(f"\n{total} sheet symbols styled across {len(docs)} documents.")
    if unmatched:
        print(f"UNMATCHED ({len(unmatched)}): {unmatched}")
    if not (args.write or args.in_place):
        print("DRY RUN - nothing written. Re-run with --write.")


if __name__ == "__main__":
    main()

