"""Isolate unit tests; Redis integration tests opt into real services explicitly."""
import pytest

@pytest.fixture(autouse=True)
def isolated_infrastructure(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    # Only test fixture hashes: production settings and password validators stay unchanged.
    import os
    if os.environ.get("TEAMBOARD_FAST_TEST_HASHERS", "1") == "1":
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.CELERY_TASK_ALWAYS_EAGER = True
    from config.celery import app
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = True
    yield
    app.conf.task_always_eager = previous
