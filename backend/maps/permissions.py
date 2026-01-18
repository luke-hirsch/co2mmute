from rest_framework import permissions


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    The request is authenticated as a staff user, or is a read-only request.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user and request.user.is_staff
