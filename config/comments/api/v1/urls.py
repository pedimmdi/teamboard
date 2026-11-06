
from django.urls import path

from .views import (
    CommentListCreateView,
    CommentDetailView,
)


app_name = "comments_api_v1"

urlpatterns = [
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
