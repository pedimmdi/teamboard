
import os

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

from channels.routing import (
    ProtocolTypeRouter,
    URLRouter,
)
from channels.security.websocket import (
    OriginValidator,
)
from django.conf import settings
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from chats.routing import websocket_urlpatterns
from chats.ws_auth import JWTWebSocketAuthMiddleware


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            JWTWebSocketAuthMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
            allowed_origins=[
                settings.FRONTEND_URL,
            ],
        ),
    }
)
