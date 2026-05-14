from rest_framework.permissions import BasePermission

class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            getattr(request.user, 'is_authenticated', False) and
            getattr(request.user, 'role', None) == 'patient'
        )

class IsParent(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            getattr(request.user, 'is_authenticated', False) and
            getattr(request.user, 'role', None) == 'parent'
        )