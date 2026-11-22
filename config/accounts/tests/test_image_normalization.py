from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from django.core.exceptions import ValidationError
from accounts.images import normalize_avatar


class AvatarNormalizationTests(SimpleTestCase):
    def test_corrupt_png_checksum_is_a_validation_error(self):
        source = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(source, format="PNG")
        data = bytearray(source.getvalue())
        index = data.index(b"IDAT")
        length = int.from_bytes(data[index-4:index], "big")
        data[index+4+length] ^= 1
        value = SimpleUploadedFile("corrupt.png", bytes(data))
        with self.assertRaises(ValidationError):
            normalize_avatar(value)
        self.assertEqual(value.tell(), 0)

    def test_new_avatar_is_bounded_webp_without_metadata(self):
        source = BytesIO()
        Image.new("RGB", (2048, 1024), "blue").save(source, format="PNG")
        output = normalize_avatar(SimpleUploadedFile("large.png", source.getvalue()))
        self.assertTrue(output.name.endswith(".webp"))
        with Image.open(output) as result:
            self.assertEqual(result.format, "WEBP")
            self.assertEqual(result.size, (512, 256))
            self.assertFalse(result.getexif())


