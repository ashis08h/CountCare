
# sales/serializers.py

from rest_framework import serializers

from sales.models import (
    StockLocation,
    MachineProduct,
    InventoryStock,
    CustomerMachine,
    StockMovement,
    VisitPayment
)

from customers.models import Customer, CustomerAddress
from accounts.models import CompanyEmployee
from sales.models import CustomerVisit
from sales.models import VisitSaleItem, VisitSaleItemMachine
from django.db.models import Exists, OuterRef



class StockLocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = StockLocation
        fields = [
            "id",
            "name",
            "code",
            "address",
            "city",
            "state",
            "pincode",
            "is_default",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_code(self, value):

        value = value.strip().upper()

        request = self.context.get("request")
        company = request.company_membership.company

        queryset = StockLocation.objects.filter(
            company=company,
            code__iexact=value,
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "This location code already exists in your company."
            )

        return value

    def validate(self, attrs):

        is_default = attrs.get(
            "is_default",
            getattr(self.instance, "is_default", False),
        )

        is_active = attrs.get(
            "is_active",
            getattr(self.instance, "is_active", True),
        )

        if is_default and not is_active:
            raise serializers.ValidationError({
                "is_default": "An inactive location cannot be the default location."
            })

        return attrs


class MachineProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = MachineProduct
        fields = [
            "id", "name", "brand", "model_number",
            "sku", "hsn_code", "description",
            "warranty_months", "mrp",
            "selling_price", "gst_rate",
            "reorder_level", "is_active",
        ]


class InventoryStockSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.name", read_only=True
    )

    location_name = serializers.CharField(
        source="location.name", read_only=True
    )

    available_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = InventoryStock
        fields = [
            "id", "product", "product_name",
            "location", "location_name",
            "quantity_on_hand", "reserved_quantity",
            "available_quantity", "updated_at",
        ]
        read_only_fields = fields


class CustomerMachineSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.name", read_only=True
    )

    location_name = serializers.CharField(
        source="location.name", read_only=True
    )

    is_under_warranty = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomerMachine
        fields = [
            "id", "product", "product_name",
            "location", "location_name",
            "customer", "serial_number",
            "status", "purchase_date",
            "purchase_reference",
            "warranty_start_date",
            "warranty_end_date",
            "installation_date",
            "is_under_warranty",
        ]
        read_only_fields = fields


class StockMovementSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.name", read_only=True
    )

    location_name = serializers.CharField(
        source="location.name", read_only=True
    )

    class Meta:
        model = StockMovement
        fields = [
            "id", "product", "product_name",
            "location", "location_name",
            "movement_type", "quantity",
            "unit_cost", "reference_number",
            "machine", "visit", "sale_item",
            "notes", "created_by", "created_at",
        ]
        read_only_fields = fields


class ReceiveMachineSerializer(serializers.Serializer):

    product_id = serializers.IntegerField(min_value=1)
    location_id = serializers.IntegerField(min_value=1)

    serial_number = serializers.CharField(max_length=100)

    movement_type = serializers.ChoiceField(
        choices=["OPENING", "PURCHASE"],
        default="PURCHASE",
    )

    purchase_reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )

    unit_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        default=0,
    )

    def validate(self, attrs):
        company = self.context["company"]

        try:
            attrs["product"] = MachineProduct.objects.get(
                pk=attrs["product_id"],
                company=company,
                is_active=True,
            )
        except MachineProduct.DoesNotExist:
            raise serializers.ValidationError({
                "product_id": "Invalid company product."
            })

        try:
            attrs["location"] = StockLocation.objects.get(
                pk=attrs["location_id"],
                company=company,
                is_active=True,
            )
        except StockLocation.DoesNotExist:
            raise serializers.ValidationError({
                "location_id": "Invalid company location."
            })

        return attrs


class TransferMachineSerializer(serializers.Serializer):

    machine_id = serializers.IntegerField(min_value=1)
    destination_location_id = serializers.IntegerField(min_value=1)

    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, attrs):
        company = self.context["company"]

        try:
            attrs["destination_location"] = StockLocation.objects.get(
                pk=attrs["destination_location_id"],
                company=company,
                is_active=True,
            )
        except StockLocation.DoesNotExist:
            raise serializers.ValidationError({
                "destination_location_id": "Invalid destination."
            })

        return attrs



class SaleCustomerAddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerAddress
        fields = [
            "id",
            "address_type",
            "address_line_1",
            "address_line_2",
            "city",
            "district",
            "state",
            "pincode",
            "country",
            "is_default",
        ]



