from pathlib import Path

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from openpyxl import Workbook

from customers.models import (
    CustomerImportBatch,
    CustomerImportRow,
)

from customers.serializers import CustomerSerializer

from customers.services.customer_import_service import (
    parse_uploaded_file,
)

from customers.permissions import ToggleAPIPermission
from accounts.permissions import CashCountPermission


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def make_json_safe(value):
    """Convert serializer errors into JSON-serializable values."""

    if isinstance(value, dict):
        return {
            key: make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            make_json_safe(item)
            for item in value
        ]

    return str(value)


def get_row_errors(serializer):
    return make_json_safe(serializer.errors)


def batch_summary(batch):
    return {
        "batch_id": batch.id,
        "file_name": batch.file_name,
        "file_type": batch.file_type,
        "total_rows": batch.total_rows,
        "successful_rows": batch.successful_rows,
        "failed_rows": batch.failed_rows,
        "status": batch.status,
    }


def row_summary(row):
    return {
        "row_number": row.row_number,
        "data": row.row_data,
        "status": row.status,
        "errors": row.errors,
        "customer_id": row.customer_id,
    }


def get_company_batch_or_404(request, batch_id):
    """
    Return an import batch only if it belongs to
    the currently logged-in user's company.
    """

    membership = getattr(
        request,
        "company_membership",
        None,
    )

    if not membership:
        from django.http import Http404
        raise Http404

    return get_object_or_404(
        CustomerImportBatch.objects.select_related(
            "company",
            "uploaded_by",
        ),
        id=batch_id,
        company_id=membership.company_id,
    )


# ---------------------------------------------------------
# BASE PERMISSION CLASS
# ---------------------------------------------------------

class CustomerImportPermissionMixin:
    """
    Applies authentication, API toggle permission
    and company-level RBAC permission.
    """

    permission_classes = [
        IsAuthenticated,
        ToggleAPIPermission,
        CashCountPermission,
    ]

    permission_map = {}

    def get_permissions(self):
        self.required_permission = self.permission_map.get(
            self.request.method
        )

        return super().get_permissions()


# ---------------------------------------------------------
# DOWNLOAD IMPORT TEMPLATE
# ---------------------------------------------------------

class CustomerImportTemplateAPIView(
    CustomerImportPermissionMixin,
    APIView,
):

    permission_map = {
        "GET": "customers_add",
    }

    def get(self, request):

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Customers"

        headers = [
            "Customer Type",
            "Business Name",
            "Contact Person",
            "Mobile Number",
            "Alternate Mobile",
            "Email",
            "GST Number",
            "PAN Number",
            "Notes",
            "Address Type",
            "Address Line 1",
            "Address Line 2",
            "City",
            "District",
            "State",
            "PIN Code",
            "Country",
        ]

        worksheet.append(headers)

        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        response["Content-Disposition"] = (
            'attachment; filename="cashcount_customer_template.xlsx"'
        )

        workbook.save(response)

        return response


# ---------------------------------------------------------
# UPLOAD AND PREVIEW IMPORT FILE
# ---------------------------------------------------------

