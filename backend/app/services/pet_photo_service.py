"""Pet photo storage: validate, auto-resize and convert to WebP."""

from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import bad_request

logger = logging.getLogger("petcare.pet_photos")

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

# Reject decompression bombs before Pillow allocates a huge bitmap.
Image.MAX_IMAGE_PIXELS = 40_000_000


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def save_pet_photo(data: bytes, pet_id: uuid.UUID) -> str:
    """Decode, auto-resize, flatten and store an image as WebP.

    Returns the generated filename, not a path, so the database never holds
    host-specific paths.
    """
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise bad_request(
                    "INVALID_IMAGE_TYPE", "รองรับเฉพาะไฟล์ JPEG, PNG หรือ WebP"
                )
            image = ImageOps.exif_transpose(source) or source.copy()
            image.thumbnail(
                (settings.photo_max_dimension, settings.photo_max_dimension),
                Image.Resampling.LANCZOS,
            )
            image = _flatten_to_rgb(image)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise bad_request("INVALID_IMAGE", "ไฟล์รูปไม่ถูกต้องหรืออ่านไม่ได้") from exc

    directory = Path(settings.photo_dir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{pet_id}-{uuid.uuid4().hex}.webp"
    target = directory / filename
    temporary = directory / f".{filename}.tmp"

    try:
        image.save(
            temporary,
            format="WEBP",
            quality=settings.photo_quality,
            method=6,
        )
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

    return filename


def delete_pet_photo(filename: str | None) -> None:
    if not filename:
        return
    path = Path(settings.photo_dir) / Path(filename).name
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("could not delete pet photo %s", path, exc_info=True)
