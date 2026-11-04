import json

from datetime import date

from django.shortcuts import render
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from customers.models import Customer

from django.contrib.auth.decorators import login_required


def customer_management_page(request):
    return render(request, "customers/customer_list.html")


def customer_detail_page(request, customer_id):
    return render(
        request,
        "customers/customer_detail.html",
        {"customer_id": customer_id}
    )


def customer_import_page(request):
    return render(request, "customers/customer_import.html")


def customer_import_history_page(request):
    return render(
        request,
        "customers/customer_import_history.html"
    )


@login_required
def dashboard_page(request):
    # Customer summary
    total_customers = Customer.objects.count()

    active_customers = Customer.objects.filter(
        status="ACTIVE"
    ).count()

    inactive_customers = Customer.objects.filter(
        status="INACTIVE"
    ).count()

    individual_customers = Customer.objects.filter(
        customer_type="INDIVIDUAL"
    ).count()

    business_customers = Customer.objects.filter(
        customer_type="BUSINESS"
    ).count()

    # Last 6 months customer registration trend
    today = timezone.localdate()

    start_month = date(
        today.year if today.month > 5 else today.year - 1,
        ((today.month - 6) % 12) + 1,
        1,
    )

    monthly_results = (
        Customer.objects
        .filter(created_at__date__gte=start_month)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    monthly_data = {
        item["month"].strftime("%Y-%m"): item["total"]
        for item in monthly_results
    }

    monthly_labels = []
    monthly_counts = []

    # Generate the last 6 months, including months with zero customers
    for offset in range(5, -1, -1):
        month_number = today.month - offset
        year = today.year

        while month_number <= 0:
            month_number += 12
            year -= 1

        month_date = date(year, month_number, 1)
        month_key = month_date.strftime("%Y-%m")

        monthly_labels.append(month_date.strftime("%b %Y"))
        monthly_counts.append(monthly_data.get(month_key, 0))

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
        context
    )