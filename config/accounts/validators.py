from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


def validate_avatar(value):
    if value.size > 5 * 1024 * 1024:
        raise ValidationError('Profile images must be 5 MB or smaller.')
    formats = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}
    expected = formats.get(Path(value.name).suffix.lower())
    try:
        value.seek(0)
        with Image.open(value) as image:
            if expected is None or image.format != expected:
                raise ValidationError('Upload a JPEG, PNG, or WebP image with the correct extension.')
            if image.width > 4096 or image.height > 4096:
                raise ValidationError('Profile images must be 4096 × 4096 pixels or smaller.')
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError('Upload a valid JPEG, PNG, or WebP image.') from exc
    finally:
        value.seek(0)
