from django.urls import path

from customers.views.frontend_views import customer_management_page,\
    customer_detail_page, customer_import_page, customer_import_history_page

from customers.views.customer_views import (
    CustomerListAPIView,
    CustomerCreateAPIView,
    CustomerDetailAPIView,
    CustomerDeactivateAPIView,
    CustomerActivateAPIView,
    CustomerAddressListAPIView,
)

from customers.views.customer_import_views import (
    CustomerImportTemplateAPIView,
    CustomerImportPreviewAPIView,
    CustomerImportBatchPreviewAPIView,
    CustomerImportConfirmAPIView,
)

from customers.views.customer_import_history_views import (
    CustomerImportHistoryAPIView,
    CustomerImportHistoryDetailAPIView,
    CustomerImportFailedReportAPIView,
    CustomerImportOriginalDataAPIView,
)

from customers.views.customer_export_views import (
    CustomerExportAPIView,
)

from customers.views.frontend_views import (
    dashboard_page,
    customer_management_page,
    customer_detail_page,
    customer_import_page,
    customer_import_history_page,
)

urlpatterns = [

    path(
        "dashboard/",
        dashboard_page,
        name="dashboard",
    ),

    # Customer Import History

    path(
        "customer-imports/history/",
        CustomerImportHistoryAPIView.as_view(),
        name="customer-import-history",
    ),

    path(
        "customer-imports/history/<int:batch_id>/",
        CustomerImportHistoryDetailAPIView.as_view(),
        name="customer-import-history-detail",
    ),

    path(
        "customer-imports/history/<int:batch_id>/failed-report/",
        CustomerImportFailedReportAPIView.as_view(),
        name="customer-import-failed-report",
    ),

    path(
        "customer-imports/history/<int:batch_id>/original-data/",
        CustomerImportOriginalDataAPIView.as_view(),
        name="customer-import-original-data",
    ),

    path(
        "customer-import-history/",
        customer_import_history_page,
        name="customer-import-history-page",
    ),

    path(
        "customer-imports/template/",
        CustomerImportTemplateAPIView.as_view(),
        name="customer-import-template",
    ),

    path(
        "customer-imports/preview/",
        CustomerImportPreviewAPIView.as_view(),
        name="customer-import-preview",
    ),

    path(
        "customer-imports/<int:batch_id>/preview/",
        CustomerImportBatchPreviewAPIView.as_view(),
        name="customer-import-batch-preview",
    ),

    path(
        "customer-imports/<int:batch_id>/confirm/",
        CustomerImportConfirmAPIView.as_view(),
        name="customer-import-confirm",
    ),

    # Frontend
    path(
        "customer-management/",
        customer_management_page,
        name="customer-management",
    ),

    path(
        "customer-management/<int:customer_id>/",
        customer_detail_page,
        name="customer-detail-page",
    ),

    path(
        "customer-import/",
        customer_import_page,
        name="customer-import-page",
    ),

    path(
        "customers/export/",
        CustomerExportAPIView.as_view(),
        name="customer-export",
    ),

    # Customer APIs
    path("customers/", CustomerListAPIView.as_view(), name="customer-list"),
    path("customers/create/", CustomerCreateAPIView.as_view(), name="customer-create"),
    path("customers/<int:pk>/", CustomerDetailAPIView.as_view(), name="customer-detail"),
    path("customers/<int:pk>/deactivate/", CustomerDeactivateAPIView.as_view(), name="customer-deactivate"),
    path("customers/<int:pk>/activate/", CustomerActivateAPIView.as_view(), name="customer-activate"),
    path("customers/<int:pk>/addresses/", CustomerAddressListAPIView.as_view(), name="customer-addresses"),
]