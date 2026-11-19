
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import ValidationError


MAX_FILES = 5
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_TOTAL_SIZE = 20 * 1024 * 1024

IMAGE_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
}


def chat_attachment_storage():
    return FileSystemStorage(
        location=settings.CHAT_ATTACHMENT_ROOT,
        file_permissions_mode=0o600,
    )


def validate_chat_attachments(files):
    files = list(files)

    if len(files) > MAX_FILES:
        raise ValidationError({
            "attachments": "Maximum 5 files per message.",
        })

    if sum(getattr(file, "size", 0) for file in files) > MAX_TOTAL_SIZE:
        raise ValidationError({
            "attachments": "Total attachment size cannot exceed 20 MB.",
        })

    for file in files:
        if not 0 < getattr(file, "size", 0) <= MAX_FILE_SIZE:
            raise ValidationError({
                "attachments": "Each file must be nonempty and at most 5 MB.",
            })

        extension = Path(file.name).suffix.lower()

        try:
            file.seek(0)

            if extension == ".txt":
                content = file.read().decode("utf-8")
                if any(
                    ord(char) < 32 and char not in "\t\n\r"
                    for char in content
                ):
                    raise ValueError("Invalid text content")

            elif extension in IMAGE_FORMATS:
                with Image.open(file) as image:
                    if (
                        image.format != IMAGE_FORMATS[extension]
                        or max(image.size) > 4096
                    ):
                        raise ValueError("Invalid image format or dimensions")
                    image.verify()
            else:
                raise ValueError("Unsupported file extension")

        except (
            ValueError,
            UnicodeError,
            OSError,
            SyntaxError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
        ) as exc:
            raise ValidationError({
                "attachments": "Upload valid PNG, JPEG or UTF-8 TXT files.",
            }) from exc
        finally:
            file.seek(0)

    return files
