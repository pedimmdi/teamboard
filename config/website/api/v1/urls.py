
from django.urls import path

from .views import (
    ContactMessageSubmitView,
    PublicBlogPostDetailView,
    PublicBlogPostListView,
    PublicBlogSitemapView,
    PublicWebsitePolicyView,
)


app_name = "website_api_v1"


urlpatterns = [
    path(
        "contact/",
        ContactMessageSubmitView.as_view(),
        name="contact_submit",
    ),
    path(
        "blog/",
        PublicBlogPostListView.as_view(),
        name="blog_list",
    ),
    path(
        "blog/<str:slug>/",
        PublicBlogPostDetailView.as_view(),
        name="blog_detail",
    ),
    path("sitemap/", PublicBlogSitemapView.as_view(), name="blog_sitemap"),
    path("policy/", PublicWebsitePolicyView.as_view(), name="policy"),
]
