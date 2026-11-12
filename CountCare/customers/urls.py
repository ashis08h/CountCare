
from django.urls import path

# Frontend views
from customers.views.frontend_views import (
    dashboard_page,
    customer_management_page,
    customer_detail_page,
    customer_import_page,
    customer_import_history_page,
)

# Customer API views
from customers.views.customer_views import (
    CustomerListAPIView,
    CustomerCreateAPIView,
    CustomerDetailAPIView,
    CustomerDeactivateAPIView,
    CustomerActivateAPIView,
    CustomerAddressListAPIView,
)

# Customer import views
from customers.views.customer_import_views import (
    CustomerImportTemplateAPIView,
    CustomerImportPreviewAPIView,
    CustomerImportBatchPreviewAPIView,
    CustomerImportConfirmAPIView,
)

# Customer import history views
from customers.views.customer_import_history_views import (
    CustomerImportHistoryAPIView,
    CustomerImportHistoryDetailAPIView,
    CustomerImportFailedReportAPIView,
    CustomerImportOriginalDataAPIView,
)

# Customer export view
from customers.views.customer_export_views import (
    CustomerExportAPIView,
)


urlpatterns = [

    # =====================================================
    # DASHBOARD
    # =====================================================

    path(
        "dashboard/",
        dashboard_page,
        name="dashboard",
    ),

    # =====================================================
    # CUSTOMER FRONTEND PAGES
    # =====================================================

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

    # =====================================================
    # CUSTOMER IMPORT FRONTEND PAGES
    # =====================================================

    path(
        "customer-import/",
        customer_import_page,
        name="customer-import-page",
    ),

    path(
        "customer-import-history/",
        customer_import_history_page,
        name="customer-import-history-page",
    ),

    # =====================================================
    # CUSTOMER APIs
    # =====================================================

    path(
        "customers/",
        CustomerListAPIView.as_view(),
        name="customer-list",
    ),

    path(
        "customers/create/",
        CustomerCreateAPIView.as_view(),
        name="customer-create",
    ),

    path(
        "customers/<int:pk>/",
        CustomerDetailAPIView.as_view(),
        name="customer-detail",
    ),

    path(
        "customers/<int:pk>/deactivate/",
        CustomerDeactivateAPIView.as_view(),
        name="customer-deactivate",
    ),

    path(
        "customers/<int:pk>/activate/",
        CustomerActivateAPIView.as_view(),
        name="customer-activate",
    ),

    path(
        "customers/<int:pk>/addresses/",
        CustomerAddressListAPIView.as_view(),
        name="customer-addresses",
    ),

    # =====================================================
    # CUSTOMER EXPORT
    # =====================================================

    path(
        "customers/export/",
        CustomerExportAPIView.as_view(),
        name="customer-export",
    ),

    # =====================================================
    # CUSTOMER IMPORT APIs
    # =====================================================

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

    # =====================================================
    # CUSTOMER IMPORT HISTORY APIs
    # =====================================================

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

]
