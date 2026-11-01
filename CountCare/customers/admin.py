from django.contrib import admin
from .models import Customer, CustomerAddress, CustomerImportBatch

# Register your models here.

class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):

    list_display = (
        "customer_code",
        "contact_person",
        "business_name",
        "mobile_number",
        "customer_type",
        "status",
        "created_at",
    )

    search_fields = (
        "customer_code",
        "contact_person",
        "business_name",
        "mobile_number",
    )

    list_filter = (
        "customer_type",
        "status",
        "created_at",
    )

    inlines = [CustomerAddressInline]


@admin.register(CustomerImportBatch)
class CustomerImportBatchAdmin(admin.ModelAdmin):

    list_display = (
        "file_name",
        "file_type",
        "total_rows",
        "successful_rows",
        "failed_rows",
        "status",
        "created_at",
    )

    list_filter = ("status", "file_type")