class SaleCustomerLookupSerializer(serializers.ModelSerializer):

    addresses = serializers.SerializerMethodField()

    default_billing_address_id = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_code",
            "customer_type",
            "business_name",
            "contact_person",
            "mobile_number",
            "alternate_mobile",
            "email",
            "gst_number",
            "addresses",
            "default_billing_address_id",
        ]

    def get_addresses(self, obj):

        addresses = CustomerAddress.objects.filter(
            customer=obj
        ).order_by("id")

        return SaleCustomerAddressSerializer(
            addresses,
            many=True
        ).data

    def get_default_billing_address_id(self, obj):

        address = CustomerAddress.objects.filter(
            customer=obj,
            address_type="BILLING",
            is_default=True,
        ).first()

        return address.id if address else None



class SalesEmployeeSerializer(serializers.ModelSerializer):

    employee_name = serializers.SerializerMethodField()
    role_name = serializers.CharField(
        source="role.name",
        read_only=True,
    )

    class Meta:
        model = CompanyEmployee
        fields = [
            "id",
            "employee_name",
            "role_name",
        ]

    def get_employee_name(self, obj):
        full_name = obj.user.get_full_name()
        return full_name or obj.user.username


class CreateSalesVisitSerializer(serializers.Serializer):

    customer_id = serializers.IntegerField(min_value=1)
    billing_address_id = serializers.IntegerField(min_value=1)
    salesman_id = serializers.IntegerField(min_value=1)
    stock_location_id = serializers.IntegerField(min_value=1)

    visit_date = serializers.DateField()

    visit_time = serializers.TimeField(
        required=False,
        allow_null=True,
    )

    purpose = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )

    visit_notes = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):

        company = self.context["company"]

        # Validate customer belongs to this company.
        try:
            customer = Customer.objects.get(
                id=attrs["customer_id"],
                company=company,
                status=Customer.Status.ACTIVE,
            )
        except Customer.DoesNotExist:
            raise serializers.ValidationError({
                "customer_id": "Invalid or inactive customer."
            })

        # Validate selected address belongs to selected customer.
        try:
            billing_address = CustomerAddress.objects.get(
                id=attrs["billing_address_id"],
                customer=customer,
            )
        except CustomerAddress.DoesNotExist:
            raise serializers.ValidationError({
                "billing_address_id": (
                    "This billing address does not belong to the selected customer."
                )
            })

        # Validate salesman belongs to this company.
        try:
            salesman = CompanyEmployee.objects.select_related(
                "user", "role"
            ).get(
                id=attrs["salesman_id"],
                company=company,
                is_active=True,
                company__is_active=True,
                user__is_active=True,
            )
        except CompanyEmployee.DoesNotExist:
            raise serializers.ValidationError({
                "salesman_id": "Invalid or inactive salesman."
            })

        # Validate warehouse.
        try:
            stock_location = StockLocation.objects.get(
                id=attrs["stock_location_id"],
                company=company,
                is_active=True,
            )
        except StockLocation.DoesNotExist:
            raise serializers.ValidationError({
                "stock_location_id": "Invalid or inactive warehouse."
            })

        attrs["customer"] = customer
        attrs["billing_address"] = billing_address
        attrs["salesman"] = salesman
        attrs["stock_location"] = stock_location

        return attrs

    def create(self, validated_data):

        company = self.context["company"]
        user = self.context["request"].user

        customer = validated_data["customer"]
        billing_address = validated_data["billing_address"]

        address_parts = [
            billing_address.address_line_1,
            billing_address.address_line_2,
            billing_address.city,
            billing_address.district,
            billing_address.state,
            billing_address.pincode,
            billing_address.country,
        ]

        address_snapshot = ", ".join(
            part.strip()
            for part in address_parts
            if part and part.strip()
        )

        return CustomerVisit.objects.create(
            company=company,
            customer=customer,
            salesman=validated_data["salesman"],
            stock_location=validated_data["stock_location"],
            location_address=address_snapshot,
            customer_contact_person=customer.contact_person,
            customer_contact_number=customer.mobile_number,
            visit_type="NEW_SALE",
            status="DRAFT",
            visit_date=validated_data["visit_date"],
            visit_time=validated_data.get("visit_time"),
            purpose=validated_data.get("purpose", ""),
            visit_notes=validated_data.get("visit_notes", ""),
            created_by=user,
        )



