from django.db.models import Q
from django.contrib.auth import get_user_model
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from chats.access import get_chat_workspace, get_conversation_or_404
from chats.models import Conversation, ChatMessage, ChatAttachment
from chats.services import (
    get_or_create_project_chat,
    get_or_create_direct_chat,
    create_chat_message,
    update_chat_message,
    delete_chat_message,
    get_chat_messages,
    message_response_queryset,
)
from chats.storage import chat_attachment_storage
from chats.unread import get_unread_chats, mark_chat_read
from config.api_pagination import LegacyArrayPagination
from .serializers import ChatReadSerializer, ChatUnreadSerializer
from workspaces.models import WorkspaceMembership
from .pagination import ChatMessagePagination
from .serializers import (
    ConversationSerializer,
    DirectCreateSerializer,
    ChatMessageSerializer,
    ChatMessageCreateSerializer,
    ChatMessageUpdateSerializer,
)


User = get_user_model()


class ProjectChatView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer

    @extend_schema(
        tags=["Chats"],
        summary="Get or initialize a project chat",
        responses={200: ConversationSerializer},
    )
    def get(self, request, *args, **kwargs):
        conversation = get_or_create_project_chat(
            workspace_slug=kwargs["slug"],
            project_id=kwargs["project_id"],
            actor=request.user,
        )
        return Response(
            ConversationSerializer(conversation).data
        )


class DirectChatListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer
    pagination_class = LegacyArrayPagination

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "chat_direct_create"
            return [ScopedRateThrottle()]
        return []

    @extend_schema(
        tags=["Chats"],
        summary="List own direct conversations",
        description=(
            "Pass page or page_size for a paginated object. Requests without those parameters "
            "return an array of up to 100 conversations, X-Total-Count, and a Link to the next "
            "page when more results exist."
        ),
        responses={200: ConversationSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        workspace = get_chat_workspace(
            workspace_slug=self.kwargs["slug"],
            actor=self.request.user,
        )
        return Conversation.objects.filter(
            Q(direct_user_low=self.request.user)
            | Q(direct_user_high=self.request.user),
            workspace=workspace,
            type=Conversation.Type.DIRECT,
        ).order_by("-updated_at", "-id")

    @extend_schema(
        tags=["Chats"],
        summary="Start or retrieve a direct conversation",
        request=DirectCreateSerializer,
        responses={200: ConversationSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = DirectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        workspace = get_chat_workspace(
            workspace_slug=kwargs["slug"],
            actor=request.user,
        )

        recipient_id = serializer.validated_data["recipient_id"]

        if not WorkspaceMembership.objects.filter(
            workspace=workspace,
            user_id=recipient_id,
            user__is_active=True,
        ).exists():
            raise Http404

        recipient = get_object_or_404(
            User,
            pk=recipient_id,
            is_active=True,
        )

        conversation = get_or_create_direct_chat(
            workspace_slug=kwargs["slug"],
            recipient=recipient,
            actor=request.user,
        )

        return Response(
            ConversationSerializer(conversation).data,
            status=status.HTTP_200_OK,
        )


class ChatMessageListCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatMessageSerializer
    pagination_class = ChatMessagePagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "chat_message_create"
            return [ScopedRateThrottle()]
        return []

    @extend_schema(
        tags=["Chats"],
        summary="List conversation messages",
        responses={200: ChatMessageSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = get_chat_messages(
            workspace_slug=kwargs["slug"],
            conversation_id=kwargs["conversation_id"],
            actor=request.user,
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(
            queryset, request, view=self
        )
        return paginator.get_paginated_response(
            ChatMessageSerializer(page, many=True).data
        )

    @extend_schema(
        tags=["Chats"],
        summary="Send a message with optional attachments",
        request=ChatMessageCreateSerializer,
        responses={201: ChatMessageSerializer},
    )
    def post(self, request, *args, **kwargs):
        data = request.data.copy()

        if request.content_type.startswith("multipart/"):
            data.setlist(
                "attachments",
                request.FILES.getlist("attachments"),
            )

        serializer = ChatMessageCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        message = create_chat_message(
            workspace_slug=kwargs["slug"],
            conversation_id=kwargs["conversation_id"],
            actor=request.user,
            **serializer.validated_data,
        )

        message = message_response_queryset().get(pk=message.pk)

        return Response(
            ChatMessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )


class ChatMessageDetailView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatMessageSerializer

    def get_message(self):
        conversation = get_conversation_or_404(
            workspace_slug=self.kwargs["slug"],
            conversation_id=self.kwargs["conversation_id"],
            actor=self.request.user,
        )
        return get_object_or_404(
            ChatMessage,
            pk=self.kwargs["message_id"],
            conversation=conversation,
        )

    @extend_schema(tags=["Chats"], summary="Retrieve a message, including an older reply target", responses={200: ChatMessageSerializer})
    def get(self, request, *args, **kwargs):
        return Response(ChatMessageSerializer(self.get_message()).data)

    @extend_schema(
        tags=["Chats"],
        summary="Edit own message",
        request=ChatMessageUpdateSerializer,
        responses={200: ChatMessageSerializer},
    )
    def patch(self, request, *args, **kwargs):
        message = self.get_message()
        serializer = ChatMessageUpdateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        message = update_chat_message(
            workspace_slug=kwargs["slug"],
            message_id=message.pk,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(
            ChatMessageSerializer(message).data
        )

    @extend_schema(
        tags=["Chats"],
        summary="Soft-delete own message",
        responses={204: None},
    )
    def delete(self, request, *args, **kwargs):
        message = self.get_message()
        delete_chat_message(
            workspace_slug=kwargs["slug"],
            message_id=message.pk,
            actor=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatAttachmentDownloadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    serializer_class = ChatMessageSerializer

    @extend_schema(
        tags=["Chats"],
        summary="Download a private chat attachment",
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
    )
    def get(self, request, *args, **kwargs):
        conversation = get_conversation_or_404(
            workspace_slug=kwargs["slug"],
            conversation_id=kwargs["conversation_id"],
            actor=request.user,
        )

        attachment = get_object_or_404(
            ChatAttachment.objects.select_related("message"),
            pk=kwargs["attachment_id"],
            message_id=kwargs["message_id"],
            message__conversation=conversation,
            message__deleted_at__isnull=True,
        )

        try:
            file = chat_attachment_storage().open(
                attachment.storage_key,
                "rb",
            )
        except (FileNotFoundError, OSError) as exc:
            raise Http404 from exc

        response = FileResponse(
            file,
            as_attachment=True,
            filename=attachment.filename,
            content_type="application/octet-stream",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ChatUnreadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatUnreadSerializer

    @extend_schema(tags=["Chats"], summary="Unread message totals for accessible workspace conversations", responses={200: ChatUnreadSerializer})
    def get(self, request, *args, **kwargs):
        return Response(ChatUnreadSerializer(get_unread_chats(workspace_slug=kwargs["slug"], actor=request.user)).data)


class ChatReadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatReadSerializer

    @extend_schema(tags=["Chats"], summary="Acknowledge displayed messages up to an ordered message cursor", request=ChatReadSerializer, responses={204: None})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mark_chat_read(workspace_slug=kwargs["slug"], conversation_id=kwargs["conversation_id"], actor=request.user, **serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)
