
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from rest_framework import (
    generics,
    permissions,
    status,
)
from rest_framework.response import Response

from website.services import (
    create_contact_message,
    get_public_blog_posts,
)
from website.security import (
    ContactSubmissionThrottle,
    LimitedContactJSONParser,
)

from .pagination import PublicBlogPagination
from .serializers import (
    ContactMessageSubmitResponseSerializer,
    ContactMessageSubmitSerializer,
    PublicBlogPostDetailSerializer,
    PublicBlogPostListSerializer,
)


class ContactMessageSubmitView(generics.GenericAPIView):
    """
    Public, write-only contact endpoint.
    """

    serializer_class = ContactMessageSubmitSerializer

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    parser_classes = [LimitedContactJSONParser]

    throttle_classes = [ContactSubmissionThrottle]
    throttle_scope = "website_contact"

    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Website"],
        operation_id="website_contact_submit",
        summary="Submit a public contact message",
        description=(
            "Accept a contact message from a visitor. "
            "Authentication is not required. "
            "Submitted messages are private and cannot "
            "be retrieved through this endpoint."
        ),
        auth=[],
        request=ContactMessageSubmitSerializer,
        responses={
            201: ContactMessageSubmitResponseSerializer,
            400: OpenApiResponse(
                description="Invalid contact form data."
            ),
            413: OpenApiResponse(
                description="Contact JSON payload exceeds 32 KB."
            ),
            415: OpenApiResponse(
                description="Only JSON requests are accepted."
            ),
            429: OpenApiResponse(
                description="Contact form rate limit exceeded."
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = dict(serializer.validated_data)

        # Discard simple bot submissions without disclosing
        # the spam-detection rule to the sender.
        if not validated_data.pop("website_url", ""):
            create_contact_message(**validated_data)

        return Response(
            {"detail": "Your message has been received."},
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Website"],
        operation_id="website_blog_list",
        summary="List published blog posts",
        description=(
            "Returns paginated public blog posts ordered "
            "by publication date, newest first. "
            "Drafts and future scheduled posts are excluded."
        ),
        auth=[],
    ),
)
class PublicBlogPostListView(generics.ListAPIView):
    """
    Public read-only article listing.
    """

    serializer_class = PublicBlogPostListSerializer

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    pagination_class = PublicBlogPagination

    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return get_public_blog_posts()


@extend_schema_view(
    get=extend_schema(
        tags=["Website"],
        operation_id="website_blog_detail",
        summary="Retrieve a published blog post",
        description=(
            "Returns a published article by its slug. "
            "Drafts, unpublished posts, and future "
            "scheduled posts return 404."
        ),
        auth=[],
        responses={
            200: PublicBlogPostDetailSerializer,
            404: OpenApiResponse(
                description="Published article not found."
            ),
        },
    ),
)
class PublicBlogPostDetailView(generics.RetrieveAPIView):
    """
    Public read-only article details.
    """

    serializer_class = PublicBlogPostDetailSerializer

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    lookup_field = "slug"
    lookup_url_kwarg = "slug"

    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return get_public_blog_posts()
