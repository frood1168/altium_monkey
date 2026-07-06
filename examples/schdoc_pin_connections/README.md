# schdoc_pin_connections

Compile a project netlist, walk all SchDocs for a single component designator,
and write a CSV of each pin's number, name, and connected net.

The script loads the project with `AltiumDesign.from_prjpcb(...)`, builds the
compiled netlist, then walks every reachable SchDoc (via `AltiumPrjPcb`) to
collect the target component's pins across all parts and sheets. Pins that are
not present in the compiled netlist are reported as `NC`.

## What It Shows

1. Compiling a project netlist with `AltiumDesign.to_netlist()`
2. Walking reachable SchDocs with `AltiumPrjPcb.get_reachable_schdoc_paths()`
3. Matching a component by designator and reading its pins
4. Mapping pins to nets and emitting a CSV report

## Run

Arg-free demo (uses the bundled RT_SUPER_C1 project and designator `U1`):

```powershell
uv run python examples\schdoc_pin_connections\schdoc_pin_connections.py
```

Real usage with an explicit project and designator:

```powershell
uv run python examples\schdoc_pin_connections\schdoc_pin_connections.py path\to\PROJECT.PrjPcb R5
```

Options: `-o/--output FILE.csv`, `--filter-nets GND VCC ...` (exclude nets),
`--no-nc` (drop unconnected pins).

## Input Project

The arg-free demo reads the bundled sample:

```text
examples/assets/projects/rt_super_c1/RT_SUPER_C1.PrjPcb
```

## Output

The demo writes (path is resolved next to the script, not the current dir):

```text
examples/schdoc_pin_connections/output/U1_connections.csv
```

Columns: `Designator, Part, Pin, Pin Name, Net`.
