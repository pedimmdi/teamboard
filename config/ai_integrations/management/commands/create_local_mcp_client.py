from django.core.management.base import BaseCommand, CommandError
from oauth2_provider.models import get_application_model

from ai_integrations.security import is_loopback_http_url


class Command(BaseCommand):
    help = "Register one public OAuth client for local TeamBoard MCP testing."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--redirect-uri", required=True)

    def handle(self, *args, **options):
        name = options["name"].strip()
        redirect_uri = options["redirect_uri"]
        if not 1 <= len(name) <= 80:
            raise CommandError("Use a client name between 1 and 80 characters.")
        if not is_loopback_http_url(redirect_uri):
            raise CommandError(
                "Use an exact HTTP loopback callback with an explicit port."
            )
        application = get_application_model().objects.create(
            name=name,
            redirect_uris=redirect_uri,
            client_type="public",
            authorization_grant_type="authorization-code",
            client_secret="",
            skip_authorization=False,
        )
        self.stdout.write(application.client_id)
