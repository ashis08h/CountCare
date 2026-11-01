from django.shortcuts import render


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