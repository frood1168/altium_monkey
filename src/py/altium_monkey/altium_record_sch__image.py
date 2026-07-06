"""Schematic record model for SchRecordType.IMAGE."""

from typing import Any, Protocol

from .altium_sch_enums import Rotation90
from .altium_record_types import (
    ColorValue,
    CoordPoint,
    LineWidth,
    SchGraphicalObject,
    SchRectMils,
    SchRecordType,
    color_to_hex,
    rgb_to_win32_color,
)
from .altium_serializer import AltiumSerializer, Fields
from .altium_sch_image_payload import (
    SchEmbeddedImageFormat,
    decode_bmp_rgba,
    decode_sch_embedded_image_payload,
    detect_image_format,
    image_size_px_from_data,
)
from .altium_sch_record_helpers import (
    CornerMilsMixin,
    detect_case_mode_method_from_dotted_uppercase_fields,
)
from .altium_sch_svg_renderer import SchSvgRenderContext


class _RgbaImageBuffer(Protocol):
    mode: str
    size: tuple[int, int]

    def convert(self, mode: str) -> "_RgbaImageBuffer": ...

    def tobytes(self) -> bytes: ...


def _png_u32(value: int) -> bytes:
    return int(value).to_bytes(4, "big", signed=False)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    import zlib

    crc = zlib.crc32(kind)
    crc = zlib.crc32(payload, crc)
    return _png_u32(len(payload)) + kind + payload + _png_u32(crc & 0xFFFFFFFF)


def _png_filter_score(value: int) -> int:
    return value if value < 128 else 256 - value


def _png_paeth_predictor(left: int, up: int, upper_left: int) -> int:
    pa = abs(up - upper_left)
    pb = abs(left - upper_left)
    pc = abs(left + up - (2 * upper_left))
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return upper_left


def _filter_rgba_rows_pillow_style(
    rgba_pixels: bytes,
    width: int,
    height: int,
) -> bytes:
    bytes_per_pixel = 4
    row_bytes = width * bytes_per_pixel
    filtered = bytearray()
    previous = bytearray(row_bytes + 1)

    for y in range(height):
        row_start = y * row_bytes
        current = bytearray(1 + row_bytes)
        current[1:] = rgba_pixels[row_start : row_start + row_bytes]

        best_row = current
        best_score = sum(_png_filter_score(value) for value in current[1:])

        if best_score > 0:
            up = bytearray(1 + row_bytes)
            up[0] = 2
            score = 0
            for index in range(1, row_bytes + 1):
                value = (current[index] - previous[index]) & 0xFF
                up[index] = value
                score += _png_filter_score(value)
            if score < best_score:
                best_row = up
                best_score = score

        if best_score > 0:
            prior = bytearray(1 + row_bytes)
            prior[0] = 1
            score = 0
            for index in range(1, min(row_bytes, bytes_per_pixel) + 1):
                value = current[index]
                prior[index] = value
                score += _png_filter_score(value)
            for index in range(bytes_per_pixel + 1, row_bytes + 1):
                value = (current[index] - current[index - bytes_per_pixel]) & 0xFF
                prior[index] = value
                score += _png_filter_score(value)
            if score < best_score:
                best_row = prior
                best_score = score

        if best_score > 0:
            paeth = bytearray(1 + row_bytes)
            paeth[0] = 4
            score = 0
            for index in range(1, min(row_bytes, bytes_per_pixel) + 1):
                value = (current[index] - previous[index]) & 0xFF
                paeth[index] = value
                score += _png_filter_score(value)
            for index in range(bytes_per_pixel + 1, row_bytes + 1):
                predictor = _png_paeth_predictor(
                    current[index - bytes_per_pixel],
                    previous[index],
                    previous[index - bytes_per_pixel],
                )
                value = (current[index] - predictor) & 0xFF
                paeth[index] = value
                score += _png_filter_score(value)
            if score < best_score:
                best_row = paeth

        filtered.extend(best_row)
        previous = current

    return bytes(filtered)


