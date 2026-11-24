"""Logo upload boundaries and non-disclosure tests use only synthetic images."""

import base64
import io
from unittest.mock import patch

import pytest
from PIL import Image

from app.modules.online_booking.logo import MAX_LOGO_BYTES, sanitize_logo


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def image_bytes(fmt: str, size=(8, 8), **options) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, "red").save(stream, format=fmt, **options)
    return stream.getvalue()


@pytest.mark.parametrize(
    "fmt,filename", [("PNG", "logo.png"), ("JPEG", "logo.jpg"), ("WEBP", "logo.webp")]
)
def test_supported_rasters_are_reencoded_without_metadata(fmt, filename):
    exif = Image.Exif()
    exif[270] = "Synthetic private metadata"
    raw = image_bytes(fmt, exif=exif)
    result = sanitize_logo(encoded(raw), filename)
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (8, 8)
        assert not image.getexif()
        assert "exif" not in image.info
        assert "Synthetic private metadata" not in repr(image.info)


def test_svg_and_mismatched_file_extension_are_rejected():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    with pytest.raises(ValueError):
        sanitize_logo(encoded(svg), "logo.svg")
    with pytest.raises(ValueError):
        sanitize_logo(encoded(svg), "logo.png")
    with pytest.raises(ValueError):
        sanitize_logo(encoded(image_bytes("PNG")), "logo.jpg")


def test_encoded_size_is_rejected_before_base64_decoding():
    oversize = encoded(b"x" * (MAX_LOGO_BYTES + 1))
    with patch(
        "app.modules.online_booking.logo.base64.b64decode", side_effect=AssertionError("decoded")
    ):
        with pytest.raises(ValueError):
            sanitize_logo(oversize, "logo.png")


def test_dimensions_are_rejected_before_pixel_loading():
    huge = image_bytes("PNG", size=(1025, 10))
    with patch.object(Image.Image, "load", side_effect=AssertionError("pixels decoded")):
        with pytest.raises(ValueError, match="dimensions"):
            sanitize_logo(encoded(huge), "logo.png")


@pytest.mark.parametrize("fmt,filename", [("PNG", "logo.png"), ("WEBP", "logo.webp")])
def test_animated_raster_is_rejected(fmt, filename):
    image = Image.new("RGBA", (8, 8), "red")
    frames = [Image.new("RGBA", (8, 8), "blue")]
    data = io.BytesIO()
    image.save(data, format=fmt, save_all=True, append_images=frames, duration=100, loop=0)
    with pytest.raises(ValueError, match="Animated"):
        sanitize_logo(encoded(data.getvalue()), filename)


@pytest.mark.asyncio
async def test_admin_can_preview_sanitized_logo_when_public_booking_disabled(
    client, db_session, test_clinic, auth_headers
):
    from app.modules.online_booking.models import BookingSettings

    config = BookingSettings(
        clinic_id=test_clinic.id,
        enabled=False,
        logo_data=image_bytes("PNG"),
    )
    db_session.add(config)
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    preview = await client.get("/api/v1/online_booking/settings/logo", headers=headers)
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert preview.headers["cache-control"] == "private, no-store"
    public = await client.get(f"/api/v1/online_booking/public/{test_clinic.id}/logo")
    assert public.status_code == 404