class SalesVisitListSerializer(serializers.ModelSerializer):

    customer_name = serializers.SerializerMethodField()
    customer_code = serializers.CharField(
        source="customer.customer_code",
        read_only=True,
    )
    customer_mobile = serializers.CharField(
        source="customer_contact_number",
        read_only=True,
    )
    salesman_name = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(
        source="stock_location.name",
        read_only=True,
        default="",
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    visit_type_display = serializers.CharField(
        source="get_visit_type_display",
        read_only=True,
    )
    item_count = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = CustomerVisit
        fields = [
            "id",
            "visit_number",
            "customer_id",
            "customer_name",
            "customer_code",
            "customer_mobile",
            "salesman_id",
            "salesman_name",
            "stock_location_id",
            "warehouse_name",
            "visit_type",
            "visit_type_display",
            "visit_date",
            "visit_time",
            "status",
            "status_display",
            "purpose",
            "location_address",
            "item_count",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def get_customer_name(self, obj):
        return (
            obj.customer.business_name
            or obj.customer.contact_person
            or obj.customer.customer_code
        )

    def get_salesman_name(self, obj):
        user = obj.salesman.user
        return user.get_full_name() or user.username

    def get_item_count(self, obj):
        return obj.sale_items.count()

    def get_total_amount(self, obj):
        from decimal import Decimal

        total = sum(
            (
                item.total_amount
                for item in obj.sale_items.all()
            ),
            Decimal("0.00"),
        )

        return total



class SalesVisitItemDetailSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )
    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )
    gross_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    taxable_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    gst_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    total_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    serial_numbers = serializers.SerializerMethodField()

    class Meta:
        model = VisitSaleItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "discount_amount",
            "gst_rate",
            "gross_amount",
            "taxable_amount",
            "gst_amount",
            "total_amount",
            "serial_numbers"
        ]

    def get_serial_numbers(self, obj):
        return list(
            obj.machine_selections
            .select_related("machine")
            .values_list("machine__serial_number", flat=True)
        )


class SalesVisitDetailSerializer(serializers.ModelSerializer):

    customer_name = serializers.SerializerMethodField()
    customer_code = serializers.CharField(
        source="customer.customer_code",
        read_only=True,
    )
    salesman_name = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(
        source="stock_location.name",
        read_only=True,
        default="",
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    visit_type_display = serializers.CharField(
        source="get_visit_type_display",
        read_only=True,
    )

    sale_items = SalesVisitItemDetailSerializer(
        many=True,
        read_only=True,
    )

    total_amount = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()

    class Meta:
        model = CustomerVisit
        fields = [
            "id",
            "visit_number",
            "customer",
            "customer_name",
            "customer_code",
            "salesman",
            "salesman_name",
            "stock_location",
            "warehouse_name",
            "visit_type",
            "visit_type_display",
            "visit_date",
            "visit_time",
            "status",
            "status_display",
            "purpose",
            "visit_notes",
            "location_address",
            "customer_contact_person",
            "customer_contact_number",
            "sale_items",
            "total_items",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def get_customer_name(self, obj):
        return (
            obj.customer.business_name
            or obj.customer.contact_person
            or obj.customer.customer_code
        )

    def get_salesman_name(self, obj):
        user = obj.salesman.user
        return user.get_full_name() or user.username

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.sale_items.all())

    def get_total_amount(self, obj):
        from decimal import Decimal

        return sum(
            (
                item.total_amount
                for item in obj.sale_items.all()
            ),
            Decimal("0.00"),
        )



class AvailableSaleMachineSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerMachine
        fields = [
            "id",
            "serial_number",
            "status",
        ]


class AvailableSaleProductSerializer(serializers.ModelSerializer):

    available_quantity = serializers.IntegerField(read_only=True)
    available_machines = serializers.SerializerMethodField()

    class Meta:
        model = MachineProduct
        fields = [
            "id",
            "name",
            "brand",
            "model_number",
            "sku",
            "hsn_code",
            "mrp",
            "selling_price",
            "gst_rate",
            "available_quantity",
            "available_machines",
        ]

    def get_available_machines(self, obj):

        company = self.context["company"]
        location = self.context["location"]
        visit = self.context["visit"]

        selected_elsewhere = VisitSaleItemMachine.objects.filter(
            machine_id=OuterRef("pk")
        )

        machines = (
            CustomerMachine.objects
            .filter(
                company=company,
                product=obj,
                location=location,
                status=CustomerMachine.MachineStatus.IN_STOCK,
                customer__isnull=True,
                sale_item__isnull=True,
            )
            .annotate(
                selected_elsewhere=Exists(selected_elsewhere)
            )
            .filter(selected_elsewhere=False)
            .order_by("serial_number")
        )

        return AvailableSaleMachineSerializer(
            machines,
            many=True,
        ).data


class AddSaleItemSerializer(serializers.Serializer):

    product_id = serializers.IntegerField(min_value=1)

    machine_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )

    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        default=0,
    )

    gst_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
    )

    def validate(self, attrs):

        company = self.context["company"]
        visit = self.context["visit"]

        if visit.status != CustomerVisit.VisitStatus.DRAFT:
            raise serializers.ValidationError({
                "visit": "Products can only be added to draft visits."
            })

        if not visit.stock_location:
            raise serializers.ValidationError({
                "visit": "This visit has no warehouse selected."
            })

        machine_ids = attrs["machine_ids"]

        if len(machine_ids) != len(set(machine_ids)):
            raise serializers.ValidationError({
                "machine_ids": "Duplicate machine selections are not allowed."
            })

        try:
            product = MachineProduct.objects.get(
                pk=attrs["product_id"],
                company=company,
                is_active=True,
            )
        except MachineProduct.DoesNotExist:
            raise serializers.ValidationError({
                "product_id": "Invalid or inactive product."
            })

        machines = list(
            CustomerMachine.objects.filter(
                pk__in=machine_ids,
                company=company,
                product=product,
                location=visit.stock_location,
                status=CustomerMachine.MachineStatus.IN_STOCK,
                customer__isnull=True,
                sale_item__isnull=True,
            )
        )

        if len(machines) != len(machine_ids):
            raise serializers.ValidationError({
                "machine_ids": (
                    "One or more selected machines are unavailable, "
                    "already sold, or do not belong to this product "
                    "and warehouse."
                )
            })

        already_selected = VisitSaleItemMachine.objects.filter(
            machine_id__in=machine_ids
        ).exists()

        if already_selected:
            raise serializers.ValidationError({
                "machine_ids": (
                    "One or more machines are already selected "
                    "in another draft sale."
                )
            })

        attrs["product"] = product
        attrs["machines"] = machines
        attrs["quantity"] = len(machines)

        return attrs

    def create(self, validated_data):

        visit = self.context["visit"]

        product = validated_data["product"]
        machines = validated_data["machines"]

        quantity = validated_data["quantity"]

        unit_price = validated_data["unit_price"]
        discount_amount = validated_data["discount_amount"]
        gst_rate = validated_data["gst_rate"]

        gross_amount = unit_price * quantity

        if discount_amount > gross_amount:
            raise serializers.ValidationError({
                "discount_amount": (
                    "Discount cannot exceed the gross amount."
                )
            })

        sale_item = VisitSaleItem.objects.create(
            visit=visit,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            discount_amount=discount_amount,
            gst_rate=gst_rate,
        )

        VisitSaleItemMachine.objects.bulk_create([
            VisitSaleItemMachine(
                sale_item=sale_item,
                machine=machine,
            )
            for machine in machines
        ])

        return sale_item



