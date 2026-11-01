from django.conf import settings
from rest_framework.permissions import BasePermission, IsAuthenticated


class ToggleAPIPermission(BasePermission):

    def has_permission(self, request, view):
        if not settings.API_SECURITY_ENABLED:
            return True

        return IsAuthenticated().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if not settings.API_SECURITY_ENABLED:
            return True

        return IsAuthenticated().has_object_permission(request, view, obj)