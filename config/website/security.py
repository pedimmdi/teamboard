
from io import BytesIO

from rest_framework.exceptions import APIException
from rest_framework.parsers import JSONParser
from rest_framework.throttling import ScopedRateThrottle


class ContactPayloadTooLarge(APIException):
    status_code = 413
    default_detail = "Contact request payload is too large."
    default_code = "payload_too_large"


class LimitedContactJSONParser(JSONParser):
    """
    Limit Contact JSON payloads before decoding them.

    The limit applies to the actual request stream,
    not only the untrusted Content-Length header.
    """

    max_bytes = 32 * 1024

    def parse(self, stream, media_type=None, parser_context=None):
        payload = bytearray()

        while len(payload) <= self.max_bytes:
            remaining = self.max_bytes + 1 - len(payload)
            chunk = stream.read(min(8192, remaining))

            if not chunk:
                break

            payload.extend(chunk)

            if len(payload) > self.max_bytes:
                raise ContactPayloadTooLarge()

        return super().parse(
            BytesIO(bytes(payload)),
            media_type=media_type,
            parser_context=parser_context,
        )


class ContactSubmissionThrottle(ScopedRateThrottle):
    """
    Do not trust client-supplied forwarding headers.

    Use the address observed by Django. Trusted proxy
    IP forwarding must be configured at deployment.
    """

    def get_ident(self, request):
        return request.META.get("REMOTE_ADDR") or "unknown"
