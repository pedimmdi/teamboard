
from django.urls import path

from .views import (
    CommentListCreateView,
    CommentDetailView,
    CommentAttachmentView,
)


app_name = "comments_api_v1"

urlpatterns = [
    path("<uuid:comment_id>/attachment/", CommentAttachmentView.as_view(), name="comment-attachment"),
    path(
        "",
        CommentListCreateView.as_view(),
        name="comment-list-create",
    ),
    path(
        "<uuid:comment_id>/",
        CommentDetailView.as_view(),
        name="comment-detail",
    ),
]
