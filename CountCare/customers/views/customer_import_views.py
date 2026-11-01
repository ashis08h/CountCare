
from pathlib import Path

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError

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


def make_json_safe(value):
    """Convert serializer errors into JSON-serializable values."""

    if isinstance(value, dict):
        return {
            key: make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [make_json_safe(item) for item in value]

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


class CustomerImportTemplateAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

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


class CustomerImportPreviewAPIView(APIView):

    parser_classes = [MultiPartParser, FormParser]

    permission_classes = [ToggleAPIPermission]

    def post(self, request):

        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response(
                {"detail": "Please select an Excel or CSV file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            records = parse_uploaded_file(uploaded_file)

        except (ValueError, UnicodeDecodeError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        uploaded_by = (
            user if user.is_authenticated else None
        )

        batch = CustomerImportBatch.objects.create(
            file_name=uploaded_file.name,
            file_type=Path(uploaded_file.name).suffix.lower(),
            total_rows=len(records),
            successful_rows=0,
            failed_rows=0,
            status="PENDING",
            uploaded_by=uploaded_by,
        )

        row_objects = []

        for record in records:

            row_data = record["data"]

            serializer = CustomerSerializer(data=row_data)

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

        CustomerImportRow.objects.bulk_create(row_objects)

        valid_count = sum(
            row.status == "VALID"
            for row in row_objects
        )

        invalid_count = len(row_objects) - valid_count

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
            status=status.HTTP_201_CREATED
        )


class CustomerImportBatchPreviewAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def get(self, request, batch_id):

        batch = get_object_or_404(
            CustomerImportBatch,
            id=batch_id
        )

        rows = batch.rows.all()

        return Response(
            {
                "batch": batch_summary(batch),
                "rows": [
                    row_summary(row)
                    for row in rows
                ],
            },
            status=status.HTTP_200_OK
        )


class CustomerImportConfirmAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    @transaction.atomic
    def post(self, request, batch_id):

        batch = get_object_or_404(
            CustomerImportBatch.objects.select_for_update(),
            id=batch_id
        )

        if batch.status != "PENDING":

            return Response(
                {
                    "detail": (
                        "This import batch has already been processed "
                        "or cannot be imported."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        batch.status = "PROCESSING"
        batch.save(update_fields=["status"])

        imported_count = 0
        failed_count = batch.rows.filter(status="INVALID").count()

        for row in batch.rows.filter(status="VALID").order_by("row_number"):

            try:

                with transaction.atomic():

                    serializer = CustomerSerializer(
                        data=row.row_data
                    )

                    serializer.is_valid(raise_exception=True)

                    customer = serializer.save(
                        created_by=(
                            batch.uploaded_by
                        )
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
                row.errors = make_json_safe(exc.detail)

                row.save(
                    update_fields=["status", "errors"]
                )

                failed_count += 1

            except Exception:

                row.status = "FAILED"
                row.errors = [
                    "Unexpected error occurred while importing this row."
                ]

                row.save(
                    update_fields=["status", "errors"]
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
            status=status.HTTP_200_OK
        )
