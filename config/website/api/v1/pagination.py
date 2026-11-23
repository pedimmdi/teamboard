
from rest_framework.pagination import CursorPagination, PageNumberPagination


class PublicBlogPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class PublicBlogSitemapPagination(CursorPagination):
    page_size = 250
    # Unlike publication times, primary keys cannot tie across page boundaries.
    ordering = "pk"
