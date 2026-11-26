
from rest_framework import serializers

from customers.models import Customer


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
