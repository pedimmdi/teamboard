from rest_framework.throttling import UserRateThrottle


class AvatarUploadThrottle(UserRateThrottle):
    scope = "avatar_upload"

    def allow_request(self, request, view):
        if request.method != "PATCH" or "avatar" not in request.FILES:
            return True
        return super().allow_request(request, view)
