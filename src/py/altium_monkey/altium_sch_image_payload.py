"""Helpers for schematic embedded image payloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SchEmbeddedImageFormat(str, Enum):
    BMP = "BMP"
    PNG = "PNG"
    JPEG = "JPEG"
    GIF = "GIF"
    SVG = "SVG"
    WEBP = "WEBP"
    EMF = "EMF"
    WMF = "WMF"


ALTIUM_IMAGE_CLASS_FORMATS: dict[str, SchEmbeddedImageFormat] = {
    "TBitmap": SchEmbeddedImageFormat.BMP,
    "TdxPNGImage": SchEmbeddedImageFormat.PNG,
    "TJPEGImage": SchEmbeddedImageFormat.JPEG,
    "TGifImage": SchEmbeddedImageFormat.GIF,
    "TSVGImage": SchEmbeddedImageFormat.SVG,
    "TMetafile": SchEmbeddedImageFormat.EMF,
}


@dataclass(frozen=True)
class SchBmpInfo:
    file_size: int
    pixel_offset: int
    dib_header_size: int
    width: int
    height: int
    bits_per_pixel: int
    compression: int
    image_size: int

    @property
    def size_px(self) -> tuple[int, int]:
        return (abs(self.width), abs(self.height))


@dataclass(frozen=True)
class SchEmbeddedImagePayload:
    raw_data: bytes
    raw_format: SchEmbeddedImageFormat | None
    preview_data: bytes | None = None
    native_class: str | None = None
    native_data: bytes | None = None
    native_format: SchEmbeddedImageFormat | None = None

    @property
    def is_altium_wrapper(self) -> bool:
        return self.preview_data is not None and self.native_data is not None

    @property
    def preferred_data(self) -> bytes:
        return self.native_data if self.native_data else self.raw_data

    @property
    def preferred_format(self) -> SchEmbeddedImageFormat | None:
        return self.native_format if self.native_format else self.raw_format

    @property
    def preferred_size_px(self) -> tuple[int, int] | None:
        return image_size_px_from_data(self.preferred_data)

    @property
    def altium_source_size_px(self) -> tuple[int, int] | None:
        """
        Return the source size Altium reports in GeometryMaker image ops.
        """
        if self.native_format == SchEmbeddedImageFormat.SVG and self.preview_data:
            preview = parse_bmp_info(self.preview_data)
            if preview is not None:
                return preview.size_px
        return self.preferred_size_px


def detect_image_format(data: bytes) -> SchEmbeddedImageFormat | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return SchEmbeddedImageFormat.PNG
    if data.startswith(b"BM"):
        return SchEmbeddedImageFormat.BMP
    if data.startswith(b"\xff\xd8\xff"):
        return SchEmbeddedImageFormat.JPEG
    if data.startswith((b"GIF87a", b"GIF89a")):
        return SchEmbeddedImageFormat.GIF
    if data.startswith(b"\x01\x00\x00\x00"):
        return SchEmbeddedImageFormat.EMF
    if data.startswith(b"\xd7\xcd\xc6\x9a"):
        return SchEmbeddedImageFormat.WMF
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return SchEmbeddedImageFormat.WEBP
    head = data[:512].lstrip()
    if head.startswith((b"<svg", b"<?xml")) and b"<svg" in head[:256]:
        return SchEmbeddedImageFormat.SVG
    return None


def parse_bmp_info(data: bytes) -> SchBmpInfo | None:
    if len(data) < 54 or not data.startswith(b"BM"):
        return None
    file_size = int.from_bytes(data[2:6], "little", signed=False)
    pixel_offset = int.from_bytes(data[10:14], "little", signed=False)
    dib_header_size = int.from_bytes(data[14:18], "little", signed=False)
    if dib_header_size < 40 or len(data) < 14 + dib_header_size:
        return None
    width = int.from_bytes(data[18:22], "little", signed=True)
    height = int.from_bytes(data[22:26], "little", signed=True)
    bits_per_pixel = int.from_bytes(data[28:30], "little", signed=False)
    compression = int.from_bytes(data[30:34], "little", signed=False)
    image_size = int.from_bytes(data[34:38], "little", signed=False)
    return SchBmpInfo(
        file_size=file_size,
        pixel_offset=pixel_offset,
        dib_header_size=dib_header_size,
        width=width,
        height=height,
        bits_per_pixel=bits_per_pixel,
        compression=compression,
        image_size=image_size,
    )


def image_size_px_from_data(data: bytes) -> tuple[int, int] | None:
    image_format = detect_image_format(data)
    if image_format == SchEmbeddedImageFormat.PNG and len(data) >= 24:
        return (
            int.from_bytes(data[16:20], "big", signed=False),
            int.from_bytes(data[20:24], "big", signed=False),
        )
    if image_format == SchEmbeddedImageFormat.BMP:
        bmp = parse_bmp_info(data)
        return bmp.size_px if bmp else None
    if image_format == SchEmbeddedImageFormat.GIF and len(data) >= 10:
        return (
            int.from_bytes(data[6:8], "little", signed=False),
            int.from_bytes(data[8:10], "little", signed=False),
        )
    if image_format == SchEmbeddedImageFormat.SVG:
        return _svg_size_px(data)
    return _pillow_size_px(data)


def decode_sch_embedded_image_payload(data: bytes) -> SchEmbeddedImagePayload:
    raw_format = detect_image_format(data)
    wrapper = _decode_altium_wrapper(data)
    if wrapper is None:
        return SchEmbeddedImagePayload(raw_data=data, raw_format=raw_format)
    native_class, native_data, preview_data = wrapper
    native_format = ALTIUM_IMAGE_CLASS_FORMATS.get(native_class)
    return SchEmbeddedImagePayload(
        raw_data=data,
        raw_format=raw_format,
        preview_data=preview_data,
        native_class=native_class,
        native_data=native_data,
        native_format=native_format or detect_image_format(native_data),
    )


def decode_bmp_rgba(data: bytes) -> tuple[int, int, bytes] | None:
    bmp = parse_bmp_info(data)
    if bmp is None or bmp.bits_per_pixel not in (24, 32):
        return None
    width = abs(bmp.width)
    height = abs(bmp.height)
    if width <= 0 or height <= 0:
        return None

    bytes_per_pixel = bmp.bits_per_pixel // 8
    row_bytes = ((width * 3 + 3) // 4) * 4 if bmp.bits_per_pixel == 24 else width * 4
    if bmp.pixel_offset + (row_bytes * height) > len(data):
        return None

    rgba = bytearray(width * height * 4)
    top_down = bmp.height < 0
    for source_row in range(height):
        dest_row = source_row if top_down else (height - 1 - source_row)
        source_offset = bmp.pixel_offset + source_row * row_bytes
        dest_offset = dest_row * width * 4
        for pixel in range(width):
            source_index = source_offset + pixel * bytes_per_pixel
            dest_index = dest_offset + pixel * 4
            b = data[source_index]
            g = data[source_index + 1]
            r = data[source_index + 2]
            a = data[source_index + 3] if bmp.bits_per_pixel == 32 else 0xFF
            rgba[dest_index : dest_index + 4] = bytes((r, g, b, a))
    return (width, height, bytes(rgba))


def decode_32bit_bmp_rgba(data: bytes) -> tuple[int, int, bytes] | None:
    bmp = parse_bmp_info(data)
    if bmp is None or bmp.bits_per_pixel != 32:
        return None
    return decode_bmp_rgba(data)


def bmp_alpha_extrema(data: bytes) -> tuple[int, int] | None:
    """
    Return alpha-channel extrema for an uncompressed 32-bit BMP.
    """
    bmp = parse_bmp_info(data)
    if bmp is None or bmp.bits_per_pixel != 32:
        return None
    width = abs(bmp.width)
    height = abs(bmp.height)
    if width <= 0 or height <= 0:
        return None
    row_bytes = width * 4
    if bmp.pixel_offset + (row_bytes * height) > len(data):
        return None

    alpha_bytes = data[bmp.pixel_offset + 3 : bmp.pixel_offset + row_bytes * height : 4]
    if not alpha_bytes:
        return None
    return (min(alpha_bytes), max(alpha_bytes))


def _decode_altium_wrapper(data: bytes) -> tuple[str, bytes, bytes] | None:
    bmp = parse_bmp_info(data)
    if bmp is None:
        return None
    preview_len = bmp.file_size
    if preview_len <= 0 or preview_len >= len(data):
        return None
    if preview_len + 1 > len(data):
        return None
    class_len = data[preview_len]
    class_start = preview_len + 1
    class_end = class_start + class_len
    if class_len == 0 or class_end > len(data):
        return None
    try:
        native_class = data[class_start:class_end].decode("ascii")
    except UnicodeDecodeError:
        return None
    if native_class not in ALTIUM_IMAGE_CLASS_FORMATS:
        return None
    native_data = data[class_end:]
    if not native_data:
        return None
    return native_class, native_data, data[:preview_len]


def _pillow_size_px(data: bytes) -> tuple[int, int] | None:
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(data)) as image:
            return (int(image.width), int(image.height))
    except Exception:
        return None


def _svg_size_px(data: bytes) -> tuple[int, int] | None:
    import re
    from xml.etree import ElementTree

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="ignore")

    def parse_dimension(value: str | None) -> int | None:
        if not value:
            return None
        match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
        if not match:
            return None
        return int(float(match.group(1)))

    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        root = None
    if root is None:
        return None
    width = parse_dimension(root.attrib.get("width"))
    height = parse_dimension(root.attrib.get("height"))
    if width is not None and height is not None:
        return (width, height)
    view_box = root.attrib.get("viewBox")
    if not view_box:
        return None
    parts = re.split(r"[,\s]+", view_box.strip())
    if len(parts) != 4:
        return None
    try:
        return (int(float(parts[2])), int(float(parts[3])))
    except ValueError:
        return None
