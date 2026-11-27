from typing import Annotated

from pydantic import Field, StrictInt, StrictStr

PageNumber = Annotated[StrictInt, Field(ge=1, le=100)]
PageSize = Annotated[StrictInt, Field(ge=1, le=20)]
WorkspaceSlug = Annotated[
    StrictStr, Field(min_length=1, max_length=10, pattern=r"^[a-zA-Z0-9_-]+$")
]


def bounded_page(queryset, page, page_size):
    start = (page - 1) * page_size
    rows = list(queryset[start : start + page_size + 1])
    next_page = page + 1 if len(rows) > page_size and page < 100 else None
    return rows[:page_size], next_page