def _encode_rgba_png_pillow_style(
    rgba_pixels: bytes,
    width: int,
    height: int,
) -> bytes:
    import zlib

    if width <= 0 or height <= 0 or len(rgba_pixels) != width * height * 4:
        raise ValueError("invalid RGBA PNG buffer dimensions")

    filtered = _filter_rgba_rows_pillow_style(rgba_pixels, width, height)
    compressor = zlib.compressobj(
        level=-1,
        method=zlib.DEFLATED,
        wbits=15,
        memLevel=9,
        strategy=zlib.Z_FILTERED,
    )
    compressed = compressor.compress(filtered) + compressor.flush()

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    ihdr = _png_u32(width) + _png_u32(height) + bytes((8, 6, 0, 0, 0))
    png.extend(_png_chunk(b"IHDR", ihdr))
    for offset in range(0, len(compressed), 65536):
        png.extend(_png_chunk(b"IDAT", compressed[offset : offset + 65536]))
    png.extend(_png_chunk(b"IEND", b""))
    return bytes(png)


def _save_rgba_image_as_stable_png(img: _RgbaImageBuffer) -> bytes:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    width, height = img.size
    return _encode_rgba_png_pillow_style(img.tobytes(), int(width), int(height))


class AltiumSchImage(CornerMilsMixin, SchGraphicalObject):
    """
    IMAGE record.

    Represents an embedded or linked schematic image.

    `image_data` stores the raw payload from the SchDoc Storage stream for
    preservation. For some Altium files that payload is a BMP preview plus a
    native image payload. Use `AltiumSchDoc.extract_embedded_images(...)` when
    exporting standalone image files.
    """

    def __init__(self) -> None:
        super().__init__()
        self.corner = CoordPoint()
        self.embed_image: bool = False
        self.filename: str = ""
        self.keep_aspect: bool = True
        self.orientation: Rotation90 = Rotation90.DEG_0

        # Border properties
        self.is_solid: bool = False  # Draw border when True
        self.line_width: LineWidth = LineWidth.SMALLEST  # Border thickness

        # Image data (loaded separately from Storage stream)
        self.image_data: bytes | None = None
        self.image_format: str | None = None  # 'png', 'bmp', 'jpg', etc.

        # Track which fields were present
        self._has_corner_x: bool = False
        self._has_corner_y: bool = False
        self._has_embed_image: bool = False
        self._has_keep_aspect: bool = False
        self._has_is_solid: bool = False
        self._has_line_width: bool = False

    @property
    def record_type(self) -> SchRecordType:
        return SchRecordType.IMAGE

    @property
    def embedded(self) -> bool:
        """
        Alias for embed_image.
        """
        return self.embed_image

    @property
    def width(self) -> int:
        """
        Width of image in internal units.
        """
        return abs(self.corner.x - self.location.x)

    @property
    def height(self) -> int:
        """
        Height of image in internal units.
        """
        return abs(self.corner.y - self.location.y)

    @property
    def bounds_mils(self) -> SchRectMils:
        """
        Public image bounds helper expressed in mils.
        """
        return SchRectMils.from_points(self.location_mils, self.corner_mils)

    @bounds_mils.setter
    def bounds_mils(self, value: SchRectMils) -> None:
        if not isinstance(value, SchRectMils):
            raise TypeError("bounds_mils must be a SchRectMils value")
        location, corner = value.to_coord_points()
        self.location = location
        self.corner = corner

    @property
    def border_color(self) -> ColorValue | None:
        """
        Public border color helper.
        """
        if self.color is None:
            return None
        return ColorValue.from_win32(self.color)

    @border_color.setter
    def border_color(self, value: ColorValue | None) -> None:
        if value is None:
            self.color = None
            return
        if not isinstance(value, ColorValue):
            raise TypeError("border_color must be a ColorValue or None")
        self.color = value.win32

    def parse_from_record(
        self,
        record: dict[str, Any],
        font_manager: Any | None = None,
    ) -> None:
        super().parse_from_record(record, font_manager)

        # Use serializer for field reading
        s = AltiumSerializer()

        # Parse corner coordinates with presence tracking
        corner_x, corner_x_frac, self._has_corner_x = s.read_coord(
            record, "Corner", "X"
        )
        corner_y, corner_y_frac, self._has_corner_y = s.read_coord(
            record, "Corner", "Y"
        )
        self.corner = CoordPoint(corner_x, corner_y, corner_x_frac, corner_y_frac)

        # Image properties
        self.embed_image, self._has_embed_image = s.read_bool(
            record, Fields.EMBED_IMAGE, default=False
        )
        self.filename, _ = s.read_str(record, Fields.FILENAME, default="")
        self.keep_aspect, self._has_keep_aspect = s.read_bool(
            record, Fields.KEEP_ASPECT, default=False
        )
        orient_val, _ = s.read_int(record, Fields.ORIENTATION, default=0)
        self.orientation = Rotation90(orient_val)

        # Existing SchDoc/SchLib image records can omit IsSolid while still
        # semantically behaving as borderless images in the Altium oracle.
        self.is_solid, self._has_is_solid = s.read_bool(
            record, Fields.IS_SOLID, default=False
        )
        line_width_val, self._has_line_width = s.read_int(
            record, Fields.LINE_WIDTH, default=0
        )
        self.line_width = LineWidth(line_width_val)

    def serialize_to_record(self) -> dict[str, Any]:
        record = super().serialize_to_record()

        # Determine case mode from raw record
        mode = self._detect_case_mode()
        s = AltiumSerializer(mode)
        raw = self._raw_record

        # Corner - only write if present or non-zero
        if self._has_corner_x or self.corner.x != 0:
            s.write_coord(record, "Corner", "X", self.corner.x, self.corner.x_frac, raw)
        if self._has_corner_y or self.corner.y != 0:
            s.write_coord(record, "Corner", "Y", self.corner.y, self.corner.y_frac, raw)

        # Remove fields that the base class may have written but Image
        # handles explicitly below.
        s.remove_field(record, Fields.IS_SOLID)
        s.remove_field(record, Fields.LINE_WIDTH)

        # Image core fields: only write if the field was explicitly present
        # in the original record (_has_* flag) or the value is non-default.
        s.write_bool(
            record,
            Fields.EMBED_IMAGE,
            self.embed_image,
            raw,
            force=(self._has_embed_image or self.embed_image),
        )
        if self.filename:
            s.write_str(record, Fields.FILENAME, self.filename, raw)
        s.write_bool(
            record,
            Fields.KEEP_ASPECT,
            self.keep_aspect,
            raw,
            force=(self._has_keep_aspect or self.keep_aspect),
        )
        s.write_int(
            record,
            Fields.ORIENTATION,
            self.orientation.value,
            raw,
            force=(self.orientation != Rotation90.DEG_0),
        )
        # Synthesized image records should emit the native default border fields,
        # while parsed sparse records stay sparse unless those fields were present
        # or intentionally changed.
        s.write_bool(
            record,
            Fields.IS_SOLID,
            self.is_solid,
            raw,
            force=(self._has_is_solid or self.is_solid),
        )
        s.write_int(
            record,
            Fields.LINE_WIDTH,
            self.line_width.value,
            raw,
            force=(self._has_line_width or self.line_width.value != 0),
        )

        # Image records do not own the inherited shape-only fields below.
        s.remove_field(record, Fields.AREA_COLOR)
        s.remove_field(record, Fields.TRANSPARENT)
        s.remove_field(record, Fields.LINE_STYLE)
        s.remove_field(record, Fields.LINE_STYLE_EXT)

        return record

    _detect_case_mode = detect_case_mode_method_from_dotted_uppercase_fields

    def detect_format(self) -> str | None:
        """
        Detect the raw `image_data` storage format from header bytes.

        This method reports the format visible at the start of the stored
        payload. Wrapped Altium images may therefore report `BMP` even though
        the preferred export payload is PNG, JPEG, GIF, SVG, or WebP. Use
        `AltiumSchDoc.extract_embedded_images(...)` when writing image files.

        Returns:
            Format string such as `PNG`, `BMP`, `JPEG`, or `GIF`, or None.
        """
        if not self.image_data or len(self.image_data) < 8:
            return None

        image_format = detect_image_format(self.image_data)
        if image_format is not None:
            self.image_format = image_format.value
        else:
            self.image_format = None

        return self.image_format

    def __repr__(self) -> str:
        embedded_str = "embedded" if self.embed_image else "linked"
        return (
            f"<AltiumSchImage '{self.filename}' {embedded_str} "
            f"at=({self.location.x}, {self.location.y})>"
        )

    def _try_load_original_file(self, document_path: str | None = None) -> bytes | None:
        """
        Try to load the original image file from disk.

        Altium tries multiple paths to find the original file:
        1. The exact filename as stored in the record
        2. If starts with backslash, strip it and try again
        3. Try combining with document's ImagePath parameter
        4. Try relative to document location

        When the original file is found, Altium uses it instead of the embedded
        BMP data, preserving transparency for PNG files.

        Args:
            document_path: Optional path to the SchDoc file for relative resolution

        Returns:
            Original file data as bytes, or None if not found
        """
        from pathlib import Path

        if not self.filename:
            return None

        paths_to_try = []

        # 1. Try exact path as stored
        paths_to_try.append(self.filename)

        # 2. Strip leading backslash if present
        if self.filename.startswith("\\"):
            paths_to_try.append(self.filename[1:])

        # 3. Try relative to document location
        if document_path:
            doc_dir = Path(document_path).parent
            # Try just the filename
            paths_to_try.append(str(doc_dir / Path(self.filename).name))
            # Try the path relative to document
            if self.filename.startswith("\\"):
                paths_to_try.append(str(doc_dir / self.filename[1:]))

        # Try each path
        for path in paths_to_try:
            try:
                p = Path(path)
                if p.exists() and p.is_file():
                    return p.read_bytes()
            except (OSError, ValueError):
                continue

        return None

    def _preferred_image_data(
        self,
        document_path: str | None = None,
    ) -> tuple[bytes, SchEmbeddedImageFormat | None] | None:
        original_data = self._try_load_original_file(document_path)
        if original_data:
            original_payload = decode_sch_embedded_image_payload(original_data)
            return original_payload.preferred_data, original_payload.preferred_format
        if not self.image_data:
            return None
        payload = decode_sch_embedded_image_payload(self.image_data)
        return payload.preferred_data, payload.preferred_format

    def _convert_to_png(
        self,
        background_color: str | None = None,
        alpha_tolerance: int = 5,
        document_path: str | None = None,
    ) -> bytes | None:
        """
        Convert image data to PNG format for SVG embedding.

        The renderer prefers native payload bytes from Altium embedded-image
        wrappers. For example, an embedded PNG is stored as a BMP preview plus
        `TdxPNGImage` plus the original PNG bytes; the PNG is the fidelity
        source. Schematic background-color keying is intentionally not applied.

        Args:
            background_color: Deprecated compatibility argument; ignored.
            alpha_tolerance: Deprecated compatibility argument; ignored.
            document_path: Optional path to SchDoc for resolving relative image paths.

        Returns:
            PNG image data as bytes, or None if no image data
        """
        del background_color, alpha_tolerance

        preferred = self._preferred_image_data(document_path)
        if preferred is None:
            return None
        source_data, image_format = preferred

        if image_format == SchEmbeddedImageFormat.PNG:
            return source_data
        if image_format == SchEmbeddedImageFormat.BMP:
            rgba_bmp = decode_bmp_rgba(source_data)
            if rgba_bmp is not None:
                width, height, rgba_pixels = rgba_bmp
                return _encode_rgba_png_pillow_style(rgba_pixels, width, height)

        # Convert using PIL
        import io

        try:
            from PIL import Image
        except ImportError:
            return source_data

        try:
            img = Image.open(io.BytesIO(source_data))

            # Convert to RGB(A) mode for PNG export
            if img.mode not in ("RGB", "RGBA"):
                if img.mode == "P" and "transparency" in img.info:
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")

            # Save as PNG
            output = io.BytesIO()
            img.save(output, format="PNG")
            return output.getvalue()
        except Exception:
            return source_data

    def _runtime_image_payload(
        self,
        document_path: str | None = None,
    ) -> tuple[str, bytes] | None:
        """
        Return a browser-compatible image MIME type and payload for runtime SVG.
        """
        preferred = self._preferred_image_data(document_path)
        if preferred is None:
            return None
        source_data, image_format = preferred
        native_mime = self._mime_type_for_format(image_format)
        if native_mime and image_format != SchEmbeddedImageFormat.BMP:
            return (native_mime, source_data)

        png_data = self._convert_to_png(document_path=document_path)
        if png_data:
            if detect_image_format(png_data) == SchEmbeddedImageFormat.PNG:
                return ("image/png", png_data)
            fallback_mime = self._mime_type_for_format(detect_image_format(png_data))
            if fallback_mime:
                return (fallback_mime, png_data)

        fallback_mime = self._mime_type_for_format(image_format)
        if fallback_mime:
            return (fallback_mime, source_data)
        return None

    @staticmethod
    def _mime_type_for_format(
        image_format: SchEmbeddedImageFormat | None,
    ) -> str | None:
        if image_format == SchEmbeddedImageFormat.PNG:
            return "image/png"
        if image_format == SchEmbeddedImageFormat.JPEG:
            return "image/jpeg"
        if image_format == SchEmbeddedImageFormat.GIF:
            return "image/gif"
        if image_format == SchEmbeddedImageFormat.BMP:
            return "image/bmp"
        if image_format == SchEmbeddedImageFormat.SVG:
            return "image/svg+xml"
        if image_format == SchEmbeddedImageFormat.WEBP:
            return "image/webp"
        return None

    def _get_stroke_width(self) -> tuple[str, bool]:
        """
        Get SVG stroke-width and whether to use vector-effect.

        The LineWidth enum maps to specific pixel values for SVG export:

        - SMALLEST (0): 0.5px with vector-effect="non-scaling-stroke"
          The vector-effect ensures the stroke remains 0.5px regardless of
          SVG scaling/zoom, matching Altium's "hairline" concept.
        - SMALL (1): 1px (default for new images)
        - MEDIUM (2): 3px
        - LARGE (3): 5px

        The mapping follows the schematic image border stroke values used by
        Altium's SVG export.

        Returns:
            Tuple of (stroke_width_str, use_vector_effect)
        """
        mapping = {
            LineWidth.SMALLEST: ("0.5", True),
            LineWidth.SMALL: ("1", False),
            LineWidth.MEDIUM: ("3", False),
            LineWidth.LARGE: ("5", False),
        }
        return mapping.get(self.line_width, ("1", False))

    def _format_number(self, value: float) -> str:
        """
        Format a number for SVG output, removing unnecessary decimals.
        """
        if value == int(value):
            return str(int(value))
        # Round to 4 decimal places to match Altium output precision
        rounded = round(value, 4)
        # Remove trailing zeros
        return f"{rounded:.4f}".rstrip("0").rstrip(".")

    def _get_embedded_image_size_px(self) -> tuple[int, int] | None:
        """
        Return embedded image pixel size when it can be determined cheaply.
        """
        if not self.image_data:
            return None
        return decode_sch_embedded_image_payload(self.image_data).altium_source_size_px

    def _get_image_size_px_from_data(self, data: bytes) -> tuple[int, int] | None:
        """
        Return image pixel size from raw bytes for raster or SVG sources.
        """
        return image_size_px_from_data(data)

    def _get_preferred_source_image_size_px(
        self,
        document_path: str | None = None,
    ) -> tuple[int, int] | None:
        """
        Return GeometryMaker-style source image size, preferring the original file.
        """
        original_data = self._try_load_original_file(document_path)
        if original_data:
            original_size = self._get_image_size_px_from_data(original_data)
            if original_size is not None:
                return original_size
        return self._get_embedded_image_size_px()

    def runtime_image_key(self, document_id: str) -> str:
        """
        Return the runtime image href key for this image record.

        Many legacy SchDoc title-block image records do not carry UniqueID.
        Keep their IR identity fields anonymous, but give runtime resource
        resolvers a stable per-record key so multiple anonymous images on the
        same sheet do not collide.
        """
        unique_id = str(getattr(self, "unique_id", "") or "")
        if unique_id:
            return unique_id

        index_in_sheet = getattr(self, "index_in_sheet", None)
        if index_in_sheet is not None:
            try:
                return f"{document_id}\\image:{int(index_in_sheet)}"
            except (TypeError, ValueError):
                pass

        location = getattr(self, "location", CoordPoint())
        corner = getattr(self, "corner", CoordPoint())
        owner_part_id = getattr(self, "owner_part_id", None)
        owner_display_mode = getattr(self, "owner_part_display_mode", None)
        return (
            f"{document_id}\\image:"
            f"{getattr(self, 'owner_index', 0)}:"
            f"{owner_part_id if owner_part_id is not None else 'none'}:"
            f"{owner_display_mode if owner_display_mode is not None else 'none'}:"
            f"{location.x},{location.y},{location.x_frac},{location.y_frac}:"
            f"{corner.x},{corner.y},{corner.x_frac},{corner.y_frac}:"
            f"{getattr(self, 'filename', '') or ''}"
        )

    def to_geometry(
        self,
        ctx: SchSvgRenderContext | None = None,
        *,
        document_id: str,
        units_per_px: int = 64,
    ) -> Any:
        from .altium_sch_geometry_oracle import (
            SchGeometryBounds,
            SchGeometryOp,
            SchGeometryRecord,
            make_pen,
            svg_coord_to_geometry,
            wrap_record_operations,
        )

        if ctx is None:
            ctx = SchSvgRenderContext()

        x1, y1 = ctx.transform_coord_precise(self.location)
        x2, y2 = ctx.transform_coord_precise(self.corner)
        left_px = min(x1, x2)
        top_px = min(y1, y2)
        right_px = max(x1, x2)
        bottom_px = max(y1, y2)
        if abs(right_px - left_px) <= 1e-9 or abs(bottom_px - top_px) <= 1e-9:
            return None

        dest_x1, dest_y1 = svg_coord_to_geometry(
            left_px,
            top_px,
            sheet_height_px=float(ctx.sheet_height or 0.0),
            units_per_px=units_per_px,
        )
        dest_x2, dest_y2 = svg_coord_to_geometry(
            right_px,
            bottom_px,
            sheet_height_px=float(ctx.sheet_height or 0.0),
            units_per_px=units_per_px,
        )

        image_size = self._get_preferred_source_image_size_px(ctx.document_path)
        if image_size is None:
            source_x2 = max(1, int(round(abs(right_px - left_px) * units_per_px / 5)))
            source_y2 = max(1, int(round(abs(bottom_px - top_px) * units_per_px / 5)))
        else:
            source_x2, source_y2 = image_size

        operations = [
            SchGeometryOp.image(
                dest_x1=dest_x1,
                dest_y1=dest_y1,
                dest_x2=dest_x2,
                dest_y2=dest_y2,
                source_x2=source_x2,
                source_y2=source_y2,
                alpha=1.0,
            )
        ]

        if self.is_solid:
            border_color_raw = int(self.color) if self.color is not None else 0
            border_hex = ctx.apply_compile_mask_color(
                color_to_hex(border_color_raw),
                ctx.component_compile_masked is True,
            )
            border_color_raw = rgb_to_win32_color(
                int(border_hex[1:3], 16),
                int(border_hex[3:5], 16),
                int(border_hex[5:7], 16),
            )
            pen_width = {
                LineWidth.SMALLEST: 0,
                LineWidth.SMALL: units_per_px,
                LineWidth.MEDIUM: units_per_px * 3,
                LineWidth.LARGE: units_per_px * 5,
            }.get(self.line_width, units_per_px)
            operations.append(
                SchGeometryOp.rounded_rectangle(
                    x1=dest_x1,
                    y1=dest_y1,
                    x2=dest_x2,
                    y2=dest_y2,
                    pen=make_pen(
                        border_color_raw,
                        width=pen_width,
                    ),
                )
            )

        left_units = min(dest_x1, dest_x2)
        right_units = max(dest_x1, dest_x2)
        top_units = min(dest_y1, dest_y2)
        bottom_units = max(dest_y1, dest_y2)
        unique_id = str(self.unique_id or "")
        extras = (
            {"image_key": self.runtime_image_key(document_id)} if not unique_id else {}
        )
        return SchGeometryRecord(
            handle=f"{document_id}\\{self.unique_id}",
            unique_id=self.unique_id,
            kind="image",
            object_id="eImage",
            bounds=SchGeometryBounds(
                left=int(round(left_units)),
                top=int(round(top_units)),
                right=int(round(right_units)),
                bottom=int(round(bottom_units)),
            ),
            operations=wrap_record_operations(
                self.unique_id,
                operations,
                units_per_px=units_per_px,
            ),
            extras=extras,
        )
