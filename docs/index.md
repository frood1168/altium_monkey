# altium-monkey

```text
..........▓▓▓▓▓▓▓▓▓▓..............
........▓▓▓▓▓▓▓▓▓▓▓▓▓▓............
......▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓..........
....▓▓▓▓░░░░░░▓▓░░░░░░▓▓▓▓........
░░░░▓▓░░░░░░░░░░░░░░░░░░▓▓░░░░....
░░░░▓▓░░....░░░░░░....░░▓▓░░░░....
..░░▓▓░░██..░░░░░░██..░░▓▓░░......
....▓▓░░░░░░░░░░░░░░░░░░▓▓........
......▓▓░░░░░░░░░░░░░░▓▓..........
........▓▓▓▓░░░░░░▓▓▓▓............
............▓▓▓▓▓▓..........░░....
..........▓▓▓▓▓▓▓▓▓▓......▓▓......
..........▓▓▓▓▓▓▓▓▓▓....▓▓▓▓......
........▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓........
........▓▓▓▓░░▓▓░░▓▓▓▓............
```

`ALTIUM MONKEY`

This is the documentation entry point for `altium-monkey`.

The docs are intended to be:

1. capability-first
2. example-heavy
3. easy for humans to scan
4. easy for LLM tooling to parse

Near-term focus:

1. keep the release/export flow simple
2. keep the example set current with the public API
3. keep the public Markdown documentation accurate and easy to scan

Domain guides:

1. [SchDoc](schdoc.md)
2. [SchLib](schlib.md)
3. [PcbDoc](pcbdoc.md)
4. [PcbLib](pcblib.md)
5. [PrjPcb](prjpcb.md)
6. [AltiumDesign](altium_design.md)
7. [IntLib](intlib.md)
8. [Draftsman](draftsman.md)

See the [examples index](examples/index.md) for the implemented sample set.

See the [schemas](schemas/index.md) page for the public JSON and SVG metadata
contracts emitted by `AltiumDesign`, `Netlist`, PCB SVG rendering, and
embedded/extractable asset inventory.

See the [format contracts](format_contracts/index.md) page for stable file,
API, and SVG behavior that downstream users can rely on.

See the [API patterns](api_patterns/index.md) page for units, object mutation
patterns, [PCB layers](api_patterns/pcb_layers.md),
[embedded PCB assets](api_patterns/embedded_assets.md),
[extractable assets](api_patterns/extractable_assets.md), and higher-level
API conventions.

See the [public docs style foundation](style.md) for the shared CSS asset and
generated-doc styling contract.

See the [release notes](../RELEASE_NOTES.md) for the current support boundary
and known functional gaps.
