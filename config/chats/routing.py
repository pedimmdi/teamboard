
from django.urls import re_path

from chats.consumers import ChatConsumer


websocket_urlpatterns = [
    re_path(
        r"^ws/chats/"
        r"(?P<workspace_slug>[-a-zA-Z0-9_]+)/"
        r"(?P<conversation_id>"
        r"[0-9a-fA-F]{8}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{12})/$",
        ChatConsumer.as_asgi(),
    ),
]
