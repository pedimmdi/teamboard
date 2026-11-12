from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from PIL import Image
from rest_framework.exceptions import ValidationError


def attachment_storage():
    return FileSystemStorage(location=settings.COMMENT_ATTACHMENT_ROOT, file_permissions_mode=0o600)


def validate_attachment(file):
    if not 0 < file.size <= 5 * 1024 * 1024:
        raise ValidationError({"attachment": "Choose a nonempty file up to 5 MB."})
    extension = Path(file.name).suffix.lower()
    formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}
    try:
        file.seek(0)
        if extension == ".txt":
            content = file.read().decode("utf-8")
            if any(ord(char) < 32 and char not in "\t\n\r" for char in content):
                raise ValueError
        elif extension in formats:
            with Image.open(file) as image:
                if image.format != formats[extension] or max(image.size) > 4096:
                    raise ValueError
                image.verify()
        else:
            raise ValueError
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValidationError({"attachment": "Upload a valid PNG, JPEG, or UTF-8 text file."}) from exc
    finally:
        file.seek(0)
