"""
Composed Altium design model.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .altium_api_markers import public_api
from .altium_netlist_common import _evaluate_altium_expression
from .altium_pnp_position import (
    PNP_POSITION_MODE_ALTIUM_PICK_PLACE,
    PnpPositionMode,
    normalize_pnp_position_mode,
)

if TYPE_CHECKING:
    from .altium_compiled_design_model import AltiumCompiledDesign
    from .altium_netlist_options import NetlistOptions
    from .altium_netlist_model import (
        ComponentHierarchy,
        Net,
        Netlist,
        NetlistComponent,
        PnpEntry,
    )
    from .altium_pcbdoc import AltiumPcbDoc
    from .altium_prjpcb import AltiumPrjPcb
    from .altium_sch_geometry_oracle import SchGeometryDocument
    from .altium_sch_svg_renderer import SchSvgRenderOptions
    from .altium_schdoc import AltiumSchDoc
    from .altium_schdoc_info import SchComponentInfo

log = logging.getLogger(__name__)

DESIGN_JSON_SCHEMA = "altium_monkey.design.a2"
DESIGN_JSON_GENERATOR = "altium_monkey"
SCHEMATIC_HIERARCHY_SCHEMA = "altium_monkey.schematic_hierarchy.a1"
_CANONICAL_DECIMAL_RE = re.compile(r"0|[1-9][0-9]*")


def _coerce_variant_parameter_overrides(
    variant_data: dict[str, object],
) -> dict[str, dict[str, str]]:
    """
    Return variant parameter overrides grouped by source designator.
    """
    overrides: dict[str, dict[str, str]] = {}
    raw_overrides = variant_data.get("parameter_overrides")
    if isinstance(raw_overrides, dict):
        for designator, parameters in raw_overrides.items():
            designator_s = str(designator or "").strip()
            if not designator_s or not isinstance(parameters, dict):
                continue
            coerced_params = {
                str(name): str(value)
                for name, value in parameters.items()
                if str(name or "").strip()
            }
            if coerced_params:
                overrides[designator_s] = coerced_params

    raw_param_variations = variant_data.get("param_variations")
    param_variations = (
        raw_param_variations if isinstance(raw_param_variations, list) else []
    )
    for row in param_variations:
        if not isinstance(row, dict):
            continue
        designator = str(
            row.get("ParamDesignator") or row.get("Designator") or ""
        ).strip()
        parameter_name = str(row.get("ParameterName") or "").strip()
        if not designator or not parameter_name:
            continue
        overrides.setdefault(designator, {})[parameter_name] = str(
            row.get("VariantValue", "")
        )

    return overrides


def _variant_dnp_designators(variant_data: dict[str, object]) -> set[str]:
    """
    Return designators marked not fitted in one project variant.
    """
    dnp_designators: set[str] = set()
    raw_variations = variant_data.get("variations", [])
    variations = raw_variations if isinstance(raw_variations, list) else []
    for variation in variations:
        if not isinstance(variation, dict):
            continue
        if variation.get("Kind") != "1":
            continue
        designator = str(variation.get("Designator", "") or "").strip()
        if designator:
            dnp_designators.add(designator)
    return dnp_designators


def _lookup_case_insensitive(values: dict[str, str], name: str) -> str | None:
    name_lower = name.lower()
    for key, value in values.items():
        if key.lower() == name_lower:
            return value
    return None


def _sorted_json_mapping(values: dict) -> dict:
    return dict(sorted(values.items(), key=lambda item: str(item[0])))


def _unique_nonempty_strings(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _sorted_json_rows(values: object) -> list:
    if not isinstance(values, list):
        return []
    return [
        _sorted_json_mapping(row) if isinstance(row, dict) else row for row in values
    ]


def _sorted_parameter_overrides(
    overrides: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    return {
        designator: dict(sorted(parameters.items()))
        for designator, parameters in sorted(overrides.items())
    }


def _design_json_sheet_number_value(sheet_number: str) -> int | str:
    if _CANONICAL_DECIMAL_RE.fullmatch(sheet_number):
        return int(sheet_number)
    return sheet_number


def _resolve_component_value_from_parameters(
    *,
    base_value: str,
    parameters: dict[str, str],
    project_parameters: dict[str, str] | None = None,
) -> str:
    """
    Resolve a component display value from an effective parameter dictionary.
    """
    comment = _lookup_case_insensitive(parameters, "Comment")
    if not comment:
        return base_value
    if not comment.startswith("="):
        return comment

    expr = comment[1:]
    if "+" not in expr and "'" not in expr:
        if expr.lower() == "value":
            return _lookup_case_insensitive(parameters, "Value") or base_value
        resolved = _lookup_case_insensitive(parameters, expr)
        if resolved is not None:
            return resolved
        if project_parameters:
            resolved = _lookup_case_insensitive(project_parameters, expr)
            if resolved is not None:
                return resolved
        return base_value

    expression_parameters: dict[str, str] = {}
    if project_parameters:
        expression_parameters.update(project_parameters)
    expression_parameters.update(parameters)
    expression_parameters.setdefault("Value", base_value)
    return _evaluate_altium_expression(expr, expression_parameters)


@public_api
@dataclass
class AltiumDesign:
    """
    Composed Altium design model.

    Unified entry point for all design analysis operations.

        # From single schematic
        design = AltiumDesign.from_schdoc("schematic.SchDoc")

        # Get netlist
        netlist = design.to_netlist()

        components = design.to_bom()
        variant_components = design.to_bom(variant="V1")
    """

    project: AltiumPrjPcb | None = None
    schdocs: list[AltiumSchDoc] = field(default_factory=list)
    _netlist: Netlist | None = None
    _compiled_design: AltiumCompiledDesign | None = None
    _options: NetlistOptions | None = None

    # Lazy-loaded PcbDoc for pick-and-place and PCB view operations.
    _pcbdoc: AltiumPcbDoc | None = field(default=None, repr=False)
    _pcbdoc_loaded: bool = field(default=False, repr=False)
    _pcbdoc_cache: dict[str, AltiumPcbDoc] = field(default_factory=dict, repr=False)

    @classmethod
    def from_prjpcb(cls, path: Path | str) -> AltiumDesign:
        """
        Load design from PrjPcb project file.

                Loads compile-participating SchDoc files from durable project metadata.

                Args:
                    path: Path to .PrjPcb file

                Returns:
                    AltiumDesign with project and all schematics loaded
        """
        from .altium_netlist_options import NetlistOptions
        from .altium_prjpcb import AltiumPrjPcb
        from .altium_schdoc import AltiumSchDoc

        path = Path(path)
        project = AltiumPrjPcb(path)

        options = NetlistOptions.from_prjpcb(project)
        schdoc_paths = project.get_reachable_schdoc_paths()
        schdocs = [AltiumSchDoc(schdoc_path) for schdoc_path in schdoc_paths]
        effective_scope = cls(
            project=project,
            schdocs=schdocs,
            _options=options,
        )._resolve_design_effective_scope(options)
        if effective_scope in {"HIERARCHICAL", "STRICT_HIERARCHICAL"}:
            saved_structure_paths = project.get_saved_structure_schdoc_paths()
            if saved_structure_paths:
                loaded_paths = {schdoc_path.resolve() for schdoc_path in schdoc_paths}
                for schdoc_path in saved_structure_paths:
                    resolved_path = schdoc_path.resolve()
                    if resolved_path not in loaded_paths:
                        loaded_paths.add(resolved_path)
                        schdoc_paths.append(schdoc_path)
                schdocs = [AltiumSchDoc(schdoc_path) for schdoc_path in schdoc_paths]
        else:
            all_schdoc_paths = project.get_schdoc_paths()
            if [path.resolve() for path in all_schdoc_paths] != [
                path.resolve() for path in schdoc_paths
            ]:
                schdocs = [AltiumSchDoc(schdoc_path) for schdoc_path in all_schdoc_paths]

        # Sheet parameters are merged so later sheets can override earlier ones.
        sheet_params = {}
        for schdoc in schdocs:
            sheet_params.update(schdoc.get_parameter_dict())
        options.sheet_parameters = sheet_params

        return cls(project=project, schdocs=schdocs, _options=options)

    @classmethod
    def from_schdoc(cls, path: Path | str) -> AltiumDesign:
        """
        Load design from single SchDoc (no project).

                Args:
                    path: Path to .SchDoc file

                Returns:
                    AltiumDesign with single schematic
        """
        from .altium_schdoc import AltiumSchDoc

        path = Path(path)
        schdoc = AltiumSchDoc(path)

        return cls(project=None, schdocs=[schdoc])

    @classmethod
    def from_pcbdoc(cls, path: Path | str) -> AltiumDesign:
        """
        Load design from a single PcbDoc (no project context).
        """
        from .altium_pcbdoc import AltiumPcbDoc

        pcb_path = Path(path)
        pcbdoc = AltiumPcbDoc.from_file(pcb_path)
        cache_key = str(pcb_path.resolve())
        design = cls(project=None, schdocs=[])
        design._pcbdoc = pcbdoc
        design._pcbdoc_loaded = True
        design._pcbdoc_cache[cache_key] = pcbdoc
        return design

    def compile(self, *, force: bool = False) -> AltiumCompiledDesign:
        """
        Compile this design into the beta compiled schematic model.

        Args:
            force: Rebuild the cached compiled model when True

        Returns:
            Compiled schematic design with logical documents, physical sheet
            rows, components, options, annotation state, nets, and diagnostics.
        """
        if not self.schdocs:
            raise ValueError("AltiumDesign.compile() requires at least one schematic document")
        if force:
            self._compiled_design = None
            self._netlist = None
        if self._compiled_design is None:
            from .altium_design_compiler import compile_design

            self._compiled_design = compile_design(self)
        return self._compiled_design

    def to_netlist(self) -> Netlist:
        """
        Generate unified netlist (cached).

                Returns:
                    Netlist object with all nets and components
        """
        if self._netlist is None:
            self._compile_cached_netlist()
        if self._netlist is None:
            raise RuntimeError("Netlist compilation did not produce a netlist")
        return self._netlist

    def _compile_cached_netlist(self) -> None:
        """
        Compile and cache the design netlist from the compiled design model.
        """
        if self._netlist is not None:
            return

        compiled = self.compile()
        self._netlist = compiled.to_netlist()
        from .altium_compiled_design_netlist import compiled_design_schematic_hierarchy

        self._netlist.schematic_hierarchy = compiled_design_schematic_hierarchy(
            compiled,
            self.schdocs,
        )

    def to_json(
        self,
        include_indexes: bool = True,
        *,
        include_compile_metadata: bool = False,
    ) -> dict:
        """
        Serialize design state to JSON-compatible dict.

                The returned format is the package-owned design contract with
                project metadata, enriched components, optional PCB-backed
                pick-and-place placements, and compiled nets.

                Args:
                    include_indexes: If True, include pre-computed lookup indexes
                    include_compile_metadata: If True, include low-level compile
                        summary/options/annotation state and diagnostics. The
                        default keeps the user-facing design projection compact.

                Returns:
                    JSON-compatible dict with design data
        """
        return self._design_json_from_netlist(
            self.to_netlist(),
            include_indexes,
            include_compile_metadata=include_compile_metadata,
        )

    def to_physical_ir(
        self,
        physical_page_id: str,
        project_parameters: dict[str, str] | None = None,
        *,
        profile: str = "onscreen",
        render_options: "SchSvgRenderOptions | None" = None,
    ) -> "SchGeometryDocument":
        """
        Render one compiled physical schematic page to geometry IR.

        The logical SchDoc geometry is reused, but component designator text is
        resolved through the compiled physical page before measurement and IR
        emission. This is the project-level rendering path for repeated sheets
        and instantiated channels.
        """
        compiled = self.compile()
        physical = self._resolve_physical_document(compiled, physical_page_id)
        schdoc = self._schdoc_for_physical_document(compiled, physical)
        designator_overrides = self._physical_designator_text_overrides(
            compiled,
            physical,
            schdoc,
        )
        effective_project_parameters = project_parameters
        if effective_project_parameters is None and self.project is not None:
            effective_project_parameters = dict(self.project.parameters)

        document = schdoc.to_ir(
            project_parameters=effective_project_parameters,
            profile=profile,
            render_options=render_options,
            designator_text_overrides=designator_overrides,
        )
        runtime_image_hrefs = getattr(document, "_runtime_image_hrefs", None)
        render_hints = dict(document.render_hints or {})
        render_hints["physical_page_id"] = physical.id
        render_hints["physical_source_sheet"] = physical.file_name
        render_hints["physical_designator_text_override_count"] = len(
            designator_overrides
        )
        extras = dict(document.extras or {})
        extras["physical_page"] = self._physical_page_render_metadata(physical)
        if designator_overrides:
            extras["physical_designator_text_overrides"] = dict(
                sorted(designator_overrides.items())
            )

        physical_document = replace(
            document,
            document_id=physical.id,
            source_path=physical.source_path or document.source_path,
            render_hints=render_hints,
            extras=extras,
        )
        if isinstance(runtime_image_hrefs, dict):
            object.__setattr__(
                physical_document,
                "_runtime_image_hrefs",
                runtime_image_hrefs,
            )
        return physical_document

    def to_physical_svg(
        self,
        physical_page_id: str,
        *,
        include_border: bool = True,
        scale: float = 1.0,
        options: "SchSvgRenderOptions | None" = None,
        project_parameters: dict[str, str] | None = None,
        wrap_components: bool = False,
    ) -> str:
        """
        Render one compiled physical schematic page to SVG.

        `AltiumSchDoc.to_svg()` remains the logical-sheet renderer. This method
        is the project-level physical renderer for design review consumers that
        need resolved channel/repeated-sheet designators.
        """
        from .altium_sch_geometry_renderer import (
            SchGeometrySvgRenderOptions,
            SchGeometrySvgRenderer,
        )
        from .altium_sch_svg_renderer import SchSvgRenderOptions

        del wrap_components
        if abs(scale - 1.0) > 1e-9:
            raise ValueError("Schematic IR SVG rendering currently requires scale=1.0")

        render_options = options if options is not None else SchSvgRenderOptions()
        ir_profile = (
            "oracle" if render_options.truncate_font_size_for_baseline else "onscreen"
        )
        document = self.to_physical_ir(
            physical_page_id,
            project_parameters=project_parameters,
            profile=ir_profile,
            render_options=render_options,
        )
        runtime_image_hrefs = getattr(document, "_runtime_image_hrefs", None)

        if not include_border:
            document = replace(
                document,
                records=[
                    record
                    for record in document.records
                    if str(getattr(record, "kind", "") or "") != "sheet"
                ],
                workspace_background_color=None,
            )
            if isinstance(runtime_image_hrefs, dict):
                object.__setattr__(
                    document,
                    "_runtime_image_hrefs",
                    runtime_image_hrefs,
                )

        return SchGeometrySvgRenderer(
            SchGeometrySvgRenderOptions(
                include_workspace_background=include_border,
                text_mode=(
                    "native_svg_export"
                    if render_options.truncate_font_size_for_baseline
                    else "onscreen"
                ),
                compile_mask_render_mode=render_options.compile_mask_render_mode,
                text_as_polygons=render_options.text_as_polygons,
                polygon_text_tolerance=render_options.polygon_text_tolerance,
                include_view_box=render_options.include_view_box,
            )
        ).render(document)

    @staticmethod
    def _physical_page_render_metadata(physical_document: Any) -> dict:
        return {
            "id": physical_document.id,
            "logical_document_id": physical_document.logical_document_id,
            "source_sheet": physical_document.file_name,
            "source_path": physical_document.source_path,
            "physical_instance_path": physical_document.physical_instance_path,
            "physical_instance_unique_id": (
                physical_document.physical_instance_unique_id
            ),
            "channel_index": physical_document.channel_index,
            "channel_prefix": physical_document.channel_prefix or "",
            "channel_alpha": physical_document.channel_alpha or "",
            "room_name": physical_document.room_name,
            "parent_id": physical_document.parent_id,
            "parent_sheet_symbol_id": physical_document.parent_sheet_symbol_id,
            "sheet_number": physical_document.sheet_number,
            "document_number": physical_document.document_number,
        }

    @staticmethod
    def _path_identity(path_value: object) -> str:
        if not path_value:
            return ""
        try:
            return str(Path(str(path_value)).resolve()).lower()
        except OSError:
            return str(Path(str(path_value))).lower()

    def _resolve_physical_document(
        self,
        compiled: AltiumCompiledDesign,
        physical_page_id: str,
    ) -> Any:
        requested = str(physical_page_id or "").strip()
        if not requested:
            raise ValueError("physical_page_id is required")
        for document in compiled.physical_documents:
            identifiers = {
                str(value)
                for value in (
                    document.id,
                    document.physical_instance_path,
                    document.physical_instance_unique_id,
                )
                if value
            }
            if requested in identifiers:
                return document
        available = ", ".join(
            document.id for document in compiled.physical_documents[:10]
        )
        if len(compiled.physical_documents) > 10:
            available += ", ..."
        raise ValueError(
            f"unknown physical_page_id {physical_page_id!r}; available ids: {available}"
        )

    def _schdoc_for_physical_document(
        self,
        compiled: AltiumCompiledDesign,
        physical_document: Any,
    ) -> AltiumSchDoc:
        logical_by_id = {
            document.id: document for document in compiled.logical_documents
        }
        logical = logical_by_id.get(physical_document.logical_document_id)
        path_candidates = {
            self._path_identity(getattr(physical_document, "source_path", "")),
        }
        if logical is not None:
            path_candidates.add(self._path_identity(getattr(logical, "source_path", "")))
        path_candidates.discard("")
        for schdoc in self.schdocs:
            if schdoc.filepath and self._path_identity(schdoc.filepath) in path_candidates:
                return schdoc

        file_name = str(
            getattr(logical, "file_name", "")
            if logical is not None
            else getattr(physical_document, "file_name", "")
        )
        matches = [
            schdoc
            for schdoc in self.schdocs
            if schdoc.filepath and schdoc.filepath.name == file_name
        ]
        if len(matches) == 1:
            return matches[0]
        raise ValueError(
            "could not resolve source SchDoc for physical page "
            f"{physical_document.id!r}"
        )

    @staticmethod
    def _source_designator_record_id(component_record: object) -> str:
        finder = getattr(component_record, "_find_designator_record", None)
        if not callable(finder):
            return ""
        designator_record = finder()
        designator_unique_id = str(
            getattr(designator_record, "unique_id", "") or ""
        )
        if designator_unique_id:
            return designator_unique_id
        component_unique_id = str(getattr(component_record, "unique_id", "") or "")
        if component_unique_id:
            return f"component:{component_unique_id}:designator"
        return ""

    def _physical_designator_text_overrides(
        self,
        compiled: AltiumCompiledDesign,
        physical_document: Any,
        schdoc: AltiumSchDoc,
    ) -> dict[str, str]:
        designator_record_by_component_id: dict[str, str] = {}
        designator_record_by_logical_designator: dict[str, str] = {}
        for component_info in schdoc.get_components():
            component_record = component_info.record
            designator_record_id = self._source_designator_record_id(component_record)
            if not designator_record_id:
                continue
            component_id = str(getattr(component_record, "unique_id", "") or "")
            if component_id:
                designator_record_by_component_id[component_id] = designator_record_id
            logical_designator = str(component_info.designator or "")
            if logical_designator:
                designator_record_by_logical_designator.setdefault(
                    logical_designator,
                    designator_record_id,
                )

        overrides: dict[str, str] = {}
        for component in compiled.components:
            if component.physical_document_id != physical_document.id:
                continue
            resolved_designator = (
                component.display_designator or component.physical_designator
            )
            if not resolved_designator:
                continue
            designator_record_id = designator_record_by_component_id.get(
                component.source_object_id
            )
            if not designator_record_id:
                designator_record_id = designator_record_by_logical_designator.get(
                    component.logical_designator
                )
            if designator_record_id:
                overrides[designator_record_id] = resolved_designator
        return overrides

    def _design_json_from_netlist(
        self,
        netlist: Netlist,
        include_indexes: bool,
        *,
        include_compile_metadata: bool,
    ) -> dict:
        """
        Build enriched design JSON around an already-generated netlist.
        """

        from .altium_netlist_options import NetlistOptions

        options = self._options or NetlistOptions()
        compiled = self.compile()

        options_data = {
            "net_identifier_scope": options.net_identifier_scope.name,
            "allow_ports_to_name_nets": options.allow_ports_to_name_nets,
            "allow_sheet_entries_to_name_nets": options.allow_sheet_entries_to_name_nets,
            "allow_single_pin_nets": options.allow_single_pin_nets,
            "append_sheet_numbers_to_local_nets": options.append_sheet_numbers_to_local_nets,
            "power_port_names_take_priority": options.power_port_names_take_priority,
            "higher_level_names_take_priority": options.higher_level_names_take_priority,
            "auto_sheet_numbering": options.auto_sheet_numbering,
        }

        sheets_data = self._build_sheets_data(options)
        project_data = self._build_project_data()
        variants_data = self._build_variants_data()
        active_variant_name = self._active_variant_name()
        active_variant_dnp = self._active_variant_dnp_designators(active_variant_name)
        has_repeated_physical_instances = self._has_repeated_physical_instances(
            compiled
        )
        comp_data_map = self._build_component_data_map(
            netlist,
            compiled if has_repeated_physical_instances else None,
        )
        components_data = []
        if has_repeated_physical_instances:
            components_data = self._build_compiled_components_data(
                compiled,
                active_variant_dnp=active_variant_dnp,
            )
        if not components_data:
            components_data = []
            for comp in netlist.components:
                is_dnp = comp.designator in active_variant_dnp
                data = comp_data_map.get(comp.designator, {})
                components_data.append(
                    self._enrich_component(
                        comp,
                        sheet=data.get("sheet", ""),
                        pin_count=data.get("pin_count", 0),
                        svg_id=data.get("svg_id", ""),
                        component_context={
                            **data,
                            "dnp": is_dnp,
                            "fitted": not is_dnp,
                        },
                    )
                )
        physical_pages_data = self._build_physical_pages_data(
            compiled,
            active_variant_dnp=active_variant_dnp,
        )

        result = {
            "schema": DESIGN_JSON_SCHEMA,
            "generator": DESIGN_JSON_GENERATOR,
            "project": project_data,
            "variants": variants_data,
            "options": options_data,
        }

        if include_compile_metadata:
            result["compile"] = self._build_compile_data(compiled)
            result["diagnostics"] = self._compiled_design_diagnostics(compiled)

        result.update(
            {
                "sheets": sheets_data,
                "components": components_data,
                "schematic_hierarchy": self._build_schematic_hierarchy_data(netlist),
                "physical_pages": physical_pages_data,
            }
        )

        pnp_data = self._build_pnp_data()
        if pnp_data is not None:
            result["pnp"] = pnp_data

        if has_repeated_physical_instances:
            nets_data = self._build_compiled_nets_data(compiled)
        else:
            nets_data = self._build_legacy_json_nets_data(netlist, compiled)
        result["nets"] = nets_data

        if include_indexes:
            result["indexes"] = self._build_indexes(
                components_data,
                nets_data,
                physical_pages_data,
            )

        return result

    @staticmethod
    def _build_compile_data(compiled: AltiumCompiledDesign) -> dict:
        """
        Build compact compiled-design metadata for the public design JSON.
        """
        return {
            "schema": compiled.schema,
            "summary": compiled.summary.to_dict(),
            "options": compiled.options.to_dict(),
            "annotation": compiled.annotation.to_dict(),
            "stats": dict(sorted(compiled.compile.items())),
        }

    @staticmethod
    def _compiled_design_diagnostics(
        compiled: AltiumCompiledDesign,
    ) -> list[dict]:
        """
        Return compile diagnostics from every public compiled-design owner.
        """
        rows: list[dict] = []

        def add_rows(
            owner_kind: str,
            owner_id: str,
            diagnostics: object,
        ) -> None:
            for diagnostic in diagnostics or ():
                row = diagnostic.to_dict()
                row["owner_kind"] = owner_kind
                if owner_id:
                    row["owner_id"] = owner_id
                rows.append(row)

        add_rows("compile", "", compiled.diagnostics)
        add_rows("annotation", "", compiled.annotation.diagnostics)
        for document in compiled.logical_documents:
            add_rows("logical_document", document.id, document.diagnostics)
        for document in compiled.physical_documents:
            add_rows("physical_document", document.id, document.diagnostics)
        for symbol in compiled.sheet_symbols:
            add_rows("sheet_symbol", symbol.id, symbol.diagnostics)
        for component in compiled.components:
            add_rows("component", component.id, component.diagnostics)
        for net in compiled.nets:
            add_rows("net", net.id, net.diagnostics)
        return rows

    @staticmethod
    def _has_repeated_physical_instances(compiled: AltiumCompiledDesign) -> bool:
        physical_count_by_logical_id: dict[str, int] = {}
        for document in compiled.physical_documents:
            logical_id = str(document.logical_document_id or "")
            if not logical_id:
                continue
            physical_count_by_logical_id[logical_id] = (
                physical_count_by_logical_id.get(logical_id, 0) + 1
            )
        return any(count > 1 for count in physical_count_by_logical_id.values())

    def _build_legacy_json_nets_data(
        self,
        netlist: Netlist,
        compiled: AltiumCompiledDesign,
    ) -> list[dict]:
        compiled_flat_by_id = {
            net.id: net for net in compiled.nets if net.scope == "compiled_flat"
        }
        nets_data = netlist.to_json()["nets"]
        for index, net_data in enumerate(nets_data, start=1):
            compiled_net = compiled_flat_by_id.get(str(net_data.get("uid") or ""))
            if compiled_net is not None:
                name_sources = self._compiled_net_name_sources(compiled_net)
                aliases = self._design_net_aliases(
                    str(net_data.get("name") or ""),
                    list(net_data.get("aliases") or []),
                    name_sources,
                )
                net_data["aliases"] = aliases
                if len(name_sources) > 1:
                    net_data["name_sources"] = name_sources
            net_data["uid"] = f"{index:012x}"
        return nets_data

    def _build_compiled_components_data(
        self,
        compiled: AltiumCompiledDesign,
        *,
        active_variant_dnp: set[str] | None = None,
    ) -> list[dict]:
        """
        Build top-level design JSON component rows from compiled physical rows.
        """
        from .altium_netlist_model import ComponentClassification

        physical_by_id = {
            document.id: document for document in compiled.physical_documents
        }
        flat_nets = [net for net in compiled.nets if net.scope == "compiled_flat"]
        component_to_nets = self._compiled_component_to_nets(flat_nets)
        dnp_set = active_variant_dnp or set()
        components_data: list[dict] = []
        for component in sorted(
            compiled.components,
            key=lambda item: (
                item.physical_document_id,
                item.display_designator or item.physical_designator,
                item.id,
            ),
        ):
            designator = component.display_designator or component.physical_designator
            if not designator:
                continue
            is_dnp = designator in dnp_set
            physical = physical_by_id.get(component.physical_document_id)
            sheet = physical.file_name if physical is not None else ""
            hierarchy = self._parse_hierarchy(designator, sheet)
            classification = ComponentClassification.from_component(
                designator,
                component.pin_count,
            )
            components_data.append(
                {
                    "id": component.id,
                    "designator": designator,
                    "logical_designator": component.logical_designator,
                    "physical_designator": component.physical_designator,
                    "physical_sheet_id": component.physical_document_id,
                    "source_unique_id": component.source_object_id,
                    "source_unique_id_path": component.source_unique_id_path,
                    "compiled_component_id": component.id,
                    "svg_id": component.source_object_id,
                    "sheet": sheet,
                    "pin_count": component.pin_count,
                    "part_count": component.part_count,
                    "current_part_id": component.current_part_id,
                    "value": component.value,
                    "footprint": component.footprint,
                    "library_ref": component.lib_reference,
                    "description": component.description,
                    "design_item_id": component.design_item_id,
                    "component_kind": component.component_kind,
                    "component_kind_value": component.component_kind_value,
                    "include_in_netlist": component.include_in_netlist,
                    "exclude_from_bom": component.exclude_from_bom,
                    "dnp": is_dnp,
                    "fitted": not is_dnp,
                    "annotation_state": component.annotation_state,
                    "annotation_locked": component.annotation_locked,
                    "hierarchy": hierarchy.to_json(),
                    "classification": classification.to_json(),
                    "parameters": dict(sorted(dict(component.parameters).items())),
                    "nets": component_to_nets.get(designator, []),
                }
            )
        return components_data

    @staticmethod
    def _compiled_component_to_nets(flat_nets: list[object]) -> dict[str, list[str]]:
        component_to_nets: dict[str, set[str]] = {}
        for net in flat_nets:
            net_name = str(getattr(net, "name", "") or "")
            if not net_name:
                continue
            for terminal in getattr(net, "terminals", ()) or ():
                designator = str(getattr(terminal, "designator", "") or "")
                if not designator:
                    continue
                component_to_nets.setdefault(designator, set()).add(net_name)
        return {
            designator: sorted(nets)
            for designator, nets in sorted(component_to_nets.items())
        }

    def _build_compiled_nets_data(
        self,
        compiled: AltiumCompiledDesign,
    ) -> list[dict]:
        """
        Build top-level design JSON net rows from compiled-flat nets.
        """
        nets_data: list[dict] = []
        flat_nets = [net for net in compiled.nets if net.scope == "compiled_flat"]
        for index, net in enumerate(flat_nets, start=1):
            name_sources = self._compiled_net_name_sources(net)
            net_data = {
                "id": net.id,
                "uid": f"{index:012x}",
                "name": net.name,
                "aliases": self._design_net_aliases(
                    net.name,
                    list(net.aliases),
                    name_sources,
                ),
                "physical_document_ids": list(net.physical_document_ids),
                "terminal_count": len(net.terminals),
                "terminals": [terminal.to_dict() for terminal in net.terminals],
                "graphical": self._compiled_page_net_graphical(list(net.items)),
                "endpoint_ids": _unique_nonempty_strings(
                    [endpoint.id for endpoint in net.endpoints]
                ),
                "endpoints": [endpoint.to_dict() for endpoint in net.endpoints],
                "auto_named": net.auto_named,
                "single_pin": net.single_pin,
            }
            if len(name_sources) > 1:
                net_data["name_sources"] = name_sources
            nets_data.append(net_data)
        return nets_data

    def _build_schematic_hierarchy_data(self, netlist: Netlist) -> dict:
        """
        Build schematic hierarchy JSON for the design payload.
        """
        hierarchy = getattr(netlist, "schematic_hierarchy", None)
        if isinstance(hierarchy, dict) and hierarchy:
            return hierarchy

        from .altium_netlist_options import NetlistOptions

        options = self._options or NetlistOptions()
        effective_scope = self._resolve_design_effective_scope(options)
        return {
            "schema": SCHEMATIC_HIERARCHY_SCHEMA,
            "requested_scope": options.net_identifier_scope.name,
            "effective_scope": effective_scope,
            "documents": [
                {
                    "sheet_index": idx,
                    "filename": schdoc.filepath.name
                    if schdoc.filepath
                    else f"sheet{idx}",
                    "path": str(schdoc.filepath) if schdoc.filepath else "",
                    "is_top_level": True,
                    "metadata": {},
                }
                for idx, schdoc in enumerate(self.schdocs)
            ],
            "sheet_symbols": [],
            "hierarchy_paths": [],
            "channels": [],
            "links": [],
            "unresolved": [],
        }

    def _resolve_design_effective_scope(self, options: "NetlistOptions") -> str:
        """
        Resolve automatic scope for hierarchy metadata fallback payloads.
        """
        from .altium_prjpcb import NetIdentifierScope

        scope = options.net_identifier_scope
        if scope != NetIdentifierScope.AUTOMATIC:
            return scope.name

        has_sheet_entries = any(
            sheet_symbol.entries
            for schdoc in self.schdocs
            for sheet_symbol in schdoc.get_sheet_symbols()
        )
        if has_sheet_entries:
            return NetIdentifierScope.HIERARCHICAL.name
        if any(schdoc.get_ports() for schdoc in self.schdocs):
            return NetIdentifierScope.FLAT.name
        return NetIdentifierScope.GLOBAL.name

    def _build_pnp_data(self) -> dict | None:
        """
        Build optional PCB-backed pick-and-place data for design JSON.
        """
        pcbdoc_paths = self.get_pcbdoc_paths()
        if not pcbdoc_paths:
            return None

        position_mode = PNP_POSITION_MODE_ALTIUM_PICK_PLACE
        placements = self.to_pnp(units="mm", position_mode=position_mode)
        source_path = self._pcbdoc.filepath if self._pcbdoc else pcbdoc_paths[0]
        source_name = Path(source_path).name if source_path else pcbdoc_paths[0].name
        return {
            "units": "mm",
            "position_mode": position_mode,
            "source_pcbdoc": source_name,
            "placements": [entry.to_json() for entry in placements],
        }

    def _build_component_data_map(
        self,
        netlist: Netlist,
        compiled: AltiumCompiledDesign | None = None,
    ) -> dict[str, dict]:
        """
        Build mapping of designator -> {sheet, pin_count, svg_id}.

                Single-pass iteration over all schematics keeps downstream lookups O(1).
        """
        result: dict[str, dict] = {}
        for schdoc in self.schdocs:
            sheet_name = schdoc.filepath.name if schdoc.filepath else ""
            for comp in schdoc.get_components():
                result[comp.designator] = {
                    "sheet": sheet_name,
                    "pin_count": len(comp.pins),
                    "svg_id": comp.unique_id,
                }

        if compiled is not None:
            logical_by_id = {
                document.id: document for document in compiled.logical_documents
            }
            physical_by_id = {
                document.id: document for document in compiled.physical_documents
            }
            for component in compiled.components:
                designator = (
                    component.display_designator or component.physical_designator
                )
                if not designator:
                    continue
                if designator in result:
                    existing_physical_sheet_id = str(
                        result[designator].get("physical_sheet_id") or ""
                    )
                    if (
                        existing_physical_sheet_id
                        and existing_physical_sheet_id != component.physical_document_id
                    ):
                        result[designator]["ambiguous_physical_designator"] = True
                        result[designator]["svg_id"] = ""
                        result[designator]["source_unique_id"] = ""
                        result[designator]["source_unique_id_path"] = ""
                        continue
                physical = physical_by_id.get(component.physical_document_id)
                logical = logical_by_id.get(component.logical_document_id)
                result[designator] = {
                    "sheet": physical.file_name
                    if physical is not None
                    else logical.file_name
                    if logical is not None
                    else "",
                    "pin_count": component.pin_count,
                    "svg_id": component.source_object_id,
                    "source_unique_id": component.source_object_id,
                    "source_unique_id_path": component.source_unique_id_path,
                    "logical_designator": component.logical_designator,
                    "physical_designator": component.physical_designator,
                    "physical_sheet_id": component.physical_document_id,
                    "compiled_component_id": component.id,
                }

        # Fallback for multi-channel components not directly in any SchDoc:
        # count unique pins from netlist terminals
        for comp in netlist.components:
            if comp.designator not in result:
                pins = set()
                for net in netlist.nets:
                    for terminal in net.terminals:
                        if terminal.designator == comp.designator:
                            pins.add(terminal.pin)
                result[comp.designator] = {
                    "sheet": "",
                    "pin_count": len(pins),
                    "svg_id": "",
                }

        return result

    @staticmethod
    def _source_component_rendered_pin_svg_ids(source_component: object) -> dict[str, str]:
        source_record = getattr(source_component, "record", source_component)
        show_hidden_pins = bool(
            getattr(source_component, "show_hidden_pins", False)
            or getattr(source_record, "show_hidden_pins", False)
        )
        pin_svg_ids: dict[str, str] = {}
        for pin in getattr(source_component, "pins", ()) or ():
            pin_record = getattr(pin, "record", pin)
            hidden = bool(
                getattr(pin, "hidden", False)
                or getattr(pin, "is_hidden", False)
                or getattr(pin_record, "hidden", False)
                or getattr(pin_record, "is_hidden", False)
            )
            if hidden and not show_hidden_pins:
                continue
            designator = str(
                getattr(pin, "designator", "")
                or getattr(pin_record, "designator", "")
                or ""
            )
            unique_id = str(
                getattr(pin, "unique_id", "")
                or getattr(pin_record, "unique_id", "")
                or ""
            )
            if designator and unique_id:
                pin_svg_ids[designator] = unique_id
        return pin_svg_ids

    def _build_physical_pages_data(
        self,
        compiled: AltiumCompiledDesign,
        *,
        active_variant_dnp: set[str] | None = None,
    ) -> list[dict]:
        """
        Build the user-facing physical page index for design JSON consumers.

        A source SVG id is only a logical identity. Repeated/channel sheets need
        the physical page id plus the source SVG id to identify one rendered
        component instance.
        """
        logical_by_id = {
            document.id: document for document in compiled.logical_documents
        }
        source_pin_svg_ids_by_component: dict[tuple[str, str], dict[str, str]] = {}

        def merge_source_pin_svg_ids(key: tuple[str, str], pin_svg_ids: dict[str, str]) -> None:
            existing = source_pin_svg_ids_by_component.setdefault(key, {})
            existing.update(pin_svg_ids)

        for schdoc in self.schdocs:
            sheet_name = schdoc.filepath.name if schdoc.filepath else ""
            for source_component in schdoc.get_components():
                pin_svg_ids = self._source_component_rendered_pin_svg_ids(
                    source_component
                )
                if not pin_svg_ids:
                    continue
                source_unique_id = str(getattr(source_component, "unique_id", "") or "")
                if source_unique_id:
                    merge_source_pin_svg_ids((sheet_name, source_unique_id), pin_svg_ids)
                source_designator = str(
                    getattr(source_component, "designator", "") or ""
                )
                if source_designator:
                    merge_source_pin_svg_ids((sheet_name, source_designator), pin_svg_ids)
        parent_sheet_symbol_by_child_physical_id = {
            symbol.child_physical_document_id: symbol
            for symbol in compiled.physical_sheet_symbols
        }
        dnp_set = active_variant_dnp or set()
        components_by_page: dict[str, list[dict]] = {}
        designator_page: dict[str, str] = {}
        pin_svg_ids_by_page_designator_pin: dict[tuple[str, str, str], str] = {}
        for component in sorted(
            compiled.components,
            key=lambda item: (
                item.physical_document_id,
                item.display_designator or item.physical_designator,
                item.id,
            ),
        ):
            designator = component.display_designator or component.physical_designator
            if not designator:
                continue
            logical = logical_by_id.get(component.logical_document_id)
            source_sheet = logical.file_name if logical is not None else ""
            source_pin_svg_ids = (
                source_pin_svg_ids_by_component.get(
                    (source_sheet, component.source_object_id)
                )
                or source_pin_svg_ids_by_component.get(
                    (source_sheet, component.logical_designator)
                )
                or {}
            )
            for pin, svg_id in source_pin_svg_ids.items():
                pin_svg_ids_by_page_designator_pin[
                    (component.physical_document_id, designator, pin)
                ] = svg_id
            is_dnp = designator in dnp_set
            designator_page[designator] = component.physical_document_id
            components_by_page.setdefault(component.physical_document_id, []).append(
                {
                    "id": component.id,
                    "designator": designator,
                    "physical_designator": component.physical_designator,
                    "logical_designator": component.logical_designator,
                    "source_unique_id": component.source_object_id,
                    "source_unique_id_path": component.source_unique_id_path,
                    "svg_id": component.source_object_id,
                    "pin_count": component.pin_count,
                    "value": component.value,
                    "library_ref": component.lib_reference,
                    "component_kind": component.component_kind,
                    "dnp": is_dnp,
                    "fitted": not is_dnp,
                }
            )

        flat_nets = [net for net in compiled.nets if net.scope == "compiled_flat"]
        nets_by_physical_document_id: dict[str, list[object]] = {}
        items_by_net_and_physical_document_id: dict[
            tuple[str, str],
            list[object],
        ] = {}
        net_name_sources_by_id: dict[str, list[dict]] = {}
        for net in flat_nets:
            net_name_sources_by_id[net.id] = self._compiled_net_name_sources(net)
            net_physical_document_ids = {
                str(physical_document_id)
                for physical_document_id in net.physical_document_ids
                if str(physical_document_id)
            }
            for item in net.items:
                item_physical_document_id = str(item.physical_document_id or "")
                if not item_physical_document_id:
                    continue
                net_physical_document_ids.add(item_physical_document_id)
                items_by_net_and_physical_document_id.setdefault(
                    (net.id, item_physical_document_id),
                    [],
                ).append(item)
            for physical_document_id in net_physical_document_ids:
                nets_by_physical_document_id.setdefault(
                    physical_document_id,
                    [],
                ).append(net)

        pages: list[dict] = []
        for document in sorted(compiled.physical_documents, key=lambda item: item.ordinal):
            logical = logical_by_id.get(document.logical_document_id)
            parent_sheet_symbol = parent_sheet_symbol_by_child_physical_id.get(
                document.id
            )
            page_components = components_by_page.get(document.id, [])
            page_designators = {
                str(component.get("designator") or "")
                for component in page_components
            }
            page_nets = []
            for net in nets_by_physical_document_id.get(document.id, []):
                page_terminal_objects = [
                    terminal
                    for terminal in net.terminals
                    if terminal.designator in page_designators
                    or designator_page.get(terminal.designator) == document.id
                ]
                terminals = [terminal.to_dict() for terminal in page_terminal_objects]
                items = items_by_net_and_physical_document_id.get(
                    (net.id, document.id),
                    [],
                )
                endpoints = [
                    endpoint
                    for endpoint in net.endpoints
                    if endpoint.designator in page_designators
                    or endpoint.parent_id in {document.source_path, document.file_name}
                ]
                name_sources = net_name_sources_by_id[net.id]
                graphical = self._compiled_page_net_graphical(items)
                fallback_pins = []
                for terminal in page_terminal_objects:
                    svg_id = pin_svg_ids_by_page_designator_pin.get(
                        (document.id, terminal.designator, terminal.pin)
                    )
                    if not svg_id:
                        continue
                    fallback_pins.append(
                        {
                            "designator": terminal.designator,
                            "pin": terminal.pin,
                            "svg_id": svg_id,
                        }
                    )
                if fallback_pins:
                    merged_pins = [
                        *graphical["pins"],
                        *fallback_pins,
                    ]
                    graphical["pins"] = sorted(
                        {
                            (
                                pin["designator"],
                                pin["pin"],
                                pin["svg_id"],
                            ): pin
                            for pin in merged_pins
                        }.values(),
                        key=lambda item: (
                            item.get("designator", ""),
                            item.get("pin", ""),
                            item.get("svg_id", ""),
                        ),
                    )
                    graphical["object_ids"] = sorted(
                        _unique_nonempty_strings(
                            [
                                *graphical["object_ids"],
                                *[pin["svg_id"] for pin in fallback_pins],
                            ]
                        )
                    )
                page_nets.append(
                    {
                        "id": net.id,
                        "name": net.name,
                        "aliases": self._design_net_aliases(
                            net.name,
                            list(net.aliases),
                            name_sources,
                        ),
                        "name_sources": name_sources,
                        "terminal_count": len(terminals),
                        "terminals": terminals,
                        "graphical": graphical,
                        "endpoint_ids": _unique_nonempty_strings(
                            [endpoint.id for endpoint in endpoints]
                        ),
                    }
                )
            pages.append(
                {
                    "id": document.id,
                    "logical_document_id": document.logical_document_id,
                    "source_sheet": document.file_name,
                    "source_path": document.source_path,
                    "sheet_index": logical.ordinal if logical is not None else None,
                    "compiled_sheet_index": document.ordinal,
                    "physical_instance_path": document.physical_instance_path,
                    "physical_instance_unique_id": (
                        document.physical_instance_unique_id
                    ),
                    "is_top_level": document.parent_id is None,
                    "channel_index": document.channel_index,
                    "channel_prefix": document.channel_prefix or "",
                    "channel_alpha": document.channel_alpha or "",
                    "room_name": document.room_name,
                    "parent_id": document.parent_id,
                    "parent_sheet_symbol_id": document.parent_sheet_symbol_id,
                    "parent_sheet_symbol": self._physical_page_parent_sheet_symbol(
                        parent_sheet_symbol
                    ),
                    "sheet_number": document.sheet_number,
                    "document_number": document.document_number,
                    "components": page_components,
                    "nets": page_nets,
                }
            )
        return pages

    @staticmethod
    def _physical_page_parent_sheet_symbol(symbol: object | None) -> dict | None:
        if symbol is None:
            return None
        return {
            "id": symbol.id,
            "source_object_id": symbol.source_object_id,
            "owner_physical_document_id": symbol.owner_physical_document_id,
            "logical_designator": symbol.logical_designator,
            "physical_designator": symbol.physical_designator,
            "sheet_symbol_file_name": symbol.sheet_symbol_file_name,
            "entry_count": symbol.entry_count,
        }

    @staticmethod
    def _compiled_page_net_graphical(items: list[object]) -> dict:
        pins: list[dict] = []
        labels: list[str] = []
        power_ports: list[str] = []
        ports: list[str] = []
        sheet_entries: list[str] = []
        object_ids: list[str] = []
        for item in items:
            object_id = str(
                getattr(item, "element_id", "")
                or getattr(item, "object_id", "")
                or ""
            )
            if not object_id:
                continue
            object_ids.append(object_id)
            kind = str(getattr(item, "kind", "") or "")
            if kind == "pin":
                pins.append(
                    {
                        "designator": str(getattr(item, "designator", "") or ""),
                        "pin": str(getattr(item, "pin", "") or ""),
                        "svg_id": object_id,
                    }
                )
            elif kind == "net_label":
                labels.append(object_id)
            elif kind == "power_port":
                power_ports.append(object_id)
            elif kind in {"port", "harness_port"}:
                ports.append(object_id)
            elif kind in {"sheet_entry", "harness_entry"}:
                sheet_entries.append(object_id)
        return {
            "pins": sorted(
                pins,
                key=lambda item: (
                    item.get("designator", ""),
                    item.get("pin", ""),
                    item.get("svg_id", ""),
                ),
            ),
            "labels": sorted(_unique_nonempty_strings(labels)),
            "power_ports": sorted(_unique_nonempty_strings(power_ports)),
            "ports": sorted(_unique_nonempty_strings(ports)),
            "sheet_entries": sorted(_unique_nonempty_strings(sheet_entries)),
            "object_ids": sorted(_unique_nonempty_strings(object_ids)),
        }

    @staticmethod
    def _compiled_net_name_sources(compiled_net: object) -> list[dict]:
        rows: list[dict] = []
        seen: set[tuple[str, str, str, str, str, str]] = set()

        def add(
            *,
            name: str,
            role: str,
            source: str,
            physical_document_id: str = "",
            object_id: str = "",
            graphical_id: str = "",
        ) -> None:
            clean = str(name or "").strip()
            if not clean:
                return
            key = (
                clean,
                role,
                source,
                physical_document_id,
                object_id,
                graphical_id,
            )
            if key in seen:
                return
            seen.add(key)
            row: dict[str, object] = {
                "name": clean,
                "role": role,
                "source": source,
            }
            if physical_document_id:
                row["physical_document_id"] = physical_document_id
            if object_id:
                row["object_id"] = object_id
            if graphical_id:
                row["graphical_id"] = graphical_id
            rows.append(row)

        winner = str(getattr(compiled_net, "name", "") or "")
        add(name=winner, role="winner", source="compiled_net")
        original_name = str(getattr(compiled_net, "original_name", "") or "")
        add(name=original_name, role="alias", source="original_name")
        override_name = str(getattr(compiled_net, "override_name", "") or "")
        add(name=override_name, role="alias", source="override_name")
        for alias in getattr(compiled_net, "aliases", ()) or ():
            add(name=str(alias), role="alias", source="compiled_alias")
        net_items = [*(getattr(compiled_net, "items", ()) or ())]
        for item in net_items:
            add(
                name=str(getattr(item, "name", "") or ""),
                role="candidate",
                source=str(getattr(item, "kind", "") or "net_item"),
                physical_document_id=str(
                    getattr(item, "physical_document_id", "") or ""
                ),
                object_id=str(getattr(item, "object_id", "") or ""),
                graphical_id=str(
                    getattr(item, "element_id", "")
                    or getattr(item, "object_id", "")
                    or ""
                ),
            )
        for endpoint in getattr(compiled_net, "endpoints", ()) or ():
            add(
                name=str(getattr(endpoint, "name", "") or ""),
                role="candidate",
                source=str(getattr(endpoint, "role", "") or "endpoint"),
                object_id=str(getattr(endpoint, "object_id", "") or ""),
                graphical_id=str(
                    getattr(endpoint, "element_id", "")
                    or getattr(endpoint, "object_id", "")
                    or ""
                ),
            )
        return rows

    @staticmethod
    def _design_net_aliases(
        net_name: str,
        aliases: list[str],
        name_sources: list[dict],
    ) -> list[str]:
        values = list(aliases)
        for source in name_sources:
            source_name = str(source.get("name") or "")
            if source_name != net_name:
                values.append(source_name)
        return sorted(_unique_nonempty_strings(values))

    def _build_sheets_data(self, options: NetlistOptions) -> list[dict]:
        """
        Build sheet information for JSON output.
        """
        sheet_numbers = self._resolve_sheet_numbers(options)
        sheets = []
        for idx, schdoc in enumerate(self.schdocs):
            filename = schdoc.filepath.name if schdoc.filepath else f"sheet{idx}"
            sheet_number = sheet_numbers.get(filename) or str(idx + 1)
            sheets.append(
                {
                    "filename": filename,
                    "sheet_number": _design_json_sheet_number_value(sheet_number),
                }
            )
        return sheets

    def _build_project_data(self) -> dict:
        """
        Build project information for JSON output.
        """
        if not self.project:
            return {
                "name": None,
                "filename": None,
                "parameters": {},
            }

        return {
            "name": self.project.filepath.stem if self.project.filepath else None,
            "filename": str(self.project.filepath.name)
            if self.project.filepath
            else None,
            "current_variant": self.project.get_current_variant(),
            "parameters": dict(sorted(self.project.parameters.items())),
        }

    def _active_variant_name(self) -> str | None:
        if not self.project:
            return None
        return self.project.get_current_variant()

    def _active_variant_dnp_designators(
        self,
        variant_name: str | None = None,
    ) -> set[str]:
        if not self.project:
            return set()
        effective_variant = variant_name or self.project.get_current_variant()
        if not effective_variant:
            return set()
        variant_data = self.project.variants.get(effective_variant)
        if not variant_data:
            return set()
        return _variant_dnp_designators(variant_data)

    def _build_variants_data(self) -> list[dict]:
        """
        Build variants information for JSON output.

                Returns:
                    List of variant dicts with 'name' and 'dnp' (list of designators).
                    Empty list if no project or no variants defined.
        """
        if not self.project or not self.project.variants:
            return []

        current_variant = self._active_variant_name()
        variants_list = []
        for variant_name, variant_data in self.project.variants.items():
            dnp_designators = sorted(_variant_dnp_designators(variant_data))

            variant_entry = {
                "name": variant_name,
                "is_current": variant_name == current_variant,
                "dnp": dnp_designators,
            }
            for key in ("variations", "parameters", "param_variations"):
                values = variant_data.get(key, [])
                if values:
                    variant_entry[key] = _sorted_json_rows(values)
            parameter_overrides = _coerce_variant_parameter_overrides(variant_data)
            if parameter_overrides:
                variant_entry["parameter_overrides"] = _sorted_parameter_overrides(
                    parameter_overrides
                )
            variants_list.append(variant_entry)

        return variants_list

    def _enrich_component(
        self,
        comp: NetlistComponent,
        sheet: str,
        pin_count: int,
        svg_id: str,
        component_context: dict | None = None,
    ) -> dict:
        """
        Build enriched component data for JSON.

                Args:
                    comp: NetlistComponent from netlist
                    sheet: Source sheet filename
                    pin_count: Pre-computed pin count from _build_component_data_map()
                    svg_id: Pre-computed SVG unique_id from _build_component_data_map()

                Returns:
                    Enriched component dict with hierarchy, classification, and all parameters
        """
        from .altium_netlist_model import ComponentClassification

        # Parse channel info from designator (e.g., "R1_A" -> base="R1", channel="A")
        hierarchy = self._parse_hierarchy(comp.designator, sheet)

        # Build classification
        classification = ComponentClassification.from_component(
            comp.designator, pin_count
        )

        context = component_context or {}
        return {
            "designator": comp.designator,
            "logical_designator": context.get("logical_designator", comp.designator),
            "physical_designator": context.get("physical_designator", comp.designator),
            "physical_sheet_id": context.get("physical_sheet_id", ""),
            "ambiguous_physical_designator": bool(
                context.get("ambiguous_physical_designator", False)
            ),
            "source_unique_id": context.get("source_unique_id", svg_id),
            "source_unique_id_path": context.get("source_unique_id_path", ""),
            "compiled_component_id": context.get("compiled_component_id", ""),
            "svg_id": svg_id,
            "value": comp.value,
            "footprint": comp.footprint,
            "library_ref": comp.library_ref,
            "description": comp.description,
            "dnp": bool(context.get("dnp", False)),
            "fitted": bool(context.get("fitted", True)),
            "hierarchy": hierarchy.to_json(),
            "classification": classification.to_json(),
            "parameters": dict(sorted(comp.parameters.items())),
        }

    def _parse_hierarchy(self, designator: str, sheet: str) -> ComponentHierarchy:
        """
        Parse hierarchy info from designator.

                Handles multi-channel designators like "R1_A", "R1_B" or "R1A", "R1B".
        """
        from .altium_netlist_model import ComponentHierarchy

        # Pattern: base_designator + optional channel suffix
        # Examples: "R1_A" -> R1, A; "R1A" -> R1, A; "U1_CH2" -> U1, CH2
        match = re.match(r"^([A-Za-z]+\d+)(?:_?([A-Z])|\d*)$", designator)
        if match:
            base = match.group(1)
            channel = match.group(2)
            channel_index = ord(channel) - ord("A") + 1 if channel else None
        else:
            base = designator
            channel = None
            channel_index = None

        return ComponentHierarchy(
            base_designator=base,
            channel=channel,
            channel_index=channel_index,
            sheet=sheet,
        )

    def _build_indexes(
        self,
        components_data: list[dict],
        nets_data: list[dict],
        physical_pages_data: list[dict] | None = None,
    ) -> dict:
        """
        Build pre-computed lookup indexes.
        """
        svg_to_components: dict[str, list[str]] = {}
        physical_svg_to_components: dict[str, list[str]] = {}
        component_to_physical_page: dict[str, str] = {}
        for comp_data in components_data:
            svg_id = comp_data.get("svg_id", "")
            designator = str(comp_data.get("designator", ""))
            if svg_id:
                svg_to_components.setdefault(str(svg_id), []).append(designator)
            physical_sheet_id = str(comp_data.get("physical_sheet_id", "") or "")
            if physical_sheet_id:
                component_to_physical_page[designator] = physical_sheet_id
            if physical_sheet_id and svg_id:
                physical_key = f"{physical_sheet_id}|{svg_id}"
                physical_svg_to_components.setdefault(physical_key, []).append(
                    designator
                )

        # Existing scalar map. It intentionally contains only
        # unambiguous logical SVG ids; repeated/channel consumers should use
        # svg_to_components or physical_svg_to_components.
        svg_to_component = {
            svg_id: designators[0]
            for svg_id, designators in svg_to_components.items()
            if len(_unique_nonempty_strings(designators)) == 1
        }

        component_to_nets: dict[str, list[str]] = {}
        net_to_components: dict[str, list[str]] = {}
        net_to_physical_pages: dict[str, list[str]] = {}
        for net in nets_data:
            net_name = str(net.get("name") or "")
            if not net_name:
                continue
            designators: set[str] = set()
            for terminal in net.get("terminals", []):
                if not isinstance(terminal, dict):
                    continue
                designator = str(terminal.get("designator") or "")
                if not designator:
                    continue
                designators.add(designator)
                component_to_nets.setdefault(designator, [])
                if net_name not in component_to_nets[designator]:
                    component_to_nets[designator].append(net_name)
            net_to_components[net_name] = sorted(designators)

            page_ids = [
                str(page_id)
                for page_id in net.get("physical_document_ids", [])
                if str(page_id)
            ]
            if page_ids:
                net_to_physical_pages[net_name] = sorted(
                    _unique_nonempty_strings(page_ids)
                )

        physical_page_to_components: dict[str, list[str]] = {}
        physical_page_to_nets: dict[str, list[str]] = {}
        for page in physical_pages_data or []:
            page_id = str(page.get("id") or "")
            if not page_id:
                continue
            physical_page_to_components[page_id] = [
                str(component.get("designator") or "")
                for component in page.get("components", [])
                if str(component.get("designator") or "")
            ]
            physical_page_to_nets[page_id] = [
                str(net.get("name") or "")
                for net in page.get("nets", [])
                if str(net.get("name") or "")
            ]
            for net_name in physical_page_to_nets[page_id]:
                net_to_physical_pages.setdefault(net_name, [])
                if page_id not in net_to_physical_pages[net_name]:
                    net_to_physical_pages[net_name].append(page_id)

        return {
            "svg_to_component": svg_to_component,
            "svg_to_components": {
                svg_id: sorted(_unique_nonempty_strings(designators))
                for svg_id, designators in sorted(svg_to_components.items())
            },
            "physical_svg_to_components": {
                key: sorted(_unique_nonempty_strings(designators))
                for key, designators in sorted(physical_svg_to_components.items())
            },
            "component_to_nets": {
                designator: sorted(_unique_nonempty_strings(nets))
                for designator, nets in sorted(component_to_nets.items())
            },
            "net_to_components": dict(sorted(net_to_components.items())),
            "net_to_physical_pages": {
                net_name: sorted(_unique_nonempty_strings(page_ids))
                for net_name, page_ids in sorted(net_to_physical_pages.items())
            },
            "component_to_physical_page": dict(
                sorted(component_to_physical_page.items())
            ),
            "physical_page_to_components": dict(
                sorted(physical_page_to_components.items())
            ),
            "physical_page_to_nets": dict(sorted(physical_page_to_nets.items())),
        }

    def _resolve_sheet_numbers(self, options: NetlistOptions) -> dict[str, str]:
        """
        Resolve sheet numbers for each document.

                Args:
                    options: NetlistOptions with auto_sheet_numbering flag

                Returns:
                    Dict mapping filename -> sheet number string
        """
        sheet_numbers: dict[str, str] = {}

        if options.auto_sheet_numbering:
            # Auto-number: assign 1, 2, 3, ... in document order
            for idx, schdoc in enumerate(self.schdocs):
                filename = schdoc.filepath.name if schdoc.filepath else f"sheet{idx}"
                sheet_numbers[filename] = str(idx + 1)
        else:
            # Manual: read from document parameters (SheetNumber)
            for idx, schdoc in enumerate(self.schdocs):
                filename = schdoc.filepath.name if schdoc.filepath else f"sheet{idx}"
                sheet_num = self._get_document_parameter(schdoc, "SheetNumber")
                if sheet_num:
                    sheet_numbers[filename] = sheet_num
                else:
                    sheet_numbers[filename] = str(idx + 1)

        return sheet_numbers

    @staticmethod
    def _get_document_parameter(schdoc: AltiumSchDoc, name: str) -> str | None:
        """
        Get a document parameter value by name from a SchDoc.

                Document parameters are SchParameter records at the document level
                (children of the SHEET record). These include SheetNumber, SheetTotal,
                Title, Revision, etc.
        """
        for p in schdoc.parameters:
            if getattr(p, "name", "") == name:
                value = getattr(p, "text", "")
                if value and value != "*":
                    return value
        return None

    def refresh_netlist(self) -> Netlist:
        """
        Force regeneration of netlist (clear cache).
        """
        self._netlist = None
        self._compiled_design = None
        return self.to_netlist()

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def components(self) -> list[SchComponentInfo]:
        """
        All components across all schematics.
        """
        result = []
        for schdoc in self.schdocs:
            result.extend(schdoc.get_components())
        return result

    def get_component(self, designator: str) -> SchComponentInfo | None:
        """
        Find component by designator across all schematics.
        """
        for schdoc in self.schdocs:
            comp = schdoc.get_component(designator)
            if comp:
                return comp
        return None

    def get_net(self, name: str) -> Net | None:
        """
        Get net by name from netlist.
        """
        return self.to_netlist().get_net(name)

    # ------------------------------------------------------------------
    # BOM Generation
    # ------------------------------------------------------------------

    def to_bom(self, variant: str | None = None) -> list[dict]:
        """
        Generate BOM from schematic components.

                This extracts ALL components from the schematic with their parameters.
                BOM data comes from schematic (not PCB) because:
                1. Schematic is the canonical source for component data
                2. Variants are defined at schematic level
                3. Component parameters are stored on schematic symbols

                Args:
                    variant: If specified, filter components by variant (DNP handling).
                            If None, returns all components.

                Returns:
                    List of component dicts, each containing:
                    - designator: Component designator (e.g., "R1")
                    - value: Component value
                    - footprint: PCB footprint
                    - library_ref: Library reference (symbol name)
                    - description: Component description
                    - parameters: Dict of all component parameters
                    - dnp: True if component is Do Not Populate in this variant
        """
        netlist = self.to_netlist()
        comp_data_map = self._build_component_data_map(netlist)

        # Get DNP list for this variant (if specified)
        dnp_set: set[str] = set()
        parameter_overrides: dict[str, dict[str, str]] = {}
        if variant and self.project:
            variant_data = self.project.variants.get(variant, {})
            for variation in variant_data.get("variations", []):
                # Kind=1 means Not Fitted (DNP)
                if variation.get("Kind") == "1":
                    designator = variation.get("Designator", "")
                    if designator:
                        dnp_set.add(designator)
            parameter_overrides = self.get_variant_parameter_overrides(variant)

        result = []
        for comp in netlist.components:
            # GRAPHICAL, NET_TIE_NO_BOM, and STANDARD_NO_BOM are excluded.
            if comp.exclude_from_bom:
                continue

            parameters = dict(comp.parameters)
            component_overrides = parameter_overrides.get(comp.designator, {})
            if component_overrides:
                parameters.update(component_overrides)

            value = _resolve_component_value_from_parameters(
                base_value=comp.value,
                parameters=parameters,
                project_parameters=self.project.parameters if self.project else None,
            )
            description = (
                _lookup_case_insensitive(parameters, "Description") or comp.description
            )

            # Use parameters from the compiled netlist component rather than
            # reaching back into the source SchDoc.
            component_data = {
                "designator": comp.designator,
                "value": value,
                "footprint": comp.footprint,
                "library_ref": comp.library_ref,
                "description": description,
                "sheet": comp_data_map.get(comp.designator, {}).get("sheet", ""),
                "parameters": parameters,
                "dnp": comp.designator in dnp_set,
            }
            result.append(component_data)

        return result

    def get_variants(self) -> list[str]:
        """
        Get list of available variant names.

                Returns:
                    List of variant names, empty if no project or no variants defined.
        """
        if not self.project:
            return []
        return list(self.project.variants.keys())

    def get_variant_parameter_overrides(
        self, variant: str | None = None
    ) -> dict[str, dict[str, str]]:
        """
        Get active variant parameter overrides grouped by source designator.

        Args:
            variant: Variant name to resolve. If omitted, use the project's
                current variant.

        Returns:
            Mapping of designator -> parameter name -> variant value. Empty
            when there is no project, no active variant, or no overrides.
        """
        if not self.project:
            return {}
        variant_name = variant or self.project.get_current_variant()
        if not variant_name:
            return {}
        variant_data = self.project.variants.get(variant_name)
        if not variant_data:
            return {}
        return _coerce_variant_parameter_overrides(variant_data)

    def get_pcb_project_parameters(self) -> dict[str, str]:
        """
        Resolve project-level parameters for PCB text substitution.
        """
        if not self.project:
            return {}
        parameters = dict(self.project.parameters)
        current_variant = self.project.get_current_variant()
        if current_variant:
            parameters["VariantName"] = current_variant
        return parameters

    @staticmethod
    def _filter_pcbdoc_paths(
        candidates: list[Path],
        selector: Path | str,
        *,
        project_dir: Path | None = None,
    ) -> list[Path]:
        """
        Filter PcbDoc path candidates by selector.

        Selector matching supports:
        - absolute path
        - project-relative path
        - filename
        - filename stem
        """
        selector_raw = str(selector).strip()
        if not selector_raw:
            return candidates

        selector_path = Path(selector_raw)
        selector_lower = selector_raw.lower()
        selector_norm = selector_raw.replace("\\", "/").lower()
        resolved_selector: Path | None = None

        if selector_path.is_absolute():
            resolved_selector = selector_path.resolve()
        elif project_dir is not None:
            resolved_selector = (project_dir / selector_path).resolve()

        matches: list[Path] = []
        for candidate in candidates:
            if (
                candidate.name.lower() == selector_lower
                or candidate.stem.lower() == selector_lower
            ):
                matches.append(candidate)
                continue

            if project_dir is not None:
                try:
                    rel = (
                        candidate.resolve()
                        .relative_to(project_dir.resolve())
                        .as_posix()
                        .lower()
                    )
                except ValueError:
                    rel = ""
                if rel and rel == selector_norm:
                    matches.append(candidate)
                    continue

            if (
                resolved_selector is not None
                and candidate.resolve() == resolved_selector
            ):
                matches.append(candidate)

        if not matches:
            raise ValueError(
                f"PcbDoc '{selector_raw}' not found. Available boards: "
                f"{', '.join(path.name for path in candidates)}"
            )

        deduped = list(dict.fromkeys(matches))
        if len(deduped) > 1:
            raise ValueError(
                f"PcbDoc selector '{selector_raw}' matched multiple boards: "
                f"{', '.join(path.name for path in deduped)}"
            )
        return deduped

    def get_pcbdoc_paths(self, selector: Path | str | None = None) -> list[Path]:
        """
        Get PcbDoc paths for this design.

        For project-backed designs, returns all referenced PcbDocs in project order.
        For standalone-PcbDoc designs, returns the single loaded path.
        """
        if self.project:
            candidates = self.project.get_pcbdoc_paths()
            if not candidates:
                return []
            if selector is None:
                return candidates
            return self._filter_pcbdoc_paths(
                candidates,
                selector,
                project_dir=self.project.filepath.parent
                if self.project.filepath
                else None,
            )

        standalone_path = (
            Path(self._pcbdoc.filepath).resolve()
            if self._pcbdoc and self._pcbdoc.filepath
            else None
        )
        if standalone_path is None:
            return []
        candidates = [standalone_path]
        if selector is None:
            return candidates
        return self._filter_pcbdoc_paths(candidates, selector)

    def load_pcbdoc(self, selector: Path | str | None = None) -> AltiumPcbDoc:
        """
        Load and cache a PcbDoc by selector.
        """
        pcb_paths = self.get_pcbdoc_paths(selector=selector)
        if not pcb_paths:
            if self.project:
                raise ValueError(f"No PcbDoc found in project: {self.project.filepath}")
            raise ValueError("No standalone PcbDoc is loaded in this design")

        if selector is None and self.project and len(pcb_paths) > 1:
            log.warning(
                f"Multiple PcbDoc files found, using first: {pcb_paths[0].name}"
            )

        target_path = pcb_paths[0]
        cache_key = str(target_path.resolve())
        cached = self._pcbdoc_cache.get(cache_key)
        if cached is not None:
            self._pcbdoc = cached
            self._pcbdoc_loaded = True
            return cached

        from .altium_pcbdoc import AltiumPcbDoc

        log.debug(f"Loading PcbDoc: {target_path.name}")
        parsed = AltiumPcbDoc.from_file(target_path)
        self._pcbdoc_cache[cache_key] = parsed
        self._pcbdoc = parsed
        self._pcbdoc_loaded = True
        return parsed

    # ------------------------------------------------------------------
    # Pick and Place
    # ------------------------------------------------------------------

    def to_pnp(
        self,
        variant: str | None = None,
        units: str = "mm",
        exclude_no_bom: bool = False,
        position_mode: PnpPositionMode | str = PNP_POSITION_MODE_ALTIUM_PICK_PLACE,
    ) -> list[PnpEntry]:
        """
        Generate Pick-and-Place data from PCB.

                PcbDoc data is loaded on demand so BOM-only workflows do not pay the
                parse cost of the PCB file. The default ``altium-pick-place``
                position mode matches Altium's Pick Place export: it uses the
                center of the bounding box of component-owned pad anchor points
                and falls back to the component origin when no pads exist.
                ``component-origin`` returns the footprint placement origin
                directly.

                Args:
                    variant: If specified, filter components by variant (DNP handling).
                            If None, returns all components.
                    units: Position units - "mm" (default) or "mils"
                    exclude_no_bom: If True, exclude STANDARD_NO_BOM/GRAPHICAL components.
                                   Default False because PnP may need mechanical placements.
                    position_mode: "altium-pick-place" (default) or
                                   "component-origin".

                Returns:
                    List of PnpEntry objects with position/rotation data.

                Raises:
                    ValueError: If no PcbDoc found in project.
        """
        from .altium_component_kind import component_kind_includes_in_bom
        from .altium_common_enums import ComponentKind
        from .altium_netlist_model import PnpEntry

        # Lazy-load PcbDoc on first call
        pcbdoc = self._get_or_load_pcbdoc()

        # Build BOM lookup for schematic data (parameters, description, etc.)
        # Use netlist components which have parameters populated
        netlist = self.to_netlist()
        bom_lookup = {comp.designator: comp for comp in netlist.components}

        # Get DNP list for this variant (if specified)
        dnp_set: set[str] = set()
        if variant and self.project:
            variant_data = self.project.variants.get(variant, {})
            for variation in variant_data.get("variations", []):
                if variation.get("Kind") == "1":  # Kind=1 means Not Fitted
                    designator = variation.get("Designator", "")
                    if designator:
                        dnp_set.add(designator)

        # Unit conversion factor (mils to mm: 1 mil = 0.0254 mm)
        if units == "mm":
            scale = 0.0254
        elif units == "mils":
            scale = 1.0
        else:
            raise ValueError(f"Unknown units: {units}. Use 'mm' or 'mils'.")

        normalized_position_mode = normalize_pnp_position_mode(position_mode)
        result: list[PnpEntry] = []
        for component_index, pcb_comp in enumerate(pcbdoc.components):
            designator = pcb_comp.designator

            # Skip DNP components if variant specified
            if designator in dnp_set:
                continue

            # Get schematic data for this component (if available)
            sch_comp = bom_lookup.get(designator)

            # Optionally filter based on ComponentKind from schematic
            # Default: include all (PnP may need mechanical placements)
            if (
                exclude_no_bom
                and sch_comp
                and not component_kind_includes_in_bom(
                    ComponentKind(sch_comp.component_kind)
                )
            ):
                continue

            # Calculate the selected Pick Place position relative to the board origin.
            x_mils, y_mils = pcbdoc.get_component_pnp_position_mils(
                component_index,
                position_mode=normalized_position_mode,
            )

            # Convert to requested units
            center_x = round(x_mils * scale, 4)
            center_y = round(y_mils * scale, 4)

            # Use AltiumPcbComponent's layer normalization method
            layer = pcb_comp.get_layer_normalized()

            # Use AltiumPcbComponent's rotation method
            rotation = pcb_comp.get_rotation_degrees()

            # Build PnP entry with type-safe dataclass
            pnp_entry = PnpEntry(
                designator=designator,
                comment=sch_comp.value if sch_comp else "",
                layer=layer,
                footprint=pcb_comp.footprint,
                center_x=center_x,
                center_y=center_y,
                rotation=rotation,
                description=sch_comp.description if sch_comp else pcb_comp.description,
                parameters={
                    str(key): str(value)
                    for key, value in (
                        sch_comp.parameters if sch_comp else (pcb_comp.parameters or {})
                    ).items()
                },
            )
            result.append(pnp_entry)

        return result

    def _get_or_load_pcbdoc(self) -> AltiumPcbDoc:
        """
        Load and cache the default PcbDoc for this design.

                Returns:
                    Parsed AltiumPcbDoc instance

                Raises:
                    ValueError: If no PcbDoc found in project or no project loaded
        """
        return self.load_pcbdoc(selector=None)

    @property
    def pcbdoc(self) -> AltiumPcbDoc | None:
        """
        Loaded PcbDoc, if one has already been parsed.
        """
        return self._pcbdoc
