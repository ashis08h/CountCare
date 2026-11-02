
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from openpyxl import Workbook

from customers.models import CustomerImportBatch
from customers.permissions import ToggleAPIPermission


class ImportHistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def get_batch_data(batch):

    return {
        "id": batch.id,
        "file_name": batch.file_name,
        "file_type": batch.file_type,
        "total_rows": batch.total_rows,
        "successful_rows": batch.successful_rows,
        "failed_rows": batch.failed_rows,
        "status": batch.status,
        "created_at": batch.created_at,
        "uploaded_by": (
            batch.uploaded_by.username
            if batch.uploaded_by else None
        ),
    }


class CustomerImportHistoryAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def get(self, request):

        queryset = CustomerImportBatch.objects.all().order_by(
            "-created_at"
        )

        # Optional status filter
        batch_status = request.query_params.get("status")

        if batch_status:
            queryset = queryset.filter(status=batch_status.upper())

        # Optional file-name search
        search = request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                file_name__icontains=search
            )

        paginator = ImportHistoryPagination()

        page = paginator.paginate_queryset(queryset, request)

        results = [
            get_batch_data(batch)
            for batch in page
        ]

        return paginator.get_paginated_response(results)


class CustomerImportHistoryDetailAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def get(self, request, batch_id):

        batch = get_object_or_404(
            CustomerImportBatch,
            id=batch_id
        )

        rows = batch.rows.all().order_by("row_number")

        row_data = []

        for row in rows:

            row_data.append({
                "row_number": row.row_number,
                "status": row.status,
                "data": row.row_data,
                "errors": row.errors,
                "customer_id": row.customer_id,
            })

        return Response({
            "batch": get_batch_data(batch),
            "rows": row_data,
        })


class CustomerImportFailedReportAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def get(self, request, batch_id):

        batch = get_object_or_404(
            CustomerImportBatch,
            id=batch_id
        )

        failed_rows = batch.rows.filter(
            status__in=["INVALID", "FAILED"]
        ).order_by("row_number")

        workbook = Workbook()

        worksheet = workbook.active
        worksheet.title = "Failed Customers"

        headers = [
            "Excel Row Number",
            "Customer Type",
            "Business Name",
            "Contact Person",
            "Mobile Number",
            "Alternate Mobile",
            "Email",
            "GST Number",
            "PAN Number",
            "Address Line 1",
            "City",
            "District",
            "State",
            "PIN Code",
            "Country",
            "Import Error",
        ]

        worksheet.append(headers)

        for row in failed_rows:

            data = row.row_data or {}

            addresses = data.get("addresses", [])

            address = addresses[0] if addresses else {}

            error_text = self.format_errors(row.errors)

            worksheet.append([
                row.row_number,
                data.get("customer_type", ""),
                data.get("business_name", ""),
                data.get("contact_person", ""),
                data.get("mobile_number", ""),
                data.get("alternate_mobile", ""),
                data.get("email", ""),
                data.get("gst_number", ""),
                data.get("pan_number", ""),
                address.get("address_line_1", ""),
                address.get("city", ""),
                address.get("district", ""),
                address.get("state", ""),
                address.get("pincode", ""),
                address.get("country", ""),
                error_text,
            ])

        # Set readable column widths
        for column in worksheet.columns:

            max_length = max(
                len(str(cell.value or ""))
                for cell in column
            )

            worksheet.column_dimensions[
                column[0].column_letter
            ].width = min(max_length + 3, 50)

        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        response["Content-Disposition"] = (
            f'attachment; filename="failed_customers_batch_{batch.id}.xlsx"'
        )

        workbook.save(response)

        return response

    @staticmethod
    def format_errors(errors):

        if isinstance(errors, dict):

            return "; ".join(
                f"{field}: {', '.join(map(str, messages)) if isinstance(messages, list) else messages}"
                for field, messages in errors.items()
            )

        if isinstance(errors, list):
            return "; ".join(map(str, errors))

        return str(errors or "")


class CustomerImportOriginalDataAPIView(APIView):

    permission_classes = [ToggleAPIPermission]

    def get(self, request, batch_id):

        batch = get_object_or_404(
            CustomerImportBatch,
            id=batch_id
        )

        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )

        response["Content-Disposition"] = (
            f'attachment; filename="customer_import_batch_{batch.id}.csv"'
        )

        response.write(
            "\ufeff"
            "Row Number,Status,Customer Data,Errors\n"
        )

        import csv
        import json

        writer = csv.writer(response)

        for row in batch.rows.all().order_by("row_number"):

            writer.writerow([
                row.row_number,
                row.status,
                json.dumps(row.row_data, ensure_ascii=False),
                json.dumps(row.errors, ensure_ascii=False),
            ])

        return response
