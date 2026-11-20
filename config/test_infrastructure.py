"""Real Redis checks: run with RUN_REDIS_TESTS=1; never flush shared databases."""
import asyncio
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from channels_redis.core import RedisChannelLayer
from django.core.cache.backends.redis import RedisCache

pytestmark = pytest.mark.skipif(os.environ.get("RUN_REDIS_TESTS") != "1", reason="Requires real Redis")


def test_cache_is_shared_across_processes():
    location = os.environ.get("REDIS_CACHE_URL", "redis://redis:6379/1")
    prefix = "test:" + uuid4().hex
    cache = RedisCache(location, {"KEY_PREFIX": prefix, "OPTIONS": {"socket_timeout": 2}})
    try:
        cache.set("counter", 7, timeout=30)
        script = "from django.core.cache.backends.redis import RedisCache; import sys; c=RedisCache(sys.argv[1], {'KEY_PREFIX':sys.argv[2]}); print(c.get('counter')); c.incr('counter')"
        result = subprocess.run([sys.executable, "-c", script, location, prefix], check=True, capture_output=True, text=True, timeout=15)
        assert result.stdout.strip() == "7"
        assert cache.get("counter") == 8
        assert cache._cache.get_client().ttl(cache.make_key("counter")) <= 30
    finally:
        cache.delete("counter")


def test_channel_group_delivers_between_processes():
    location = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    async def exercise():
        layer = RedisChannelLayer(hosts=[location], prefix="test:" + uuid4().hex)
        channel = await layer.new_channel()
        group = "test." + uuid4().hex
        try:
            await layer.group_add(group, channel)
            script = "from channels_redis.core import RedisChannelLayer; from asgiref.sync import async_to_sync; import sys; l=RedisChannelLayer(hosts=[sys.argv[1]],prefix=sys.argv[2]); async_to_sync(l.group_send)(sys.argv[3], {'type':'probe.event','value':7})"
            await asyncio.to_thread(subprocess.run, [sys.executable, "-c", script, location, layer.prefix, group], check=True, capture_output=True, timeout=15)
            assert await asyncio.wait_for(layer.receive(channel), timeout=5) == {"type": "probe.event", "value": 7}
        finally:
            await layer.group_discard(group, channel)
            await layer.close_pools()
    async_to_sync(exercise)()


def test_throttle_history_is_shared_across_processes():
    from types import SimpleNamespace
    from rest_framework.throttling import UserRateThrottle
    location = os.environ.get("REDIS_CACHE_URL", "redis://redis:6379/1")
    prefix = "test:" + uuid4().hex
    store = RedisCache(location, {"KEY_PREFIX": prefix})
    class Probe(UserRateThrottle):
        rate = "1/min"
        scope = "probe"
        cache = store
    request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True, pk=uuid4().hex))
    probe = Probe()
    try:
        assert probe.allow_request(request, None)
        script = """import django; django.setup()
import sys
from types import SimpleNamespace
from django.core.cache.backends.redis import RedisCache
from rest_framework.throttling import UserRateThrottle
class Probe(UserRateThrottle):
    rate = '1/min'
    scope = 'probe'
    cache = RedisCache(sys.argv[1], {'KEY_PREFIX':sys.argv[2]})
print(Probe().allow_request(SimpleNamespace(user=SimpleNamespace(is_authenticated=True,pk=sys.argv[3])),None))
"""
        result = subprocess.run([sys.executable, "-c", script, location, prefix, request.user.pk], check=True, capture_output=True, text=True, timeout=15)
        assert result.stdout.strip() == "False"
    finally:
        store.delete(probe.get_cache_key(request, None))


def test_redis_cache_outage_does_not_silently_bypass_throttles():
    from redis.exceptions import ConnectionError
    cache = RedisCache("redis://127.0.0.1:1/0", {"OPTIONS": {"socket_connect_timeout": 0.2, "socket_timeout": 0.2}})
    with pytest.raises(ConnectionError):
        cache.get("unreachable")
