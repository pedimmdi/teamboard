from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .validators import validate_avatar


def normalize_avatar(value):
    """Normalize new avatars; existing files and attachments are untouched."""
    validate_avatar(value)
    value.seek(0)
    with Image.open(value) as image:
        normalized = ImageOps.exif_transpose(image)
        transparent = "A" in normalized.getbands() or "transparency" in normalized.info
        target_mode = "RGBA" if transparent else "RGB"
        if normalized.mode != target_mode:
            normalized = normalized.convert(target_mode)
        normalized.thumbnail((512, 512), Image.Resampling.LANCZOS)
        normalized.info.clear()
        normalized.getexif().clear()
        output = BytesIO()
        normalized.save(output, format="WEBP", quality=90, lossless=transparent, method=0)
    return ContentFile(output.getvalue(), name=Path(value.name).stem + ".webp")
