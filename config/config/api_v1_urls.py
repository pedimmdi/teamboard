from django.urls import include, path

urlpatterns = [
    path("accounts/", include("accounts.api.v1.urls")),
    path("workspaces/", include("workspaces.api.v1.urls")),
]