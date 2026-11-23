from hashlib import blake2b
from pathlib import PurePosixPath

from django.apps import apps
from django.core.files.storage import default_storage
from django.db import DEFAULT_DB_ALIAS, connections, router, transaction


AVATAR_MODELS = ("accounts.Profile", "workspaces.Workspace", "projects.Project")
AVATAR_PREFIXES = ("profile_images", "workspaces", "projects")


class AvatarCleanupMixin:
    """Keep an avatar write and its cleanup job in the same transaction."""

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        using = using or router.db_for_write(type(self), instance=self)
        if update_fields is not None:
            update_fields = frozenset(update_fields)
        save = super().save
        if update_fields is not None and "avatar" not in update_fields:
            return save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)
        with transaction.atomic(using=using):
            return save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)


def is_avatar_key(key):
    if not isinstance(key, str) or "\\" in key:
        return False
    parts = key.split("/")
    return (
        len(parts) == 3
        and parts[0] in AVATAR_PREFIXES
        and all(part and part not in {".", ".."} for part in parts[1:])
        and PurePosixPath(parts[-1]).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


def lock_avatar_key(key, using):
    # Django uses PostgreSQL for the application database. Use a namespaced
    # hash as the transaction lock shared by reattachments and cleanup workers.
    digest = blake2b(key.encode(), digest_size=8, person=b"teamboard.avatar").digest()
    lock_id = int.from_bytes(digest, "big", signed=True)
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])


def avatar_is_referenced(key, using=DEFAULT_DB_ALIAS):
    return any(
        apps.get_model(label)._base_manager.using(using).filter(avatar=key).exists()
        for label in AVATAR_MODELS
    )


def cleanup_avatar_file(key, using=DEFAULT_DB_ALIAS):
    if not is_avatar_key(key):
        raise ValueError("Invalid avatar storage key")
    with transaction.atomic(using=using):
        lock_avatar_key(key, using)
        if not avatar_is_referenced(key, using):
            try:
                default_storage.delete(key)
            except FileNotFoundError:
                pass
