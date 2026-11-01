
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from customers.permissions import ToggleAPIPermission

from django_filters.rest_framework import DjangoFilterBackend

from customers.models import Customer
from customers.serializers import CustomerSerializer


# --------------------------------------------------
# Customer Pagination
# --------------------------------------------------

class CustomerPagination(PageNumberPagination):

    page_size = 20

    page_size_query_param = "page_size"

    max_page_size = 100


# --------------------------------------------------
# Customer List API
# --------------------------------------------------

class CustomerListAPIView(generics.ListAPIView):

    serializer_class = CustomerSerializer

    permission_classes = [ToggleAPIPermission]

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

        return Customer.objects.all().prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Create API
# --------------------------------------------------

class CustomerCreateAPIView(generics.CreateAPIView):

    serializer_class = CustomerSerializer

    permission_classes = [ToggleAPIPermission]

    def perform_create(self, serializer):
        user = self.request.user

        serializer.save(
            created_by=user if user.is_authenticated else None
        )


# --------------------------------------------------
# Customer Retrieve API
# --------------------------------------------------

class CustomerRetrieveAPIView(generics.RetrieveAPIView):

    serializer_class = CustomerSerializer

    permission_classes = [ToggleAPIPermission]

    lookup_field = "pk"

    def get_queryset(self):

        return Customer.objects.prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Update API
# --------------------------------------------------

class CustomerUpdateAPIView(generics.UpdateAPIView):

    serializer_class = CustomerSerializer

    permission_classes = [ToggleAPIPermission]

    lookup_field = "pk"

    http_method_names = [
        "put",
        "patch",
        "head",
        "options",
    ]

    def get_queryset(self):

        return Customer.objects.prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Detail API
# GET / PUT / PATCH
# --------------------------------------------------

class CustomerDetailAPIView(generics.RetrieveUpdateAPIView):

    serializer_class = CustomerSerializer

    permission_classes = [ToggleAPIPermission]

    lookup_field = "pk"

    http_method_names = [
        "get",
        "put",
        "patch",
        "head",
        "options",
    ]

    def get_queryset(self):

        return Customer.objects.prefetch_related(
            "addresses"
        )


# --------------------------------------------------
# Customer Deactivate API
# --------------------------------------------------

class CustomerDeactivateAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def post(self, request, pk):

        customer = get_object_or_404(
            Customer,
            pk=pk
        )

        if customer.status == Customer.Status.INACTIVE:

            return Response(
                {
                    "message": "Customer is already inactive."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        customer.status = Customer.Status.INACTIVE

        customer.save(
            update_fields=[
                "status",
                "updated_at"
            ]
        )

        return Response(
            {
                "message": "Customer deactivated successfully.",
                "customer_id": customer.id,
                "customer_code": customer.customer_code,
                "status": customer.status,
            },
            status=status.HTTP_200_OK
        )


# --------------------------------------------------
# Customer Activate API
# --------------------------------------------------

class CustomerActivateAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def post(self, request, pk):

        customer = get_object_or_404(
            Customer,
            pk=pk
        )

        if customer.status == Customer.Status.ACTIVE:

            return Response(
                {
                    "message": "Customer is already active."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        customer.status = Customer.Status.ACTIVE

        customer.save(
            update_fields=[
                "status",
                "updated_at"
            ]
        )

        return Response(
            {
                "message": "Customer activated successfully.",
                "customer_id": customer.id,
                "customer_code": customer.customer_code,
                "status": customer.status,
            },
            status=status.HTTP_200_OK
        )


# --------------------------------------------------
# Customer Address List API
# --------------------------------------------------

class CustomerAddressListAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def get(self, request, pk):

        customer = get_object_or_404(
            Customer,
            pk=pk
        )

        serializer = CustomerSerializer(
            customer,
            context={"request": request}
        )

        return Response(
            {
                "customer_code": customer.customer_code,
                "addresses": serializer.data["addresses"],
            },
            status=status.HTTP_200_OK
        )
