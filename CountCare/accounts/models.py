
from django.db import models
from django.contrib.auth.models import User


class Company(models.Model):
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, blank=True, null=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True)
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Permission(models.Model):
    MODULE_CHOICES = [
        ("dashboard", "Dashboard"),
        ("customers", "Customer Management"),
        ("products", "Product Management"),
        ("inventory", "Inventory"),
        ("quotations", "Quotations"),
        ("sales", "Sales Orders"),
        ("payments", "Payments"),
        ("reports", "Reports"),
        ("employees", "Employee Management"),
        ("company", "Company Settings"),
    ]

    ACTION_CHOICES = [
        ("view", "View"),
        ("add", "Add"),
        ("change", "Edit"),
        ("delete", "Delete"),
        ("approve", "Approve"),
        ("export", "Export"),
    ]

    module = models.CharField(
        max_length=50,
        choices=MODULE_CHOICES
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )

    codename = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    class Meta:
        ordering = ["module", "action"]
        constraints = [
            models.UniqueConstraint(
                fields=["module", "action"],
                name="unique_module_action_permission"
            )
        ]

    def save(self, *args, **kwargs):
        self.codename = f"{self.module}_{self.action}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.codename


class Role(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="roles"
    )

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles"
    )

    is_system_role = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_role_name_per_company"
            )
        ]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class CompanyEmployee(models.Model):
    ROLE_OWNER = "OWNER"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company_membership"
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="employees"
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="employees"
    )

    is_active = models.BooleanField(default=True)

    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.company.name}"

    @property
    def is_owner(self):
        return self.role.name == self.ROLE_OWNER
