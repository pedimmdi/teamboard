from contextlib import asynccontextmanager

import httpx2
from config.mcp_local_asgi import create_mcp_application
from django.conf import settings


@asynccontextmanager
async def mcp_test_client():
    # The SDK starts each session manager once. Tests get independent lifespans.
    application, server = create_mcp_application()
    transport = httpx2.ASGITransport(app=application, client=("127.0.0.1", 51234))
    async with (
        server.session_manager.run(),
        httpx2.AsyncClient(transport=transport, base_url=settings.MCP_LOCAL_ISSUER) as client,
    ):
        yield client
