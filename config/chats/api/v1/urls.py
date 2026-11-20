
from django.urls import path

from .views import (
    ProjectChatView,
    ChatReadView,
    ChatUnreadView,
    DirectChatListCreateView,
    ChatMessageListCreateView,
    ChatMessageDetailView,
    ChatAttachmentDownloadView,
)

app_name = "chats_api_v1"

urlpatterns = [
    path("unread/", ChatUnreadView.as_view(), name="unread"),
    path("<uuid:conversation_id>/read/", ChatReadView.as_view(), name="read"),
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
