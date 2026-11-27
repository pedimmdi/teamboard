from ai_integrations.security import MCP_SCOPES, READ_SCOPE, REFRESH_IDLE_SECONDS

OAUTH_LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "mcp_events": {"class": "logging.StreamHandler"},
        "mcp_sdk_suppressed": {"class": "logging.NullHandler"},
    },
    "loggers": {
        "oauth2_provider": {"level": "WARNING"},
        "oauthlib": {"level": "WARNING"},
        "mcp": {"handlers": ["mcp_sdk_suppressed"], "propagate": False},
        "ai_integrations": {"handlers": ["mcp_events"], "level": "INFO", "propagate": False},
    },
}


def oauth_settings(issuer, schemes, *, confidential=False):
    return {
        "OIDC_ISS_ENDPOINT": issuer,
        "OIDC_ENABLED": False,
        "ACCESS_TOKEN_EXPIRE_SECONDS": 300,
        "AUTHORIZATION_CODE_EXPIRE_SECONDS": 60,
        "REFRESH_TOKEN_EXPIRE_SECONDS": REFRESH_IDLE_SECONDS,
        "PKCE_REQUIRED": True,
        "ROTATE_REFRESH_TOKEN": True,
        "REFRESH_TOKEN_REUSE_PROTECTION": True,
        "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
        "COMPLIANT_BCP_RFC9700_PKCE_REQUIRED": True,
        "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
        "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
        "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
        "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
        "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
        "COMPLIANT_BCP_RFC9700_REFRESH_TOKEN": True,
        "COMPLIANT_BCP_RFC9700_REDIRECT_URI_MATCHING": True,
        "ALLOWED_REDIRECT_URI_SCHEMES": schemes,
        "ALLOW_URI_WILDCARDS": False,
        "SCOPES": MCP_SCOPES,
        "DEFAULT_SCOPES": [READ_SCOPE],
        "OAUTH2_RESPONSE_TYPES_SUPPORTED": ["code"],
        "OAUTH2_GRANT_TYPES_SUPPORTED": ["authorization_code", "refresh_token"],
        "OAUTH2_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED": ["none", "client_secret_post"] if confidential else ["none"],
        "OAUTH2_PROTECTED_RESOURCE_IDENTIFIER": issuer + "/mcp",
        "OAUTH2_PROTECTED_RESOURCE_AUTHORIZATION_SERVERS": [issuer],
        "OAUTH2_VALIDATOR_CLASS": "ai_integrations.oauth.LocalOAuthValidator",
    }
