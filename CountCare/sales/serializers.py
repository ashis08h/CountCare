
# sales/serializers.py

from rest_framework import serializers

from sales.models import (
    StockLocation,
    MachineProduct,
    InventoryStock,
    CustomerMachine,
    StockMovement,
)

from customers.models import Customer, CustomerAddress
from accounts.models import CompanyEmployee
from sales.models import CustomerVisit


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
            billing_address=billing_address,
            billing_address_snapshot=address_snapshot,
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

