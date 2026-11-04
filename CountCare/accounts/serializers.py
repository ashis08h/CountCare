
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    CompanyEmployee,
    Role,
    Permission,
)


class StaffCreateSerializer(serializers.Serializer):

    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    email = serializers.EmailField()
    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )
    password = serializers.CharField(
        min_length=8,
        write_only=True,
    )
    role_id = serializers.IntegerField()

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "Username is already registered."
            )
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Email is already registered."
            )
        return value

    def validate_role_id(self, value):

        membership = self.context["membership"]

        role = Role.objects.filter(
            id=value,
            company=membership.company,
        ).first()

        if not role:
            raise serializers.ValidationError(
                "Invalid role for this company."
            )

        if role.name == "OWNER":
            raise serializers.ValidationError(
                "The OWNER role cannot be assigned to staff."
            )

        return value


class StaffListSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    first_name = serializers.CharField(
        source="user.first_name",
        read_only=True,
    )

    last_name = serializers.CharField(
        source="user.last_name",
        read_only=True,
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    role_name = serializers.CharField(
        source="role.name",
        read_only=True,
    )

    class Meta:
        model = CompanyEmployee
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "role_name",
            "is_active",
            "joined_at",
        ]


class RoleSerializer(serializers.ModelSerializer):

    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        source="permissions",
        required=False,
    )

    permission_details = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "permission_ids",
            "permission_details",
            "is_system_role",
        ]
        read_only_fields = [
            "id",
            "is_system_role",
            "permission_details",
        ]

    def get_permission_details(self, obj):
        return [
            {
                "id": permission.id,
                "module": permission.module,
                "action": permission.action,
                "codename": permission.codename,
            }
            for permission in obj.permissions.all()
        ]

    def validate_name(self, value):

        if value.strip().upper() == "OWNER":
            raise serializers.ValidationError(
                "OWNER is a reserved role name."
            )

        return value.strip()

    def validate(self, attrs):

        permissions = attrs.get("permissions", [])

        allowed_ids = {
            permission.id
            for permission in permissions
        }

        if len(allowed_ids) != len(permissions):
            raise serializers.ValidationError(
                "Duplicate permissions are not allowed."
            )

        return attrs
