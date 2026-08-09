"""Check the proposed RfBoard sheet-symbol fills against the constraints that bind.

Reuses the dataviz validator's colour math (contrast, OKLab dE, CVD simulation).
"""
from __future__ import annotations

import sys

sys.path.insert(
    0,
    r"C:\Users\DANYAL~1\AppData\Local\Temp\claude\bundled-skills\2.1.220"
    r"\a7b0d0160c2afe27fbb91f17d3fbb0b1\dataviz\scripts",
)
from validate_palette import contrast, deltaE  # noqa: E402

WHITE = "#FFFFFF"      # Altium sheet background
BLACK = "#000000"      # sheet-name / entry text
CHIP = "#FFFF80"       # existing sheet-entry fill

# per-parent-sheet groups: these are the only sets seen side by side
SHEETS = {
    "Rfboard_Top": [
        ("U_Rfboard_Praline",       "#EEC6D3", "yours"),
        ("U_Rfboard_Rffe-Mux",      "#E2A48F", "yours"),
        ("U_Rfboard_Power",         "#C56F55", "yours"),
    ],
    "Rfboard_Praline": [
        ("Switch Control",          "#5590CD", "praline"),
        ("U_Rfboard_Control-Logic", "#EEC6D3", "yours"),
        ("U_Rfboard_Sdr-Afe",       "#E2A48F", "yours"),
        ("U_Rfboard_Sdr-Rffe",      "#C56F55", "yours"),
    ],
    "Rfboard_Sdr-Rffe (RF chain)": [
        ("RF Front End",            "#A9CBEA", "praline"),
        ("Mixer",                   "#7FAEDC", "praline"),
        ("Image Reject Filters",    "#5590CD", "praline"),
        ("U_mixer-rxtx",            "#2B72BE", "praline"),
    ],
    "Rfboard_Sdr-Afe (conversion)": [
        ("Clock Generator",         "#9FD8CE", "praline"),
        ("IF Transceiver",          "#6FC4B5", "praline"),
        ("ADC, DAC",                "#42AC9A", "praline"),
        ("FPGA",                    "#1E9280", "praline"),
    ],
    "Rfboard_Control-Logic": [
        ("Microcontroller",         "#A9CBEA", "praline"),
        ("Power",                   "#6C9FD4", "praline"),
        ("USB",                     "#3372B5", "praline"),
    ],
    "Rfboard_Mux": [
        ("U_Rfboard_Mux-Ctrl",      "#EEC6D3", "yours"),
        ("U_Rfboard_Mux",           "#E2A48F", "yours"),
    ],
}

print(f"{'fill':<9} {'blk txt':>8} {'vs white':>9} {'vs chip':>8} {'dE chip':>8}   block")
print("-" * 74)
seen = {}
for sheet, rows in SHEETS.items():
    for name, hexv, fam in rows:
        seen[hexv] = fam
        print(
            f"{hexv:<9} {contrast(BLACK, hexv):>7.1f}: {contrast(WHITE, hexv):>8.2f}: "
            f"{contrast(CHIP, hexv):>7.2f}: {deltaE(CHIP, hexv):>8.1f}   {name}"
        )

print("\nWorst within-sheet pair (all pairs, normal + CVD):")
ok = True
for sheet, rows in SHEETS.items():
    worst = None
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i][1], rows[j][1]
            d = deltaE(a, b)
            cvd = min(deltaE(a, b, "protan"), deltaE(a, b, "deutan"))
            if worst is None or d < worst[0]:
                worst = (d, cvd, rows[i][0], rows[j][0])
    if worst:
        flag = "ok " if worst[0] >= 15 and worst[1] >= 8 else "LOW"
        if flag == "LOW":
            ok = False
        print(f"  [{flag}] {sheet:<30} dE {worst[0]:5.1f} normal / {worst[1]:5.1f} cvd"
              f"   ({worst[2]} vs {worst[3]})")

print("\nFamily separation (every praline fill vs every 'yours' fill):")
pral = [h for h, f in seen.items() if f == "praline"]
mine = [h for h, f in seen.items() if f == "yours"]
worst = min(((deltaE(a, b), min(deltaE(a, b, "protan"), deltaE(a, b, "deutan")), a, b)
             for a in pral for b in mine), key=lambda t: t[0])
print(f"  worst cross-family dE {worst[0]:.1f} normal / {worst[1]:.1f} cvd  ({worst[2]} vs {worst[3]})")
print("\nALL WITHIN-SHEET CHECKS PASS" if ok else "\nSOME WITHIN-SHEET PAIRS TOO CLOSE")
