from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .models import Company, CompanyEmployee, Role, Permission

from django.views.decorators.csrf import ensure_csrf_cookie

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .permissions import CashCountPermission, is_company_owner
from .serializers import (
    StaffCreateSerializer,
    StaffListSerializer,
    RoleSerializer,
)


# --------------------------------------------------
# Default permissions and owner role
# --------------------------------------------------

DEFAULT_MODULES = [
    "dashboard",
    "customers",
    "products",
    "inventory",
    "quotations",
    "sales",
    "payments",
    "reports",
    "employees",
    "company",
]

DEFAULT_ACTIONS = [
    "view",
    "add",
    "change",
    "delete",
    "approve",
    "export",
]


def create_company_owner_role(company):
    """
    Create all available permissions and assign them
    to the company's OWNER role.
    """

    permission_objects = []

    for module in DEFAULT_MODULES:
        for action in DEFAULT_ACTIONS:
            codename = f"{module}_{action}"

            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={
                    "module": module,
                    "action": action,
                    "description": f"{action.title()} {module}",
                },
            )

            permission_objects.append(permission)

    owner_role, _ = Role.objects.get_or_create(
        company=company,
        name="OWNER",
        defaults={
            "description": "Company owner with full company permissions.",
            "is_system_role": True,
        },
    )

    owner_role.permissions.set(permission_objects)

    return owner_role


# --------------------------------------------------
# Company Registration
# --------------------------------------------------

@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def register_company(request):

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":

        company_name = request.POST.get("company_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        gst_number = request.POST.get("gst_number", "").strip()
        registration_number = request.POST.get(
            "registration_number", ""
        ).strip()

        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        errors = []

        if not company_name:
            errors.append("Company name is required.")

        if not username:
            errors.append("Username is required.")

        if not email:
            errors.append("Email address is required.")

        if not password:
            errors.append("Password is required.")

        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")

        if password != confirm_password:
            errors.append("Passwords do not match.")

        if User.objects.filter(username__iexact=username).exists():
            errors.append("This username is already registered.")

        if User.objects.filter(email__iexact=email).exists():
            errors.append("This email address is already registered.")

        if errors:
            for error in errors:
                messages.error(request, error)

            return render(
                request,
                "accounts/register.html",
                {"form_data": request.POST},
            )

        try:
            with transaction.atomic():

                company = Company.objects.create(
                    name=company_name,
                    email=email,
                    phone=phone,
                    gst_number=gst_number or None,
                    registration_number=registration_number or None,
                )

                owner_role = create_company_owner_role(company)

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=username,
                )

                CompanyEmployee.objects.create(
                    user=user,
                    company=company,
                    role=owner_role,
                    is_active=True,
                )

            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )

            messages.success(
                request,
                f"Welcome to CashCount, {company.name}!",
            )

            return redirect("dashboard")

        except Exception:
            messages.error(
                request,
                "Unable to create your company account. Please try again.",
            )

    return render(request, "accounts/register.html")


# --------------------------------------------------
# Login
# --------------------------------------------------

@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def login_view(request):

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":

        username_or_email = request.POST.get(
            "username", ""
        ).strip()

        password = request.POST.get("password", "")

        username = username_or_email

        # Allow login using either username or email.
        if "@" in username_or_email:
            matching_users = User.objects.filter(
                email__iexact=username_or_email
            )

            if matching_users.count() == 1:
                username = matching_users.first().username
            else:
                messages.error(
                    request,
                    "Invalid username/email or password.",
                )
                return render(request, "accounts/login.html")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            messages.error(
                request,
                "Invalid username/email or password.",
            )

        elif not user.is_active:
            messages.error(
                request,
                "Your account is inactive. Contact your company owner.",
            )

        else:
            membership = (
                CompanyEmployee.objects
                .select_related("company", "role")
                .filter(user=user, is_active=True)
                .first()
            )

            if not membership or not membership.company.is_active:
                messages.error(
                    request,
                    "Your company access is inactive. Contact your administrator.",
                )
            else:
                login(request, user)

                next_url = request.GET.get("next")

                if next_url and next_url.startswith("/"):
                    return redirect(next_url)

                return redirect("dashboard")

    return render(request, "accounts/login.html")


# --------------------------------------------------
# Logout
# --------------------------------------------------

@require_http_methods(["POST"])
def logout_view(request):

    logout(request)

    messages.success(request, "You have been logged out successfully.")

    return redirect("login")


# ==================================================
# STAFF MANAGEMENT
# Owner-only APIs
# ==================================================

class StaffListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, CashCountPermission]
    required_permission = "employees_view"

    def get(self, request):

        membership = request.company_membership

        employees = (
            CompanyEmployee.objects
            .filter(company=membership.company)
            .exclude(role__name="OWNER")
            .select_related("user", "role")
            .order_by("-joined_at")
        )

        serializer = StaffListSerializer(
            employees,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request):

        if not is_company_owner(request.user):
            return Response(
                {"detail": "Only the company owner can create staff."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StaffCreateSerializer(
            data=request.data,
            context={
                "membership": request.company_membership,
            },
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        role = get_object_or_404(
            Role,
            id=data["role_id"],
            company=request.company_membership.company,
        )

        with transaction.atomic():

            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password"],
                first_name=data["first_name"],
                last_name=data.get("last_name", ""),
            )

            employee = CompanyEmployee.objects.create(
                user=user,
                company=request.company_membership.company,
                role=role,
                is_active=True,
            )

        return Response(
            {
                "message": "Staff account created successfully.",
                "employee": StaffListSerializer(employee).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StaffDetailAPIView(APIView):

    permission_classes = [IsAuthenticated, CashCountPermission]
    required_permission = "employees_view"

    def get_employee(self, request, employee_id):

        return get_object_or_404(
            CompanyEmployee.objects.select_related(
                "user", "company", "role"
            ),
            id=employee_id,
            company=request.company_membership.company,
        )

    def patch(self, request, employee_id):

        if not is_company_owner(request.user):
            return Response(
                {"detail": "Only the company owner can update staff."},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee = self.get_employee(request, employee_id)

        if employee.role.name == "OWNER":
            return Response(
                {"detail": "Owner account cannot be modified here."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_active = request.data.get("is_active")

        if is_active is not None:
            if not isinstance(is_active, bool):
                return Response(
                    {"detail": "is_active must be true or false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            employee.is_active = is_active
            employee.save(update_fields=["is_active"])

        role_id = request.data.get("role_id")

        if role_id is not None:

            role = get_object_or_404(
                Role,
                id=role_id,
                company=employee.company,
            )

            if role.name == "OWNER":
                return Response(
                    {"detail": "Cannot assign OWNER role."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            employee.role = role
            employee.save(update_fields=["role"])

        return Response({
            "message": "Staff account updated successfully.",
            "employee": StaffListSerializer(employee).data,
        })

    def delete(self, request, employee_id):

        if not is_company_owner(request.user):
            return Response(
                {"detail": "Only the company owner can remove staff."},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee = self.get_employee(request, employee_id)

        if employee.role.name == "OWNER":
            return Response(
                {"detail": "Owner account cannot be deleted here."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Deactivate instead of deleting historical records.
        employee.is_active = False
        employee.user.is_active = False

        employee.save(update_fields=["is_active"])
        employee.user.save(update_fields=["is_active"])

        return Response({
            "message": "Staff account deactivated successfully."
        })


# ==================================================
# ROLE MANAGEMENT
# Owner-only APIs
# ==================================================

class RoleListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, CashCountPermission]
    required_permission = "employees_view"

    def get(self, request):

        roles = Role.objects.filter(
            company=request.company_membership.company
        ).prefetch_related("permissions")

        serializer = RoleSerializer(roles, many=True)

        return Response(serializer.data)

    def post(self, request):

        if not is_company_owner(request.user):
            return Response(
                {"detail": "Only the owner can create roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        permissions = serializer.validated_data.get(
            "permissions", []
        )

        # Prevent assigning permissions that are not in the
        # CashCount permission catalogue.
        allowed_permissions = set(
            Permission.objects.filter(
                id__in=[permission.id for permission in permissions]
            )
        )

        if len(allowed_permissions) != len(permissions):
            return Response(
                {"detail": "Invalid permission selection."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role = serializer.save(
            company=request.company_membership.company,
            is_system_role=False,
        )

        return Response(
            RoleSerializer(role).data,
            status=status.HTTP_201_CREATED,
        )


class RoleDetailAPIView(APIView):

    permission_classes = [IsAuthenticated, CashCountPermission]
    required_permission = "employees_view"

    def get_role(self, request, role_id):

        return get_object_or_404(
            Role.objects.prefetch_related("permissions"),
            id=role_id,
            company=request.company_membership.company,
        )

    def get(self, request, role_id):

        role = self.get_role(request, role_id)

        return Response(RoleSerializer(role).data)

    def put(self, request, role_id):

        if not is_company_owner(request.user):
            return Response(
                {"detail": "Only the owner can update roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        role = self.get_role(request, role_id)

        if role.name == "OWNER" or role.is_system_role:
            return Response(
                {"detail": "System roles cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RoleSerializer(
            role,
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        updated_role = serializer.save()

        return Response(RoleSerializer(updated_role).data)

    def delete(self, request, role_id):

        if not is_company_owner(request.user):
            return Response(
                {"detail": "Only the owner can delete roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        role = self.get_role(request, role_id)

        if role.name == "OWNER" or role.is_system_role:
            return Response(
                {"detail": "System roles cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role.employees.exists():
            return Response(
                {
                    "detail": (
                        "This role is assigned to employees. "
                        "Reassign them before deleting it."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        role.delete()

        return Response({
            "message": "Role deleted successfully."
        })


# ==================================================
# PERMISSION CATALOGUE
# ==================================================

class PermissionListAPIView(APIView):

    permission_classes = [IsAuthenticated, CashCountPermission]
    required_permission = "employees_view"

    def get(self, request):

        permissions = Permission.objects.all().order_by(
            "module", "action"
        )

        data = [
            {
                "id": item.id,
                "module": item.module,
                "action": item.action,
                "codename": item.codename,
                "description": item.description,
            }
            for item in permissions
        ]

        return Response(data)
