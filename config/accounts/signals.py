from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Profile
from .images import normalize_avatar


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(pre_save, sender=Profile)
def remember_previous_avatar(sender, instance, using, **kwargs):
    if kwargs.get("raw"):
        return
    previous = sender.objects.using(using).filter(pk=instance.pk).first() if instance.pk else None
    instance._previous_avatar = previous.avatar if previous else None
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "avatar" not in update_fields:
        instance._previous_avatar = None
        return
    if instance.avatar and not instance.avatar._committed:
        instance.avatar = normalize_avatar(instance.avatar)


@receiver(post_save, sender=Profile)
def delete_replaced_avatar(sender, instance, using, **kwargs):
    previous = getattr(instance, '_previous_avatar', None)
    if previous and previous.name != instance.avatar.name:
        transaction.on_commit(lambda: previous.delete(save=False), using=using, robust=True)


@receiver(post_delete, sender=Profile)
def delete_profile_avatar(sender, instance, using, **kwargs):
    if instance.avatar:
        transaction.on_commit(lambda: instance.avatar.delete(save=False), using=using, robust=True)
