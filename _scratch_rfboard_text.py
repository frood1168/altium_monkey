"""Scratch: where does black text actually sit on RfBoard sheet symbols?"""
from __future__ import annotations

from pathlib import Path

from altium_monkey import AltiumSchDoc

ROOT = Path(r"C:\Workspace\!__Balboa\!__Altium\RfBoard")


def hx(v):
    if v is None:
        return "-"
    v = int(v)
    return f"#{v & 0xFF:02X}{(v >> 8) & 0xFF:02X}{(v >> 16) & 0xFF:02X}"


doc = AltiumSchDoc(ROOT / "Rfboard_Sdr-Rffe.SchDoc")
syms = [o for o in doc.objects if type(o).__name__ == "AltiumSchSheetSymbol"]

for s in syms:
    print(f"\n=== {getattr(s.sheet_name, 'text', '?')} ===")
    print(f"  symbol origin=({s.location.x},{s.location.y}) size={s.x_size}x{s.y_size} "
          f"fill={hx(s.area_color)} border={hx(s.color)}")
    for label, obj in (("sheet_name", s.sheet_name), ("file_name", s.file_name)):
        if obj is None:
            print(f"  {label}: None")
            continue
        print(f"  {label}: text={getattr(obj,'text','?')!r} color={hx(getattr(obj,'color',None))} "
              f"loc=({obj.location.x},{obj.location.y}) "
              f"hidden={getattr(obj,'is_hidden',None)} "
              f"font_id={getattr(obj,'font_id',None)}")
    for e in s.entries[:3]:
        print(f"  entry {getattr(e,'name','?')!r}: text={hx(getattr(e,'text_color',None))} "
              f"fill={hx(getattr(e,'area_color',None))} border={hx(getattr(e,'color',None))} "
              f"side={getattr(e,'side',None)} dist_top={getattr(e,'distance_from_top',None)}")
