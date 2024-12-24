from rest_framework import permissions


class IsAdminOrReadOnly(permissions.IsAdminUser):
    def has_permission(self, request, view):
        admin_permission = super().has_permission(request, view)
        return request.method == 'GET' or admin_permission


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        if request.user.is_staff:
            return True

        return obj.owner == request.user
