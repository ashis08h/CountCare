
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import CashCountPermission
from customers.models import Customer
from customers.permissions import ToggleAPIPermission

from .serializers import EmailCampaignCustomerSerializer


class EmailMarketingPermissionMixin:

    permission_classes = [
        IsAuthenticated,
        ToggleAPIPermission,
        CashCountPermission,
    ]

    permission_map = {
        "GET": "email_marketing_view",
        "POST": "email_marketing_add",
        "PUT": "email_marketing_change",
        "PATCH": "email_marketing_change",
        "DELETE": "email_marketing_delete",
    }

    def get_permissions(self):

        self.required_permission = self.permission_map.get(
            self.request.method
        )

        return super().get_permissions()

    def get_company(self):
        return self.request.company_membership.company


class EmailMarketingCustomerListAPIView(
    EmailMarketingPermissionMixin,
    ListAPIView,
):

    serializer_class = EmailCampaignCustomerSerializer

    def get_queryset(self):

        company = self.get_company()

        queryset = Customer.objects.filter(
            company=company,
            status="ACTIVE",
        ).exclude(
            email__isnull=True,
        ).exclude(
            email__exact="",
        )

        search = self.request.query_params.get(
            "search",
            "",
        ).strip()

        if search:

            from django.db.models import Q

            queryset = queryset.filter(
                Q(business_name__icontains=search)
                | Q(contact_person__icontains=search)
                | Q(email__icontains=search)
                | Q(customer_code__icontains=search)
            )

        return queryset.order_by(
            "business_name",
            "contact_person",
        )
