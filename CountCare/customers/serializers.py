
import re

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from .models import (
    Customer,
    CustomerAddress,
    CustomerImportBatch,
)


# --------------------------------------------------
# Customer Address Serializer
# --------------------------------------------------

class CustomerAddressSerializer(serializers.ModelSerializer):

    id = serializers.IntegerField(required=False)

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
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_address_type(self, value):

        allowed_types = [
            "BILLING",
            "SHIPPING",
            "OFFICE",
            "HOME",
        ]

        if value not in allowed_types:
            raise serializers.ValidationError(
                "Invalid address type."
            )

        return value

    def validate_address_line_1(self, value):

        value = value.strip()

        if len(value) < 3:
            raise serializers.ValidationError(
                "Address must contain at least 3 characters."
            )

        if len(value) > 255:
            raise serializers.ValidationError(
                "Address cannot exceed 255 characters."
            )

        return value

    def validate_city(self, value):

        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "City must contain at least 2 characters."
            )

        return value

    def validate_state(self, value):

        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "State must contain at least 2 characters."
            )

        return value

    def validate_pincode(self, value):

        value = value.strip()

        if not re.fullmatch(r"[1-9][0-9]{5}", value):
            raise serializers.ValidationError(
                "Enter a valid 6-digit Indian PIN code."
            )

        return value

    def validate_country(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Country cannot be empty."
            )

        return value


# --------------------------------------------------
# Customer Serializer
# --------------------------------------------------

