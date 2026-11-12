
from django.shortcuts import get_object_or_404

from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from django_filters.rest_framework import DjangoFilterBackend

from customers.models import Customer
from customers.serializers import CustomerSerializer
from customers.permissions import ToggleAPIPermission

from accounts.permissions import CashCountPermission


# --------------------------------------------------
# Customer Pagination
# --------------------------------------------------

class CustomerPagination(PageNumberPagination):

    page_size = 20

    page_size_query_param = "page_size"

    max_page_size = 100


# --------------------------------------------------
# Company Scoped Customer API Mixin
# --------------------------------------------------

class CustomerCompanyMixin:
    """
    Common functionality for all customer APIs.

    1. Requires an active company membership.
    2. Checks the required role permission.
    3. Restricts customer access to the logged-in user's company.
    """

    permission_classes = [
        ToggleAPIPermission,
        CashCountPermission,
    ]

    permission_map = {
        "GET": "customers_view",
        "POST": "customers_add",
        "PUT": "customers_change",
        "PATCH": "customers_change",
        "DELETE": "customers_delete",
    }

    def get_permissions(self):

        self.required_permission = self.permission_map.get(
            self.request.method
        )

        return super().get_permissions()

    def get_company(self):

        membership = getattr(
            self.request,
            "company_membership",
            None,
        )

        if not membership:
            return None

        return membership.company

    def get_company_customer_queryset(self):

        company = self.get_company()

        if not company:
            return Customer.objects.none()

        return Customer.objects.filter(
            company=company
        )


# --------------------------------------------------
# Customer List API
# GET /api/customers/
# --------------------------------------------------

class CustomerListAPIView(
    CustomerCompanyMixin,
    generics.ListAPIView,
):

    serializer_class = CustomerSerializer

    pagination_class = CustomerPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = [
        "customer_type",
        "status",
    ]

    search_fields = [
        "customer_code",
        "business_name",
        "contact_person",
        "mobile_number",
        "alternate_mobile",
        "email",
        "gst_number",
        "pan_number",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "contact_person",
        "business_name",
        "customer_code",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):

        return self.get_company_customer_queryset().prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Create API
# POST /api/customers/create/
# --------------------------------------------------

class CustomerCreateAPIView(
    CustomerCompanyMixin,
    generics.CreateAPIView,
):

    serializer_class = CustomerSerializer

    def perform_create(self, serializer):

        membership = self.request.company_membership

        serializer.save(
            company=membership.company,
            created_by=self.request.user,
        )


# --------------------------------------------------
# Customer Retrieve API
# GET /api/customers/<pk>/
# --------------------------------------------------

class CustomerRetrieveAPIView(
    CustomerCompanyMixin,
    generics.RetrieveAPIView,
):

    serializer_class = CustomerSerializer

    lookup_field = "pk"

    def get_queryset(self):

        return self.get_company_customer_queryset().prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Update API
# PUT / PATCH /api/customers/<pk>/update/
# --------------------------------------------------

class CustomerUpdateAPIView(
    CustomerCompanyMixin,
    generics.UpdateAPIView,
):

    serializer_class = CustomerSerializer

    lookup_field = "pk"

    http_method_names = [
        "put",
        "patch",
        "head",
        "options",
    ]

    def get_queryset(self):

        return self.get_company_customer_queryset().prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Detail API
# GET / PUT / PATCH
# --------------------------------------------------

class CustomerDetailAPIView(
    CustomerCompanyMixin,
    generics.RetrieveUpdateAPIView,
):

    serializer_class = CustomerSerializer

    lookup_field = "pk"

    http_method_names = [
        "get",
        "put",
        "patch",
        "head",
        "options",
    ]

    def get_queryset(self):

        return self.get_company_customer_queryset().prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Deactivate API
# POST /api/customers/<pk>/deactivate/
# --------------------------------------------------

class CustomerDeactivateAPIView(
    CustomerCompanyMixin,
    APIView,
):

    permission_map = {
        "POST": "customers_change",
    }

    def post(self, request, pk):

        customer = get_object_or_404(
            self.get_company_customer_queryset(),
            pk=pk,
        )

        if customer.status == Customer.Status.INACTIVE:

            return Response(
                {
                    "message": "Customer is already inactive."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer.status = Customer.Status.INACTIVE

        customer.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return Response(
            {
                "message": "Customer deactivated successfully.",
                "customer_id": customer.id,
                "customer_code": customer.customer_code,
                "status": customer.status,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------
# Customer Activate API
# POST /api/customers/<pk>/activate/
# --------------------------------------------------

class CustomerActivateAPIView(
    CustomerCompanyMixin,
    APIView,
):

    permission_map = {
        "POST": "customers_change",
    }

    def post(self, request, pk):

        customer = get_object_or_404(
            self.get_company_customer_queryset(),
            pk=pk,
        )

        if customer.status == Customer.Status.ACTIVE:

            return Response(
                {
                    "message": "Customer is already active."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer.status = Customer.Status.ACTIVE

        customer.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return Response(
            {
                "message": "Customer activated successfully.",
                "customer_id": customer.id,
                "customer_code": customer.customer_code,
                "status": customer.status,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------
# Customer Address List API
# GET /api/customers/<pk>/addresses/
# --------------------------------------------------

class CustomerAddressListAPIView(
    CustomerCompanyMixin,
    APIView,
):

    permission_map = {
        "GET": "customers_view",
    }

    def get(self, request, pk):

        customer = get_object_or_404(
            self.get_company_customer_queryset(),
            pk=pk,
        )

        serializer = CustomerSerializer(
            customer,
            context={"request": request},
        )

        return Response(
            {
                "customer_code": customer.customer_code,
                "addresses": serializer.data["addresses"],
            },
            status=status.HTTP_200_OK,
        )