class CustomerImportPreviewAPIView(
    CustomerImportPermissionMixin,
    APIView,
):

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    permission_map = {
        "POST": "customers_add",
    }

    def post(self, request):

        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response(
                {
                    "detail": "Please select an Excel or CSV file."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            records = parse_uploaded_file(uploaded_file)

        except (ValueError, UnicodeDecodeError) as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = request.company_membership

        # Create the import batch under the logged-in user's company.
        batch = CustomerImportBatch.objects.create(
            company=membership.company,
            file_name=uploaded_file.name,
            file_type=Path(uploaded_file.name).suffix.lower(),
            total_rows=len(records),
            successful_rows=0,
            failed_rows=0,
            status="PENDING",
            uploaded_by=request.user,
        )

        row_objects = []

        for record in records:

            row_data = record["data"]

            serializer = CustomerSerializer(
                data=row_data
            )

            if serializer.is_valid():

                row_status = "VALID"
                errors = []

            else:

                row_status = "INVALID"
                errors = get_row_errors(serializer)

            row_objects.append(
                CustomerImportRow(
                    batch=batch,
                    row_number=record["row_number"],
                    row_data=row_data,
                    errors=errors,
                    status=row_status,
                )
            )

        CustomerImportRow.objects.bulk_create(
            row_objects
        )

        valid_count = sum(
            row.status == "VALID"
            for row in row_objects
        )

        invalid_count = len(row_objects) - valid_count

        batch.failed_rows = invalid_count

        batch.save(
            update_fields=["failed_rows"]
        )

        return Response(
            {
                "message": "File uploaded and validated successfully.",
                "batch": batch_summary(batch),
                "valid_rows": valid_count,
                "invalid_rows": invalid_count,
                "rows": [
                    row_summary(row)
                    for row in row_objects
                ],
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------
# VIEW IMPORT BATCH PREVIEW
# ---------------------------------------------------------

class CustomerImportBatchPreviewAPIView(
    CustomerImportPermissionMixin,
    APIView,
):

    permission_map = {
        "GET": "customers_view",
    }

    def get(self, request, batch_id):

        batch = get_company_batch_or_404(
            request,
            batch_id,
        )

        rows = batch.rows.all().order_by("row_number")

        return Response(
            {
                "batch": batch_summary(batch),
                "rows": [
                    row_summary(row)
                    for row in rows
                ],
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------
# CONFIRM AND PROCESS CUSTOMER IMPORT
# ---------------------------------------------------------

class CustomerImportConfirmAPIView(
    CustomerImportPermissionMixin,
    APIView,
):

    permission_map = {
        "POST": "customers_add",
    }

    @transaction.atomic
    def post(self, request, batch_id):

        batch = get_object_or_404(
            CustomerImportBatch.objects.select_for_update(),
            id=batch_id,
            company_id=request.company_membership.company_id,
        )

        if batch.status != "PENDING":

            return Response(
                {
                    "detail": (
                        "This import batch has already been processed "
                        "or cannot be imported."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch.status = "PROCESSING"

        batch.save(
            update_fields=["status"]
        )

        imported_count = 0

        failed_count = batch.rows.filter(
            status="INVALID"
        ).count()

        valid_rows = batch.rows.filter(
            status="VALID"
        ).order_by("row_number")

        for row in valid_rows:

            try:

                with transaction.atomic():

                    serializer = CustomerSerializer(
                        data=row.row_data
                    )

                    serializer.is_valid(
                        raise_exception=True
                    )

                    # Always assign the batch company.
                    # Never trust company information from uploaded data.
                    customer = serializer.save(
                        company=batch.company,
                        created_by=batch.uploaded_by,
                    )

                    row.customer = customer
                    row.status = "IMPORTED"
                    row.errors = []

                    row.save(
                        update_fields=[
                            "customer",
                            "status",
                            "errors",
                        ]
                    )

                imported_count += 1

            except ValidationError as exc:

                row.status = "FAILED"
                row.errors = make_json_safe(
                    exc.detail
                )

                row.save(
                    update_fields=[
                        "status",
                        "errors",
                    ]
                )

                failed_count += 1

            except Exception:

                row.status = "FAILED"
                row.errors = [
                    "Unexpected error occurred while importing this row."
                ]

                row.save(
                    update_fields=[
                        "status",
                        "errors",
                    ]
                )

                failed_count += 1

        batch.successful_rows = imported_count
        batch.failed_rows = failed_count
        batch.status = "COMPLETED"

        batch.save(
            update_fields=[
                "successful_rows",
                "failed_rows",
                "status",
            ]
        )

        return Response(
            {
                "message": "Customer import completed.",
                "batch": batch_summary(batch),
            },
            status=status.HTTP_200_OK,
        )