class CustomerSerializer(serializers.ModelSerializer):

    addresses = CustomerAddressSerializer(
        many=True,
        required=False
    )

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
            "pan_number",
            "notes",
            "status",
            "addresses",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "customer_code",
            "created_at",
            "updated_at",
        ]

    # ----------------------------------------------
    # Field-level validations
    # ----------------------------------------------

    def validate_customer_type(self, value):

        allowed_types = [
            "INDIVIDUAL",
            "BUSINESS",
        ]

        if value not in allowed_types:
            raise serializers.ValidationError(
                "Customer type must be INDIVIDUAL or BUSINESS."
            )

        return value

    def validate_contact_person(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Contact person is required."
            )

        if len(value) < 2:
            raise serializers.ValidationError(
                "Contact person must contain at least 2 characters."
            )

        return value

    def validate_business_name(self, value):

        value = value.strip()

        if len(value) > 200:
            raise serializers.ValidationError(
                "Business name cannot exceed 200 characters."
            )

        return value

    def validate_mobile_number(self, value):

        value = re.sub(r"[\s-]", "", value.strip())

        # Accept Indian 10-digit numbers and +91 numbers.
        pattern = r"^(?:\+91)?[6-9][0-9]{9}$"

        if not re.fullmatch(pattern, value):
            raise serializers.ValidationError(
                "Enter a valid Indian mobile number."
            )

        return value

    def validate_alternate_mobile(self, value):

        if not value:
            return value

        value = re.sub(r"[\s-]", "", value.strip())

        pattern = r"^(?:\+91)?[6-9][0-9]{9}$"

        if not re.fullmatch(pattern, value):
            raise serializers.ValidationError(
                "Enter a valid alternate mobile number."
            )

        primary_mobile = self.initial_data.get(
            "mobile_number"
        )

        if primary_mobile:

            primary_mobile = re.sub(
                r"[\s-]",
                "",
                primary_mobile.strip()
            )

            if primary_mobile == value:
                raise serializers.ValidationError(
                    "Primary and alternate mobile numbers cannot be the same."
                )

        return value

    def validate_email(self, value):

        value = value.strip().lower()

        if value:

            try:
                validate_email(value)

            except DjangoValidationError:
                raise serializers.ValidationError(
                    "Enter a valid email address."
                )

        return value

    def validate_gst_number(self, value):

        value = value.strip().upper()

        if value:

            pattern = (
                r"^[0-9]{2}[A-Z]{5}[0-9]{4}"
                r"[A-Z][1-9A-Z]Z[0-9A-Z]$"
            )

            if not re.fullmatch(pattern, value):
                raise serializers.ValidationError(
                    "Enter a valid GST number."
                )

        return value

    def validate_pan_number(self, value):

        value = value.strip().upper()

        if value:

            pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]$"

            if not re.fullmatch(pattern, value):
                raise serializers.ValidationError(
                    "Enter a valid PAN number."
                )

        return value

    # ----------------------------------------------
    # Object-level validations
    # ----------------------------------------------

    def validate(self, attrs):

        customer_type = attrs.get(
            "customer_type",
            getattr(
                self.instance,
                "customer_type",
                Customer.CustomerType.BUSINESS
            )
        )

        business_name = attrs.get(
            "business_name",
            getattr(self.instance, "business_name", "")
        )

        mobile = attrs.get(
            "mobile_number",
            getattr(self.instance, "mobile_number", None)
        )

        alternate_mobile = attrs.get(
            "alternate_mobile",
            getattr(self.instance, "alternate_mobile", "")
        )

        # Business customer validation
        if customer_type == Customer.CustomerType.BUSINESS:

            if not business_name or not business_name.strip():

                raise serializers.ValidationError({
                    "business_name": (
                        "Business name is required for business customers."
                    )
                })

        # Individual customer
        if customer_type == Customer.CustomerType.INDIVIDUAL:

            attrs["business_name"] = ""

        # Compare normalized mobile numbers
        if mobile and alternate_mobile:

            normalize = lambda number: re.sub(
                r"[\s-]",
                "",
                number
            )

            if normalize(mobile) == normalize(alternate_mobile):

                raise serializers.ValidationError({
                    "alternate_mobile": (
                        "Primary and alternate mobile numbers cannot be the same."
                    )
                })

        # Address validations
        addresses = attrs.get("addresses")

        if addresses is not None:

            default_addresses = [
                address
                for address in addresses
                if address.get("is_default", False)
            ]

            if len(default_addresses) > 1:

                raise serializers.ValidationError({
                    "addresses": (
                        "Only one address can be marked as default."
                    )
                })

        return attrs

    # ----------------------------------------------
    # Create customer and nested addresses
    # ----------------------------------------------

    def create(self, validated_data):

        addresses_data = validated_data.pop(
            "addresses",
            []
        )

        from django.db import transaction

        with transaction.atomic():

            customer = Customer.objects.create(
                **validated_data
            )

            for address_data in addresses_data:

                CustomerAddress.objects.create(
                    customer=customer,
                    **address_data
                )

        return customer

    # ----------------------------------------------
    # Update customer and nested addresses
    # ----------------------------------------------

    def update(self, instance, validated_data):

        from django.db import transaction

        addresses_data = validated_data.pop(
            "addresses",
            None
        )

        with transaction.atomic():

            for key, value in validated_data.items():

                setattr(instance, key, value)

            instance.save()

            if addresses_data is not None:

                existing_addresses = {
                    address.id
                    for address in instance.addresses.all()
                }

                submitted_ids = {
                    address["id"]
                    for address in addresses_data
                    if address.get("id") is not None
                }

                # Prevent updating another customer's address
                if not submitted_ids.issubset(existing_addresses):

                    raise serializers.ValidationError({
                        "addresses": (
                            "Invalid address ID. "
                            "Address does not belong to this customer."
                        )
                    })

                for address_data in addresses_data:

                    address_data = dict(address_data)

                    address_id = address_data.pop(
                        "id",
                        None
                    )

                    if address_id:

                        CustomerAddress.objects.filter(
                            customer=instance,
                            id=address_id
                        ).update(**address_data)

                    else:

                        CustomerAddress.objects.create(
                            customer=instance,
                            **address_data
                        )

        return instance


# --------------------------------------------------
# Customer Import Batch Serializer
# --------------------------------------------------

class CustomerImportBatchSerializer(serializers.ModelSerializer):

    class Meta:

        model = CustomerImportBatch

        fields = [
            "id",
            "file_name",
            "file_type",
            "total_rows",
            "successful_rows",
            "failed_rows",
            "status",
            "created_at",
        ]

        read_only_fields = fields
