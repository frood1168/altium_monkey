"""Scratch: dump RfBoard sheet-symbol hierarchy + current colors."""
from __future__ import annotations

from pathlib import Path

from altium_monkey import AltiumSchDoc

ROOT = Path(r"C:\Workspace\!__Balboa\!__Altium\RfBoard")


def bgr_to_hex(v):
    if v is None:
        return "-"
    v = int(v)
    r = v & 0xFF
    g = (v >> 8) & 0xFF
    b = (v >> 16) & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def main() -> None:
    docs = sorted(
        p
        for p in ROOT.rglob("*.SchDoc")
        if not any(
            seg in p.parts
            for seg in ("history", "Project Logs for RfBoard", "Project Outputs for RfBoard")
        )
    )
    for path in docs:
        rel = path.relative_to(ROOT)
        try:
            doc = AltiumSchDoc(path)
        except Exception as exc:  # noqa: BLE001
            print(f"\n### {rel}  -- LOAD FAILED: {type(exc).__name__}: {exc}")
            continue

        syms = [o for o in doc.objects if type(o).__name__ == "AltiumSchSheetSymbol"]
        if not syms:
            continue
        print(f"\n### {rel}   ({len(syms)} sheet symbols)")
        for s in syms:
            name = getattr(s.sheet_name, "text", "?") if s.sheet_name else "?"
            fname = getattr(s.file_name, "text", "?") if s.file_name else "?"
            entry_colors = sorted(
                {
                    (bgr_to_hex(getattr(e, "text_color", None)),
                     bgr_to_hex(getattr(e, "area_color", None)))
                    for e in s.entries
                }
            )
            print(
                f"  - {name:<28} -> {fname:<30} "
                f"fill={bgr_to_hex(s.area_color):<8} border={bgr_to_hex(s.color):<8} "
                f"solid={s.is_solid} lw={s.line_width.name:<8} "
                f"size={s.x_size}x{s.y_size} entries={len(s.entries)}"
            )
            if entry_colors:
                print(f"      entry (text,fill) colors: {entry_colors}")


if __name__ == "__main__":
    main()
