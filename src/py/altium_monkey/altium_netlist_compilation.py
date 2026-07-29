"""
Top-level netlist compilation entrypoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .altium_netlist_options import NetlistOptions
    from .altium_netlist_model import Netlist
    from .altium_prjpcb import AltiumPrjPcb
    from .altium_schdoc import AltiumSchDoc


def _default_options_for_compile_netlist(
    schdocs: list["AltiumSchDoc"],
    project: "AltiumPrjPcb | None",
) -> "NetlistOptions":
    from .altium_netlist_options import NetlistOptions

    if project is None:
        return NetlistOptions()

    result = NetlistOptions.from_prjpcb(project)
    sheet_params: dict[str, str] = {}
    for schdoc in schdocs:
        sheet_params.update(schdoc.get_parameter_dict())
    result.sheet_parameters = sheet_params
    return result


def compile_netlist(
    schdocs: list["AltiumSchDoc"],
    project: "AltiumPrjPcb | None" = None,
    options: "NetlistOptions | None" = None,
) -> "Netlist":
    """
    Compile a design netlist through the primary entrypoint.
    
        Single-sheet and multi-sheet designs compile through the top-level
        netlist compilers.
    """

    from .altium_design import AltiumDesign
    from .altium_netlist_options import NetlistOptions
    from .altium_netlist_single_sheet import AltiumNetlistSingleSheetCompiler

    if not schdocs:
        raise ValueError("compile_netlist() requires at least one schematic document")

    effective_options = options or _default_options_for_compile_netlist(
        schdocs,
        project,
    )
    if len(schdocs) == 1:
        return AltiumNetlistSingleSheetCompiler(
            schdocs[0],
            options=effective_options,
        ).generate()

    design = AltiumDesign(
        project=project,
        schdocs=list(schdocs),
        _options=effective_options,
    )
    return design.to_netlist()


__all__ = ["compile_netlist"]
