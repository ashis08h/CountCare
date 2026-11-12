
# sales/serializers.py

from rest_framework import serializers

from sales.models import (
    StockLocation,
    MachineProduct,
    InventoryStock,
    CustomerMachine,
    StockMovement,
)


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
