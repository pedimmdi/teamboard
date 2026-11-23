from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from background.services import enqueue_avatar_file
from projects.models import Project
from workspaces.models import Workspace

from .avatar_cleanup import is_avatar_key, lock_avatar_key
from .models import Profile
from .images import normalize_avatar


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(pre_save, sender=Project)
@receiver(pre_save, sender=Workspace)
@receiver(pre_save, sender=Profile)
def remember_previous_avatar(sender, instance, using, **kwargs):
    if kwargs.get("raw"):
        return
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "avatar" not in update_fields:
        instance._previous_avatar = None
        instance._uploading_avatar = False
        return
    previous = current_avatar_key(sender, instance.pk, using)
    instance._previous_avatar = previous
    instance._uploading_avatar = bool(instance.avatar and not instance.avatar._committed)
    if instance._uploading_avatar:
        instance.avatar = normalize_avatar(instance.avatar)
    elif instance.avatar.name != previous and is_avatar_key(instance.avatar.name):
        lock_avatar_key(instance.avatar.name, using)
        if not instance.avatar.storage.exists(instance.avatar.name):
            raise ValidationError({"avatar": "The selected avatar no longer exists."})


def current_avatar_key(sender, pk, using):
    if pk is None:
        return None
    return (
        sender._base_manager.using(using).select_for_update().filter(pk=pk)
        .values_list("avatar", flat=True).first()
    )


@receiver(post_save, sender=Project)
@receiver(post_save, sender=Workspace)
@receiver(post_save, sender=Profile)
def delete_replaced_avatar(sender, instance, using, **kwargs):
    if kwargs.get("raw"):
        return
    if getattr(instance, "_uploading_avatar", False):
        lock_avatar_key(instance.avatar.name, using)
    previous = getattr(instance, "_previous_avatar", None)
    if previous != instance.avatar.name and is_avatar_key(previous):
        enqueue_avatar_file(previous, using=using)


@receiver(pre_delete, sender=Project)
@receiver(pre_delete, sender=Workspace)
@receiver(pre_delete, sender=Profile)
def remember_deleted_avatar(sender, instance, using, **kwargs):
    if sender is Project:
        # Match the workspace-then-project lock order used by project writes,
        # including when the collector reaches this project in a cascade.
        current_avatar_key(Workspace, instance.workspace_id, using)
    instance._deleted_avatar = current_avatar_key(sender, instance.pk, using)


@receiver(post_delete, sender=Project)
@receiver(post_delete, sender=Workspace)
@receiver(post_delete, sender=Profile)
def delete_resource_avatar(sender, instance, using, **kwargs):
    if is_avatar_key(instance._deleted_avatar):
        enqueue_avatar_file(instance._deleted_avatar, using=using)
