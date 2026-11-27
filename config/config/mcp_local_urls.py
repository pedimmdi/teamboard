from ai_integrations.approvals import TaskDeletionApprovalView
from ai_integrations.connections import ConnectionListView, RevokeConnectionsView
from ai_integrations.oauth import (
    ConsentView,
    LocalAuthorizeView,
    LocalRevokeView,
    LocalTokenView,
)
from ai_integrations.registration import ClientRegistrationView
from django.urls import include, path
from oauth2_provider.urls import metadata_urlpatterns

from .urls import (
    handler400 as handler400,
)
from .urls import (
    handler403 as handler403,
)
from .urls import (
    handler404 as handler404,
)
from .urls import (
    handler500 as handler500,
)
from .urls import (
    urlpatterns as teamboard_urls,
)

oauth_urls = [
    path("authorize/", LocalAuthorizeView.as_view(), name="authorize"),
    path("token/", LocalTokenView.as_view(), name="token"),
    path("revoke/", LocalRevokeView.as_view(), name="revoke-token"),
    path("register/", ClientRegistrationView.as_view(), name="dcr-register"),
]

# Keep oauth2_provider's discovery reverse names without mounting its
# application management, device grant, OIDC or dynamic registration endpoints.
urlpatterns = [
    path(
        "",
        include(
            (
                [*metadata_urlpatterns, path("oauth/", include(oauth_urls))],
                "oauth2_provider",
            ),
            namespace="oauth2_provider",
        ),
    ),
    path("api/v1/ai/consent/", ConsentView.as_view(), name="mcp-local-consent"),
    path("api/v1/ai/connections/", ConnectionListView.as_view(), name="ai-connections"),
    path("api/v1/ai/connections/revoke/", RevokeConnectionsView.as_view(), name="ai-revoke-all"),
    path("api/v1/ai/connections/<int:connection_id>/revoke/", RevokeConnectionsView.as_view(), name="ai-revoke-one"),
    path("api/v1/ai/approvals/tasks/<uuid:approval_id>/", TaskDeletionApprovalView.as_view(), name="ai-task-approval"),
    *teamboard_urls,
]
