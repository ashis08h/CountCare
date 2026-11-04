
from rest_framework.permissions import BasePermission

from .models import CompanyEmployee


class CashCountPermission(BasePermission):
    """
    Common permission checker for CashCount APIs.

    Each protected API must declare:
        required_permission = "customers_view"
        required_permission = "customers_add"
        required_permission = "customers_change"
        required_permission = "customers_delete"
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):

        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not user.is_active:
            return False

        membership = (
            CompanyEmployee.objects
            .select_related("company", "role")
            .filter(
                user=user,
                is_active=True,
                company__is_active=True,
            )
            .first()
        )

        if not membership:
            self.message = "Your company access is inactive."
            return False

        # Attach membership for use in API views.
        request.company_membership = membership

        # Owner has full access within their own company.
        if membership.role.name == "OWNER":
            return True

        required_permission = getattr(
            view,
            "required_permission",
            None,
        )

        # Fail closed: protected views must declare a permission.
        if not required_permission:
            self.message = "API permission is not configured."
            return False

        has_permission = membership.role.permissions.filter(
            codename=required_permission
        ).exists()

        if not has_permission:
            self.message = (
                f"Missing permission: {required_permission}"
            )

        return has_permission

    def has_object_permission(self, request, view, obj):

        membership = getattr(
            request,
            "company_membership",
            None,
        )

        if not membership:
            return False

        # Never allow access to an object from another company.
        if hasattr(obj, "company_id"):
            return obj.company_id == membership.company_id

        return False


def get_company_membership(user):
    return (
        CompanyEmployee.objects
        .select_related("company", "role")
        .filter(
            user=user,
            is_active=True,
            company__is_active=True,
        )
        .first()
    )


def is_company_owner(user):
    membership = get_company_membership(user)

    return bool(
        membership and membership.role.name == "OWNER"
    )
