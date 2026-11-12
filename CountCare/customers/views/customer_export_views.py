
import csv

from datetime import date, datetime

from django.db.models import Q
from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from customers.models import Customer
from customers.permissions import ToggleAPIPermission

from accounts.permissions import CashCountPermission


# --------------------------------------------------
# Export Headers
# --------------------------------------------------

EXPORT_HEADERS = [
    "Customer Code",
    "Customer Type",
    "Business Name",
    "Contact Person",
    "Mobile Number",
    "Alternate Mobile",
    "Email",
    "GST Number",
    "PAN Number",
    "Notes",
    "Customer Status",
    "Address Type",
    "Address Line 1",
    "Address Line 2",
    "City",
    "District",
    "State",
    "PIN Code",
    "Country",
    "Default Address",
    "Created At",
]


# --------------------------------------------------
# Safe Export Value
# --------------------------------------------------

def safe_export_value(value):
    """
    Prevent spreadsheet formula injection and
    convert values into export-friendly strings.
    """

    if value is None:
        return ""

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, bool):
        return "Yes" if value else "No"

    value = str(value)

    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        value = "'" + value

    return value


# --------------------------------------------------
# Get Company-Scoped Filtered Customers
# --------------------------------------------------

def get_filtered_customers(request):

    membership = getattr(
        request,
        "company_membership",
        None,
    )

    if not membership:
        return Customer.objects.none()

    queryset = Customer.objects.filter(
        company=membership.company
    ).prefetch_related(
        "addresses"
    )

    # Customer type filter

    customer_type = request.query_params.get(
        "customer_type"
    )

    if customer_type:
        queryset = queryset.filter(
            customer_type=customer_type.upper()
        )

    # Customer status filter

    customer_status = request.query_params.get(
        "status"
    )

    if customer_status:
        queryset = queryset.filter(
            status=customer_status.upper()
        )

    # Search filter

    search = request.query_params.get(
        "search",
        ""
    ).strip()

    if search:

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

        for term in search.split():

            search_query = Q()

            for field in search_fields:
                search_query |= Q(
                    **{
                        f"{field}__icontains": term
                    }
                )

            queryset = queryset.filter(search_query)

    # Ordering

    ordering = request.query_params.get(
        "ordering",
        "-created_at"
    )

    allowed_ordering = {
        "created_at",
        "-created_at",
        "updated_at",
        "-updated_at",
        "contact_person",
        "-contact_person",
        "business_name",
        "-business_name",
        "customer_code",
        "-customer_code",
    }

    if ordering in allowed_ordering:
        queryset = queryset.order_by(ordering)

    return queryset.distinct()


# --------------------------------------------------
# Prepare Customer Export Rows
# --------------------------------------------------

def customer_export_rows(customers):

    rows = []

    for customer in customers:

        addresses = list(customer.addresses.all())

        # Include one blank address row if no address exists.

        if not addresses:
            addresses = [None]

        for address in addresses:

            rows.append([
                customer.customer_code,
                customer.customer_type,
                customer.business_name,
                customer.contact_person,
                customer.mobile_number,
                customer.alternate_mobile,
                customer.email,
                customer.gst_number,
                customer.pan_number,
                customer.notes,
                customer.status,

                address.address_type if address else "",
                address.address_line_1 if address else "",
                address.address_line_2 if address else "",
                address.city if address else "",
                address.district if address else "",
                address.state if address else "",
                address.pincode if address else "",
                address.country if address else "",
                address.is_default if address else False,

                customer.created_at,
            ])

    return [
        [
            safe_export_value(value)
            for value in row
        ]
        for row in rows
    ]


# --------------------------------------------------
# Customer Export API
# GET /api/customers/export/?export_format=xlsx
# --------------------------------------------------

class CustomerExportAPIView(APIView):

    # Do not disable authentication.
    # Use the authentication classes configured in settings.py.

    permission_classes = [
        IsAuthenticated,
        ToggleAPIPermission,
        CashCountPermission,
    ]

    # Staff must have this permission.
    # OWNER has full access within their own company.

    required_permission = "customers_export"

    def get(self, request, *args, **kwargs):

        export_format = request.query_params.get(
            "export_format",
            "xlsx"
        ).lower()

        if export_format not in ["xlsx", "csv"]:

            return HttpResponse(
                "Unsupported export format. Use xlsx or csv.",
                status=400
            )

        # Only customers belonging to the logged-in
        # user's company will be exported.

        customers = get_filtered_customers(request)

        rows = customer_export_rows(customers)

        # --------------------------------------------------
        # CSV Export
        # --------------------------------------------------

        if export_format == "csv":

            response = HttpResponse(
                content_type="text/csv; charset=utf-8"
            )

            response["Content-Disposition"] = (
                'attachment; filename="cashcount_customers.csv"'
            )

            # BOM helps Excel recognize UTF-8 correctly.

            response.write("\ufeff")

            writer = csv.writer(response)

            writer.writerow(EXPORT_HEADERS)

            writer.writerows(rows)

            return response

        # --------------------------------------------------
        # Excel Export
        # --------------------------------------------------

        workbook = Workbook()

        worksheet = workbook.active

        worksheet.title = "Customers"

        worksheet.append(EXPORT_HEADERS)

        for row in rows:
            worksheet.append(row)

        # Header formatting

        for cell in worksheet[1]:

            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )

            cell.fill = PatternFill(
                fill_type="solid",
                fgColor="1F4E78"
            )

            cell.alignment = Alignment(
                horizontal="center"
            )

        # Column widths

        for column in worksheet.columns:

            max_length = max(
                len(str(cell.value or ""))
                for cell in column
            )

            worksheet.column_dimensions[
                column[0].column_letter
            ].width = min(max_length + 3, 40)

        worksheet.freeze_panes = "A2"

        worksheet.auto_filter.ref = worksheet.dimensions

        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        response["Content-Disposition"] = (
            'attachment; filename="cashcount_customers.xlsx"'
        )

        workbook.save(response)

        return response
