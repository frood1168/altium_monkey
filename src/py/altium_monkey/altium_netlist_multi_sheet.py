"""Compatibility wrapper for retired project-level multi-sheet netlisting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .altium_netlist_multi_sheet_support import (
    find_harness_bundle_info,
    find_harness_port_name,
)

if TYPE_CHECKING:
    from .altium_netlist_model import Netlist
    from .altium_netlist_options import NetlistOptions
    from .altium_prjpcb import AltiumPrjPcb
    from .altium_schdoc import AltiumSchDoc


class AltiumNetlistMultiSheetCompiler:
    """
    Compatibility facade for the retired multi-sheet clone/rewrite compiler.

    Project-level netlisting now routes through the compiled design model. This
    class remains importable for older callers and probes, but ``build()`` no
    longer executes the retired implementation.
    """

    def __init__(
        self,
        schdocs: list["AltiumSchDoc"],
        project: "AltiumPrjPcb | None",
        options: "NetlistOptions",
    ) -> None:
        self._schdocs = list(schdocs)
        self._source_schdocs = list(self._schdocs)
        self._project = project
        self._options = options

    def build(self) -> "Netlist":
        """Build a netlist via ``AltiumDesign.compile().to_netlist()``."""
        from .altium_design import AltiumDesign

        design = AltiumDesign(
            project=self._project,
            schdocs=list(self._schdocs),
            _options=self._options,
        )
        return design.to_netlist()

    @staticmethod
    def _find_harness_port_name(
        connector: object,
        signal_harnesses: object,
        port_location_map: dict[tuple[int, int], str],
    ) -> str | None:
        """Compatibility wrapper for the shared harness-port lookup helper."""
        return find_harness_port_name(
            connector,
            signal_harnesses,
            port_location_map,
        )

    @staticmethod
    def _find_harness_bundle_info(
        connector: object,
        signal_harnesses: object,
        port_location_map: dict[tuple[int, int], str],
    ) -> dict[str, object]:
        """Compatibility wrapper for the shared harness-bundle lookup helper."""
        return find_harness_bundle_info(
            connector,
            signal_harnesses,
            port_location_map,
        )


__all__ = ["AltiumNetlistMultiSheetCompiler"]
