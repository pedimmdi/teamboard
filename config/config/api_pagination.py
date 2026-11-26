from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param


class LegacyArrayPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def uses_legacy_array(self, request):
        return self.page_query_param not in request.query_params and self.page_size_query_param not in request.query_params

    def get_page_size(self, request):
        # Preserve the array response and its largest practical first page for existing clients.
        if self.uses_legacy_array(request):
            return self.max_page_size
        return super().get_page_size(request)

    def get_previous_link(self):
        previous = super().get_previous_link()
        # DRF normally drops page=1. Keep it to preserve the paginated response shape.
        if previous and self.page.number == 2:
            return replace_query_param(previous, self.page_query_param, 1)
        return previous

    def get_paginated_response(self, data):
        if not self.uses_legacy_array(self.request):
            return super().get_paginated_response(data)
        headers = {"X-Total-Count": str(self.page.paginator.count)}
        if next_url := self.get_next_link():
            next_url = replace_query_param(next_url, self.page_size_query_param, self.max_page_size)
            headers["Link"] = f'<{next_url}>; rel="next"'
        return Response(data, headers=headers)

    def get_paginated_response_schema(self, schema):
        return {"oneOf": [super().get_paginated_response_schema(schema), schema]}
