
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone


# =========================================================
# COMMON VALIDATORS
# =========================================================

ZERO = Decimal("0.00")


# =========================================================
# 1. STOCK LOCATION
# =========================================================

class StockLocation(models.Model):
    """
    Company warehouse, office, branch or storage location.
    """

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="stock_locations",
    )

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)

    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_stock_locations"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_stock_location_code_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# =========================================================
# 2. MACHINE PRODUCT CATALOGUE
# =========================================================

class MachineProduct(models.Model):
    """
    Catalogue of currency-counting machines.
    Prices are stored EXCLUDING GST.
    """

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="machine_products",
    )

    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100)
    sku = models.CharField(max_length=50)

    hsn_code = models.CharField(max_length=20, blank=True)

    description = models.TextField(blank=True)

    warranty_months = models.PositiveIntegerField(default=12)

    mrp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("18.00"),
        validators=[
            MinValueValidator(ZERO),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    reorder_level = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_machine_products"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "sku"],
                name="unique_machine_sku_per_company",
            ),
            models.UniqueConstraint(
                fields=["company", "model_number"],
                name="unique_machine_model_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.model_number})"


# =========================================================
# 3. INVENTORY BALANCE
# =========================================================

class InventoryStock(models.Model):
    """
    Current stock balance for a product at a location.

    available_quantity = quantity_on_hand - reserved_quantity
    """

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="inventory_stock",
    )

    product = models.ForeignKey(
        MachineProduct,
        on_delete=models.PROTECT,
        related_name="stock_balances",
    )

    location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        related_name="stock_balances",
    )

    quantity_on_hand = models.PositiveIntegerField(default=0)

    reserved_quantity = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_inventory_stock"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "location"],
                name="unique_product_stock_per_location",
            ),
            models.CheckConstraint(
                condition=Q(
                    reserved_quantity__lte=models.F("quantity_on_hand")
                ),
                name="reserved_stock_not_above_on_hand",
            ),
        ]

    @property
    def available_quantity(self):
        return self.quantity_on_hand - self.reserved_quantity

    def __str__(self):
        return (
            f"{self.product.name} - {self.location.name}: "
            f"{self.available_quantity}"
        )


# =========================================================
# 4. CUSTOMER MACHINE / SERIAL NUMBER REGISTER
# =========================================================

class CustomerMachine(models.Model):
    """
    Tracks every physical machine using its serial number.

    A machine with no customer and status IN_STOCK is available
    in inventory. Once sold, it is assigned to a customer.
    """

    class MachineStatus(models.TextChoices):
        IN_STOCK = "IN_STOCK", "In Stock"
        RESERVED = "RESERVED", "Reserved"
        SOLD = "SOLD", "Sold"
        UNDER_REPAIR = "UNDER_REPAIR", "Under Repair"
        REPLACED = "REPLACED", "Replaced"
        RETIRED = "RETIRED", "Retired"

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="registered_machines",
    )

    product = models.ForeignKey(
        MachineProduct,
        on_delete=models.PROTECT,
        related_name="registered_machines",
    )

    location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="machines",
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="machines",
    )

    serial_number = models.CharField(max_length=100)

    status = models.CharField(
        max_length=20,
        choices=MachineStatus.choices,
        default=MachineStatus.IN_STOCK,
    )

    sale_item = models.ForeignKey(
        "VisitSaleItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="registered_machines",
    )

    purchase_date = models.DateField(null=True, blank=True)
    purchase_reference = models.CharField(max_length=100, blank=True)

    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)

    installation_date = models.DateField(null=True, blank=True)

    replaced_by = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replaces_machine",
    )

    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_customer_machines"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "serial_number"],
                name="unique_machine_serial_per_company",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status"],
                name="sm_company_status_idx",
            ),
            models.Index(
                fields=["customer", "status"],
                name="sm_customer_status_idx",
            ),
        ]

    @property
    def is_under_warranty(self):
        today = timezone.localdate()

        return bool(
            self.warranty_start_date
            and self.warranty_end_date
            and self.warranty_start_date <= today
            and self.warranty_end_date >= today
        )

    def __str__(self):
        return f"{self.serial_number} - {self.product.name}"


# =========================================================
# 5. CUSTOMER VISIT
# =========================================================

