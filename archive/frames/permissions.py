from rest_framework.permissions import BasePermission, SAFE_METHODS


class AdminOrReadOnly(BasePermission):
    """
    Admin users have permission for all http methods,
    other users only have permission for GET, HEAD & OPTIONS
    """
    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS or
            request.user and
            request.user.is_superuser
        )
