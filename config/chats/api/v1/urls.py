
from django.urls import path

from .views import (
    ProjectChatView,
    DirectChatListCreateView,
    ChatMessageListCreateView,
    ChatMessageDetailView,
    ChatAttachmentDownloadView,
)

app_name = "chats_api_v1"

urlpatterns = [
    path(
        "direct/",
        DirectChatListCreateView.as_view(),
        name="direct-list-create",
    ),
    path(
        "<uuid:conversation_id>/messages/",
        ChatMessageListCreateView.as_view(),
        name="message-list-create",
    ),
    path(
        "<uuid:conversation_id>/messages/<uuid:message_id>/",
        ChatMessageDetailView.as_view(),
        name="message-detail",
    ),
    path(
        "<uuid:conversation_id>/messages/<uuid:message_id>/attachments/<uuid:attachment_id>/",
        ChatAttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
]