class CustomerVisit(models.Model):

    class VisitType(models.TextChoices):
        NEW_SALE = "NEW_SALE", "New Sale"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        REPLACEMENT = "REPLACEMENT", "Replacement"

    class VisitStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="customer_visits",
    )

    visit_number = models.CharField(
        max_length=30,
        editable=False,
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="sales_visits",
    )

    salesman = models.ForeignKey(
        "accounts.CompanyEmployee",
        on_delete=models.PROTECT,
        related_name="sales_visits",
    )

    visit_type = models.CharField(
        max_length=20,
        choices=VisitType.choices,
    )

    visit_date = models.DateField(default=timezone.localdate)
    visit_time = models.TimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=VisitStatus.choices,
        default=VisitStatus.DRAFT,
    )

    stock_location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_visits",
    )

    purpose = models.CharField(max_length=255, blank=True)
    visit_notes = models.TextField(blank=True)

    location_address = models.TextField(blank=True)

    customer_contact_person = models.CharField(
        max_length=150,
        blank=True,
    )

    customer_contact_number = models.CharField(
        max_length=15,
        blank=True,
    )
    customer_signature = models.ImageField(
        upload_to="sales/customer_signatures/",
        null=True,
        blank=True,
    )

    billing_address = models.ForeignKey(
        "customers.CustomerAddress",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_visits",
    )

    billing_address_snapshot = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_visits_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_customer_visits"
        ordering = ["-visit_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "visit_number"],
                name="unique_visit_number_per_company",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "visit_date"],
                name="sales_visit_company_date_idx",
            ),
            models.Index(
                fields=["company", "visit_type", "status"],
                name="sales_visit_type_status_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.visit_number:
            self.visit_number = (
                f"VIS-{uuid.uuid4().hex[:10].upper()}"
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.visit_number} - {self.customer}"


# =========================================================
# 6. VISIT SALE ITEM
# =========================================================

class VisitSaleItem(models.Model):
    """
    Product line in a new sale or replacement visit.

    unit_price and discount_amount are EXCLUSIVE of GST.
    """

    visit = models.ForeignKey(
        CustomerVisit,
        on_delete=models.CASCADE,
        related_name="sale_items",
    )

    product = models.ForeignKey(
        MachineProduct,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("18.00"),
        validators=[
            MinValueValidator(ZERO),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    class Meta:
        db_table = "sales_visit_items"

    @property
    def gross_amount(self):
        return self.unit_price * self.quantity

    @property
    def taxable_amount(self):
        return max(
            self.gross_amount - self.discount_amount,
            ZERO,
        )

    @property
    def gst_amount(self):
        return (
            self.taxable_amount * self.gst_rate
            / Decimal("100.00")
        ).quantize(Decimal("0.01"))

    @property
    def total_amount(self):
        return self.taxable_amount + self.gst_amount

    def __str__(self):
        return f"{self.product} x {self.quantity}"


# =========================================================
# 7. SERVICE RECORD
# =========================================================

class ServiceRecord(models.Model):

    class ServiceType(models.TextChoices):
        ROUTINE = "ROUTINE", "Routine Maintenance"
        REPAIR = "REPAIR", "Repair"
        CALIBRATION = "CALIBRATION", "Calibration"
        CLEANING = "CLEANING", "Cleaning"
        WARRANTY = "WARRANTY", "Warranty Service"
        REPLACEMENT = "REPLACEMENT", "Replacement"

    class ServiceStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        MACHINE_COLLECTED = "MACHINE_COLLECTED", "Machine Collected"

    class MachineCondition(models.TextChoices):
        WORKING = "WORKING", "Working"
        PARTIALLY_WORKING = (
            "PARTIALLY_WORKING",
            "Partially Working",
        )
        NOT_WORKING = "NOT_WORKING", "Not Working"

    class ReplacementReason(models.TextChoices):
        DAMAGED = "DAMAGED", "Damaged"
        BEYOND_REPAIR = "BEYOND_REPAIR", "Beyond Repair"
        UPGRADE = "UPGRADE", "Upgrade"
        WARRANTY = "WARRANTY", "Warranty Replacement"
        OTHER = "OTHER", "Other"

    visit = models.OneToOneField(
        CustomerVisit,
        on_delete=models.CASCADE,
        related_name="service_record",
    )

    machine = models.ForeignKey(
        CustomerMachine,
        on_delete=models.PROTECT,
        related_name="service_records",
    )

    replacement_machine = models.ForeignKey(
        CustomerMachine,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement_service_records",
    )

    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        blank=True,
    )

    customer_complaint = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    work_performed = models.TextField(blank=True)

    machine_condition = models.CharField(
        max_length=30,
        choices=MachineCondition.choices,
        blank=True,
    )

    service_status = models.CharField(
        max_length=25,
        choices=ServiceStatus.choices,
        default=ServiceStatus.PENDING,
    )

    is_under_warranty = models.BooleanField(default=False)

    visit_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    labour_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("18.00"),
        validators=[
            MinValueValidator(ZERO),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    exchange_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    replacement_reason = models.CharField(
        max_length=30,
        choices=ReplacementReason.choices,
        blank=True,
    )

    old_machine_returned = models.BooleanField(default=False)

    next_service_date = models.DateField(null=True, blank=True)

    service_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_service_records"

    @property
    def parts_amount(self):
        return sum(
            (part.total_amount for part in self.parts.all()),
            ZERO,
        )

    @property
    def taxable_amount(self):
        return (
            self.visit_charge
            + self.labour_charge
            + self.parts_amount
        )

    @property
    def gst_amount(self):
        return (
            self.taxable_amount * self.gst_rate
            / Decimal("100.00")
        ).quantize(Decimal("0.01"))

    @property
    def total_amount(self):
        return self.taxable_amount + self.gst_amount

    def __str__(self):
        return f"Service - {self.visit.visit_number}"


# =========================================================
# 8. SERVICE PARTS
# =========================================================

class ServicePart(models.Model):

    service_record = models.ForeignKey(
        ServiceRecord,
        on_delete=models.CASCADE,
        related_name="parts",
    )

    part_name = models.CharField(max_length=200)
    part_number = models.CharField(max_length=100, blank=True)

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    class Meta:
        db_table = "sales_service_parts"

    @property
    def total_amount(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return self.part_name


# =========================================================
# 9. STOCK MOVEMENT LEDGER
# =========================================================

class StockMovement(models.Model):
    """
    Immutable audit record for inventory changes.

    quantity is always positive.
    movement_type determines whether stock increases or decreases.
    """

    class MovementType(models.TextChoices):
        OPENING = "OPENING", "Opening Stock"
        PURCHASE = "PURCHASE", "Purchase"
        SALE = "SALE", "Sale"
        CUSTOMER_RETURN = "CUSTOMER_RETURN", "Customer Return"
        SUPPLIER_RETURN = "SUPPLIER_RETURN", "Supplier Return"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Stock Adjustment In"
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Stock Adjustment Out"
        TRANSFER_IN = "TRANSFER_IN", "Transfer In"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"
        REPLACEMENT = "REPLACEMENT", "Replacement"

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    product = models.ForeignKey(
        MachineProduct,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    movement_type = models.CharField(
        max_length=25,
        choices=MovementType.choices,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )

    reference_number = models.CharField(max_length=100, blank=True)

    visit = models.ForeignKey(
        CustomerVisit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    sale_item = models.ForeignKey(
        VisitSaleItem,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    machine = models.ForeignKey(
        CustomerMachine,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_stock_movements"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "product", "created_at"],
                name="sales_stock_product_date_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.movement_type} - "
            f"{self.product.name} - {self.quantity}"
        )


# =========================================================
# 10. VISIT PAYMENTS
# =========================================================

class VisitPayment(models.Model):

    class PaymentMode(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        CARD = "CARD", "Card"
        CHEQUE = "CHEQUE", "Cheque"

    class PaymentStatus(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        PENDING = "PENDING", "Pending"
        REFUNDED = "REFUNDED", "Refunded"

    visit = models.ForeignKey(
        CustomerVisit,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    receipt_number = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    payment_mode = models.CharField(
        max_length=20,
        choices=PaymentMode.choices,
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.RECEIVED,
    )

    transaction_reference = models.CharField(
        max_length=150,
        blank=True,
    )

    payment_date = models.DateTimeField(default=timezone.now)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visit_payments_received",
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_visit_payments"
        ordering = ["-payment_date"]

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = (
                f"REC-{uuid.uuid4().hex[:10].upper()}"
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} - {self.amount}"



# =========================================================
# 6A. DRAFT SALE ITEM MACHINE SELECTION
# =========================================================

class VisitSaleItemMachine(models.Model):
    """
    Stores machine serial numbers selected for a draft sale item.

    Selection does not deduct stock or mark a machine as sold.
    """

    sale_item = models.ForeignKey(
        VisitSaleItem,
        on_delete=models.CASCADE,
        related_name="machine_selections",
    )

    machine = models.ForeignKey(
        CustomerMachine,
        on_delete=models.PROTECT,
        related_name="draft_sale_selections",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_visit_item_machines"

        constraints = [
            models.UniqueConstraint(
                fields=["machine"],
                name="unique_machine_draft_sale_selection",
            ),
            models.UniqueConstraint(
                fields=["sale_item", "machine"],
                name="unique_machine_per_sale_item",
            ),
        ]

    def __str__(self):
        return f"{self.sale_item} - {self.machine.serial_number}"

