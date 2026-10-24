from django.urls import include, path

urlpatterns = [
    path("accounts/", include("accounts.api.v1.urls")),
    path("organizations/", include("organizations.api.v1.urls")),
]