class UpdateSaleItemSerializer(serializers.Serializer):

    unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
    )

    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
    )

    gst_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        required=False,
    )

    def validate(self, attrs):

        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )

        item = self.instance
        visit = self.context["visit"]

        if visit.status != CustomerVisit.VisitStatus.DRAFT:
            raise serializers.ValidationError({
                "visit": "Only draft sales visits can be edited."
            })

        unit_price = attrs.get("unit_price", item.unit_price)
        discount_amount = attrs.get(
            "discount_amount",
            item.discount_amount,
        )

        gross_amount = unit_price * item.quantity

        if discount_amount > gross_amount:
            raise serializers.ValidationError({
                "discount_amount": (
                    "Discount cannot exceed the gross amount."
                )
            })

        return attrs

    def update(self, instance, validated_data):

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save(
            update_fields=[
                *validated_data.keys(),
            ]
        )

        return instance



class VisitPaymentSerializer(serializers.ModelSerializer):

    received_by_name = serializers.SerializerMethodField()
    payment_mode_display = serializers.CharField(
        source="get_payment_mode_display",
        read_only=True,
    )
    payment_status_display = serializers.CharField(
        source="get_payment_status_display",
        read_only=True,
    )

    class Meta:
        model = VisitPayment
        fields = [
            "id",
            "receipt_number",
            "amount",
            "payment_mode",
            "payment_mode_display",
            "payment_status",
            "payment_status_display",
            "transaction_reference",
            "payment_date",
            "received_by",
            "received_by_name",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "receipt_number",
            "payment_status",
            "received_by",
            "received_by_name",
            "created_at",
        ]

    def get_received_by_name(self, obj):
        if not obj.received_by:
            return "-"

        return (
            obj.received_by.get_full_name()
            or obj.received_by.username
        )


class CreateVisitPaymentSerializer(serializers.Serializer):

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
    )

    payment_mode = serializers.ChoiceField(
        choices=VisitPayment.PaymentMode.choices,
    )

    transaction_reference = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
    )

