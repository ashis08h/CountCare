
from django.urls import path

from . import views


urlpatterns = [
    # Authentication
    path("register/", views.register_company, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Staff management
    path(
        "api/staff/",
        views.StaffListCreateAPIView.as_view(),
        name="staff-list-create",
    ),
    path(
        "api/staff/<int:employee_id>/",
        views.StaffDetailAPIView.as_view(),
        name="staff-detail",
    ),

    # Role management
    path(
        "api/roles/",
        views.RoleListCreateAPIView.as_view(),
        name="role-list-create",
    ),
    path(
        "api/roles/<int:role_id>/",
        views.RoleDetailAPIView.as_view(),
        name="role-detail",
    ),

    # Permission catalogue
    path(
        "api/permissions/",
        views.PermissionListAPIView.as_view(),
        name="permission-list",
    ),
]
