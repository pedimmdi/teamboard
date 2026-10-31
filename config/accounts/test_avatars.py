from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from rest_framework.test import APITestCase

from workspaces.models import Workspace, WorkspaceMembership
from accounts.throttling import AvatarUploadThrottle


def image_file(name='photo.png', size=(24, 24), image_format='PNG'):
    buffer = BytesIO()
    Image.new('RGB', size, 'blue').save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f'image/{image_format.lower()}')


class ProfileAvatarTests(APITestCase):
    url = '/api/v1/accounts/me/'

    def setUp(self):
        cache.clear()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user(email='avatar@example.com', is_email_verified=True)
        self.client.force_authenticate(self.user)

    def upload(self, **data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.patch(self.url, {'avatar': image_file(), **data}, format='multipart')

    def test_upload_returns_public_url_and_preserves_names(self):
        response = self.upload(first_name='Alex')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['avatar'].startswith('http://testserver/media/profile_images/'))
        self.assertEqual(response.data['first_name'], 'Alex')
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.avatar.storage.exists(self.user.profile.avatar.name))

    def test_no_avatar_returns_null(self):
        self.assertIsNone(self.client.get(self.url).data['avatar'])

    def test_replacing_and_removing_delete_previous_file(self):
        self.upload()
        self.user.profile.refresh_from_db()
        first = self.user.profile.avatar.name
        storage = self.user.profile.avatar.storage
        self.upload()
        self.user.profile.refresh_from_db()
        second = self.user.profile.avatar.name
        self.assertNotEqual(first, second)
        self.assertFalse(storage.exists(first))
        self.assertTrue(storage.exists(second))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.url, {'avatar': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['avatar'])
        self.assertFalse(storage.exists(second))

    def test_name_only_update_keeps_avatar(self):
        avatar = self.upload().data['avatar']
        response = self.client.patch(self.url, {'first_name': 'Updated'}, format='json')
        self.assertEqual(response.data['avatar'], avatar)

    def test_rejects_non_image(self):
        response = self.upload(avatar=SimpleUploadedFile('fake.png', b'not an image', content_type='image/png'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('avatar', response.data)

    def test_rejects_oversized_file(self):
        image = image_file()
        image = SimpleUploadedFile('large.png', image.read() + b'0' * (5 * 1024 * 1024), content_type='image/png')
        self.assertEqual(self.upload(avatar=image).status_code, 400)

    def test_rejects_oversized_dimensions(self):
        self.assertEqual(self.upload(avatar=image_file(size=(4097, 1))).status_code, 400)

    def test_rejects_wrong_extension_and_unsupported_format(self):
        for image in (image_file(name='fake.jpg'), image_file(name='photo.gif', image_format='GIF')):
            with self.subTest(name=image.name):
                self.assertEqual(self.upload(avatar=image).status_code, 400)

    def test_accepts_jpeg_and_webp(self):
        for name, image_format in (('photo.jpg', 'JPEG'), ('photo.webp', 'WEBP')):
            with self.subTest(format=image_format):
                self.assertEqual(self.upload(avatar=image_file(name=name, image_format=image_format)).status_code, 200)

    def test_unauthenticated_upload_is_rejected(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.upload().status_code, 401)

    def test_upload_cannot_change_another_users_profile(self):
        other = get_user_model().objects.create_user(email='other@example.com')
        self.assertEqual(self.upload(user=other.pk).status_code, 200)
        other.profile.refresh_from_db()
        self.assertFalse(other.profile.avatar)

    def test_member_list_includes_avatar_and_null_fallback(self):
        avatar = self.upload().data['avatar']
        workspace = Workspace.objects.create(name='Avatar team')
        WorkspaceMembership.objects.create(workspace=workspace, user=self.user, role='owner')
        other = get_user_model().objects.create_user(email='member@example.com')
        WorkspaceMembership.objects.create(workspace=workspace, user=other)
        response = self.client.get(f'/api/v1/workspaces/{workspace.slug}/members/')
        self.assertEqual(response.status_code, 200)
        members = {member['user_id']: member for member in response.data['results']}
        self.assertEqual(members[self.user.pk]['avatar'], avatar)
        self.assertIsNone(members[other.pk]['avatar'])

    def test_user_deletion_cleans_up_image(self):
        self.upload()
        self.user.profile.refresh_from_db()
        name = self.user.profile.avatar.name
        storage = self.user.profile.avatar.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
        self.assertFalse(storage.exists(name))

    def test_invalid_profile_update_keeps_existing_image(self):
        avatar = self.upload().data['avatar']
        self.assertEqual(self.upload(first_name='x' * 151).status_code, 400)
        self.assertEqual(self.client.get(self.url).data['avatar'], avatar)

    def test_exif_is_removed_and_orientation_is_applied(self):
        output = BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "Private camera owner"
        Image.new("RGB", (32, 16), "blue").save(output, format="JPEG", exif=exif)
        response = self.upload(avatar=SimpleUploadedFile("camera.jpg", output.getvalue(), content_type="image/jpeg"))
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        with self.user.profile.avatar.open("rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.size, (16, 32))
                self.assertFalse(image.getexif())
                self.assertNotIn("exif", image.info)

    def test_admin_and_model_uploads_strip_png_metadata(self):
        output = BytesIO()
        metadata = PngInfo()
        metadata.add_text("Author", "Private author")
        Image.new("RGB", (16, 16), "blue").save(output, format="PNG", pnginfo=metadata)
        self.user.profile.avatar = SimpleUploadedFile("camera.png", output.getvalue(), content_type="image/png")
        self.user.profile.save()
        with self.user.profile.avatar.open("rb") as stored:
            with Image.open(stored) as image:
                self.assertNotIn("Author", image.info)

    def test_metadata_removal_preserves_palette_transparency(self):
        output = BytesIO()
        image = Image.new("P", (16, 16), 0)
        image.putpalette([0, 0, 255] + [0] * 765)
        image.save(output, format="PNG", transparency=0)
        response = self.upload(avatar=SimpleUploadedFile("transparent.png", output.getvalue(), content_type="image/png"))
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        with self.user.profile.avatar.open("rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.convert("RGBA").getpixel((0, 0))[3], 0)

    def test_upload_throttle_does_not_block_names_or_reads(self):
        with patch.object(AvatarUploadThrottle, "THROTTLE_RATES", {"avatar_upload": "1/hour"}):
            self.assertEqual(self.upload().status_code, 200)
            self.assertEqual(self.upload().status_code, 429)
            self.assertEqual(self.client.patch(self.url, {"first_name": "Alex"}, format="json").status_code, 200)
            self.assertEqual(self.client.get(self.url).status_code, 200)
            self.assertEqual(self.client.patch(self.url, {"avatar": None}, format="json").status_code, 200)

    def test_name_only_model_save_does_not_delete_current_avatar(self):
        self.upload()
        self.user.profile.refresh_from_db()
        current_name = self.user.profile.avatar.name
        storage = self.user.profile.avatar.storage
        self.user.profile.avatar = image_file("unused.png")
        self.user.profile.first_name = "Alex"
        with self.captureOnCommitCallbacks(execute=True):
            self.user.profile.save(update_fields=["first_name"])
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar.name, current_name)
        self.assertTrue(storage.exists(current_name))
