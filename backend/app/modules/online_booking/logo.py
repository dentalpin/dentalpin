"""Strict, bounded decoding and metadata-free re-encoding of public logos."""

import base64
import binascii
import io
from pathlib import PurePath

from PIL import Image, UnidentifiedImageError

MAX_LOGO_BYTES = 512 * 1024
MAX_LOGO_DIMENSION = 1024
MAX_LOGO_BASE64 = 4 * ((MAX_LOGO_BYTES + 2) // 3)
EXTENSIONS = {"PNG": {".png"}, "JPEG": {".jpg", ".jpeg"}, "WEBP": {".webp"}}


def sanitize_logo(encoded: str, filename: str) -> bytes:
    """Decode only bounded static raster files and emit a fresh PNG without metadata."""
    if len(encoded) > MAX_LOGO_BASE64 or len(encoded) % 4:
        raise ValueError("Logo exceeds size limit or has invalid encoding")
    padding = len(encoded) - len(encoded.rstrip("="))
    if padding > 2 or len(encoded) // 4 * 3 - padding > MAX_LOGO_BYTES:
        raise ValueError("Logo exceeds size limit")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_LOGO_BYTES:
            raise ValueError("Logo exceeds size limit")
        # Image.open is lazy: inspect format, dimensions and animation before loading pixels.
        with Image.open(io.BytesIO(raw), formats=list(EXTENSIONS)) as image:
            image_format = image.format
            if image_format not in EXTENSIONS:
                raise ValueError("Unsupported image format")
            if PurePath(filename).suffix.lower() not in EXTENSIONS[image_format]:
                raise ValueError("File extension does not match image content")
            if not (
                0 < image.width <= MAX_LOGO_DIMENSION and 0 < image.height <= MAX_LOGO_DIMENSION
            ):
                raise ValueError("Image dimensions exceed limit")
            if getattr(image, "n_frames", 1) != 1 or getattr(image, "is_animated", False):
                raise ValueError("Animated images are not supported")
            image.verify()
        with Image.open(io.BytesIO(raw), formats=list(EXTENSIONS)) as image:
            image.load()
            rgba = image.convert("RGBA")
            clean = Image.new("RGBA", rgba.size)
            clean.paste(rgba)
            output = io.BytesIO()
            clean.save(output, format="PNG")
            return output.getvalue()
    except (
        binascii.Error,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        SyntaxError,
    ) as exc:
        raise ValueError("Invalid logo image") from exc
