
from rest_framework import serializers

from customers.models import Customer
from .models import EmailCampaign, EmailCampaignRecipient
from django.db import transaction


class EmailCampaignCustomerSerializer(serializers.ModelSerializer):

    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_code",
            "customer_name",
            "email",
            "mobile_number",
        ]

    def get_customer_name(self, obj):

        if obj.customer_type == "BUSINESS":
            return obj.business_name or obj.contact_person or ""

        return obj.contact_person or obj.business_name or ""


class EmailCampaignRecipientSerializer(serializers.ModelSerializer):

    class Meta:
        model = EmailCampaignRecipient
        fields = [
            "id",
            "customer",
            "customer_name",
            "email_address",
            "is_unsubscribed",
            "added_at",
        ]
        read_only_fields = fields


class EmailCampaignSerializer(serializers.ModelSerializer):

    customer_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=False,
    )

    recipients = EmailCampaignRecipientSerializer(
        many=True,
        read_only=True,
    )

    recipient_count = serializers.SerializerMethodField()

    class Meta:
        model = EmailCampaign
        fields = [
            "id",
            "name",
            "subject",
            "message",
            "frequency",
            "start_date",
            "end_date",
            "send_time",
            "timezone",
            "weekdays",
            "day_of_month",
            "interval_days",
            "scheduled_at",
            "status",
            "is_active",
            "next_run_at",
            "last_run_at",
            "customer_ids",
            "recipients",
            "recipient_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "is_active",
            "next_run_at",
            "last_run_at",
            "recipients",
            "recipient_count",
            "created_at",
            "updated_at",
        ]

    def get_recipient_count(self, obj):
        return obj.recipients.count()

    def validate_customer_ids(self, value):

        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate customer IDs are not allowed."
            )

        company = self.context["company"]

        customers = Customer.objects.filter(
            id__in=value,
            company=company,
            status="ACTIVE",
        ).exclude(
            email__isnull=True,
        ).exclude(
            email__exact="",
        )

        if customers.count() != len(value):
            raise serializers.ValidationError(
                "One or more selected customers are invalid, "
                "inactive, have no email address, or belong "
                "to another company."
            )

        return value

    def validate(self, attrs):

        frequency = attrs.get(
            "frequency",
            getattr(
                self.instance,
                "frequency",
                EmailCampaign.Frequency.ONCE,
            ),
        )

        start_date = attrs.get(
            "start_date",
            getattr(self.instance, "start_date", None),
        )

        end_date = attrs.get(
            "end_date",
            getattr(self.instance, "end_date", None),
        )

        weekdays = attrs.get(
            "weekdays",
            getattr(self.instance, "weekdays", []),
        )

        day_of_month = attrs.get(
            "day_of_month",
            getattr(self.instance, "day_of_month", None),
        )

        interval_days = attrs.get(
            "interval_days",
            getattr(self.instance, "interval_days", None),
        )

        scheduled_at = attrs.get(
            "scheduled_at",
            getattr(self.instance, "scheduled_at", None),
        )

        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        if frequency == EmailCampaign.Frequency.ONCE and not scheduled_at:
            raise serializers.ValidationError({
                "scheduled_at": "Scheduled date and time are required for a one-time campaign."
            })

        if frequency == EmailCampaign.Frequency.WEEKLY:

            if not weekdays:
                raise serializers.ValidationError({
                    "weekdays": "Select at least one weekday for a weekly campaign."
                })

            if not isinstance(weekdays, list) or any(
                not isinstance(day, int) or day < 0 or day > 6
                for day in weekdays
            ):
                raise serializers.ValidationError({
                    "weekdays": "Weekdays must be a list of numbers from 0 (Monday) to 6 (Sunday)."
                })

        if frequency == EmailCampaign.Frequency.MONTHLY:

            if day_of_month is None or not 1 <= day_of_month <= 31:
                raise serializers.ValidationError({
                    "day_of_month": "Select a day between 1 and 31 for a monthly campaign."
                })

        if frequency == EmailCampaign.Frequency.CUSTOM:

            if interval_days is None or interval_days < 1:
                raise serializers.ValidationError({
                    "interval_days": "Custom interval must be at least 1 day."
                })

        return attrs

    @transaction.atomic
    def create(self, validated_data):

        customer_ids = validated_data.pop("customer_ids")
        company = self.context["company"]
        user = self.context["request"].user

        campaign = EmailCampaign.objects.create(
            **validated_data,
            company=company,
            created_by=user,
            updated_by=user,
            status=EmailCampaign.Status.DRAFT,
            is_active=False,
            next_run_at=None,
        )

        customers = Customer.objects.filter(
            id__in=customer_ids,
            company=company,
            status="ACTIVE",
        ).exclude(
            email__isnull=True,
        ).exclude(
            email__exact="",
        )

        recipients = []

        for customer in customers:

            customer_name = (
                customer.business_name
                or customer.contact_person
                or ""
            )

            recipients.append(
                EmailCampaignRecipient(
                    campaign=campaign,
                    customer=customer,
                    customer_name=customer_name,
                    email_address=customer.email.strip().lower(),
                )
            )

        EmailCampaignRecipient.objects.bulk_create(recipients)

        return campaign

    @transaction.atomic
    def update(self, instance, validated_data):
        customer_ids = validated_data.pop("customer_ids", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.updated_by = self.context["request"].user
        instance.save()

        # Replace recipients only when customer_ids was supplied.
        if customer_ids is not None:
            company = self.context["company"]

            customers = Customer.objects.filter(
                id__in=customer_ids,
                company=company,
                status="ACTIVE",
            ).exclude(
                email__isnull=True
            ).exclude(
                email__exact=""
            )

            if customers.count() != len(customer_ids):
                raise serializers.ValidationError({
                    "customer_ids": "One or more selected customers are invalid."
                })

            instance.recipients.all().delete()

            recipients = []
            for customer in customers:
                if customer.customer_type == "BUSINESS":
                    customer_name = (
                            customer.business_name or customer.contact_person or ""
                    )
                else:
                    customer_name = (
                            customer.contact_person or customer.business_name or ""
                    )

                recipients.append(
                    EmailCampaignRecipient(
                        campaign=instance,
                        customer=customer,
                        customer_name=customer_name,
                        email_address=customer.email.strip().lower(),
                    )
                )

            EmailCampaignRecipient.objects.bulk_create(recipients)

        return instance
