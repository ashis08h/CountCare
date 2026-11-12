import json

from datetime import date
from functools import wraps

from django.shortcuts import render
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import CompanyEmployee
from customers.models import Customer

from django.views.decorators.csrf import ensure_csrf_cookie


# ---------------------------------------------------------
# COMPANY ACCESS DECORATOR
# ---------------------------------------------------------

def company_required(view_func):
    """
    Ensure the logged-in user has an active membership
    in an active company.

    Also attaches the membership to request so views
    can access request.company_membership.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        membership = (
            CompanyEmployee.objects
            .select_related("company", "role")
            .filter(
                user=request.user,
                is_active=True,
                company__is_active=True,
            )
            .first()
        )

        if not membership:
            raise PermissionDenied(
                "Your company access is inactive. "
                "Please contact your administrator."
            )

        request.company_membership = membership

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


# ---------------------------------------------------------
# CUSTOMER MANAGEMENT PAGE
# ---------------------------------------------------------

@login_required
@ensure_csrf_cookie
@company_required
def customer_management_page(request):

    return render(
        request,
        "customers/customer_list.html",
    )


# ---------------------------------------------------------
# CUSTOMER DETAIL PAGE
# ---------------------------------------------------------

@login_required
@ensure_csrf_cookie
@company_required
def customer_detail_page(request, customer_id):

    return render(
        request,
        "customers/customer_detail.html",
        {
            "customer_id": customer_id,
        },
    )


# ---------------------------------------------------------
# CUSTOMER IMPORT PAGE
# ---------------------------------------------------------

@login_required
@ensure_csrf_cookie
@company_required
def customer_import_page(request):

    return render(
        request,
        "customers/customer_import.html",
    )


# ---------------------------------------------------------
# CUSTOMER IMPORT HISTORY PAGE
# ---------------------------------------------------------

@login_required
@ensure_csrf_cookie
@company_required
def customer_import_history_page(request):

    return render(
        request,
        "customers/customer_import_history.html",
    )


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

@login_required
@company_required
def dashboard_page(request):

    membership = request.company_membership

    # All dashboard customer data is restricted
    # to the logged-in user's company.
    customers = Customer.objects.filter(
        company_id=membership.company_id
    )

    # -----------------------------------------------------
    # CUSTOMER SUMMARY
    # -----------------------------------------------------

    total_customers = customers.count()

    active_customers = customers.filter(
        status="ACTIVE"
    ).count()

    inactive_customers = customers.filter(
        status="INACTIVE"
    ).count()

    individual_customers = customers.filter(
        customer_type="INDIVIDUAL"
    ).count()

    business_customers = customers.filter(
        customer_type="BUSINESS"
    ).count()

    # -----------------------------------------------------
    # LAST 6 MONTHS CUSTOMER REGISTRATION TREND
    # -----------------------------------------------------

    today = timezone.localdate()

    start_month = date(
        today.year if today.month > 5 else today.year - 1,
        ((today.month - 6) % 12) + 1,
        1,
    )

    monthly_results = (
        customers
        .filter(
            created_at__date__gte=start_month,
            created_at__date__lte=today,
        )
        .annotate(
            month=TruncMonth("created_at")
        )
        .values("month")
        .annotate(
            total=Count("id")
        )
        .order_by("month")
    )

    monthly_data = {
        item["month"].strftime("%Y-%m"): item["total"]
        for item in monthly_results
    }

    monthly_labels = []
    monthly_counts = []

    # Generate the last 6 months,
    # including months with zero customers.
    for offset in range(5, -1, -1):

        month_number = today.month - offset
        year = today.year

        while month_number <= 0:
            month_number += 12
            year -= 1

        month_date = date(
            year,
            month_number,
            1,
        )

        month_key = month_date.strftime("%Y-%m")

        monthly_labels.append(
            month_date.strftime("%b %Y")
        )

        monthly_counts.append(
            monthly_data.get(month_key, 0)
        )

    # -----------------------------------------------------
    # DASHBOARD CONTEXT
    # -----------------------------------------------------

    context = {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "inactive_customers": inactive_customers,
        "individual_customers": individual_customers,
        "business_customers": business_customers,

        "monthly_labels": json.dumps(monthly_labels),
        "monthly_counts": json.dumps(monthly_counts),
    }

    return render(
        request,
        "customers/dashboard.html",
        context,
    )