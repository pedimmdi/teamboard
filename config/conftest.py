"""Isolate unit tests; Redis integration tests opt into real services explicitly."""
import pytest

@pytest.fixture(autouse=True)
def isolated_infrastructure(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.CELERY_TASK_ALWAYS_EAGER = True
