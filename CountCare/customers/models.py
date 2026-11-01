from django.db import models

# Create your models here.

from django.conf import settings
import uuid


class Customer(models.Model):

    class CustomerType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        BUSINESS = "BUSINESS", "Business"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    customer_code = models.CharField(
        max_length=30,
        unique=True,
        editable=False
    )

    customer_type = models.CharField(
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.BUSINESS
    )

    business_name = models.CharField(
        max_length=200,
        blank=True
    )

    contact_person = models.CharField(max_length=150)

    mobile_number = models.CharField(max_length=15)

    alternate_mobile = models.CharField(
        max_length=15,
        blank=True
    )

    email = models.EmailField(blank=True)

    gst_number = models.CharField(
        max_length=15,
        blank=True
    )

    pan_number = models.CharField(
        max_length=10,
        blank=True
    )

    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.customer_code:
            self.customer_code = (
                f"CUS-{uuid.uuid4().hex[:10].upper()}"
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_code} - {self.contact_person}"

    class Meta:
        db_table = "customers"
        ordering = ["-created_at"]


class CustomerAddress(models.Model):

    class AddressType(models.TextChoices):
        BILLING = "BILLING", "Billing"
        SHIPPING = "SHIPPING", "Shipping"
        OFFICE = "OFFICE", "Office"
        HOME = "HOME", "Home"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses"
    )

    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices,
        default=AddressType.BILLING
    )

    address_line_1 = models.CharField(max_length=255)

    address_line_2 = models.CharField(
        max_length=255,
        blank=True
    )

    city = models.CharField(max_length=100)

    district = models.CharField(
        max_length=100,
        blank=True
    )

    state = models.CharField(max_length=100)

    pincode = models.CharField(max_length=10)

    country = models.CharField(
        max_length=100,
        default="India"
    )

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.customer_code} - {self.city}"

    class Meta:
        db_table = "customer_addresses"
        ordering = ["-is_default", "id"]


class CustomerImportBatch(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    file_name = models.CharField(max_length=255)

    file_type = models.CharField(max_length=10)

    total_rows = models.PositiveIntegerField(default=0)

    successful_rows = models.PositiveIntegerField(default=0)

    failed_rows = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} - {self.status}"

    class Meta:
        db_table = "customer_import_batches"
        ordering = ["-created_at"]


class CustomerImportRow(models.Model):

    class ImportRowStatus(models.TextChoices):
        VALID = "VALID", "Valid"
        INVALID = "INVALID", "Invalid"
        IMPORTED = "IMPORTED", "Imported"
        FAILED = "FAILED", "Failed"

    batch = models.ForeignKey(
        CustomerImportBatch,
        on_delete=models.CASCADE,
        related_name="rows"
    )

    row_number = models.PositiveIntegerField()

    # Original customer data from Excel/CSV
    row_data = models.JSONField(default=dict)

    # Validation or import errors
    errors = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20,
        choices=ImportRowStatus.choices,
        default=ImportRowStatus.VALID
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_rows"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_import_rows"
        ordering = ["row_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["batch", "row_number"],
                name="unique_customer_import_batch_row"
            )
        ]

    def __str__(self):
        return f"Batch {self.batch_id} - Row {self.row_number}"

