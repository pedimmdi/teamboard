from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .validators import validate_avatar


def normalize_avatar(value):
    """Apply orientation and re-encode pixels without user-supplied metadata."""
    validate_avatar(value)
    value.seek(0)
    with Image.open(value) as image:
        image_format = image.format
        normalized = ImageOps.exif_transpose(image).copy()
        if "transparency" in normalized.info:
            normalized = normalized.convert("RGBA")
        normalized.info.clear()
        normalized.getexif().clear()
        output = BytesIO()
        normalized.save(output, format=image_format)
    return ContentFile(output.getvalue(), name=Path(value.name).name)
