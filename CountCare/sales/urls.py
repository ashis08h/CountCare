
# sales/urls.py

from django.urls import path

from sales.views import (
    ProductListCreateAPIView,
    StockLocationListCreateAPIView,
    InventoryListAPIView,
    MachineListAPIView,
    StockMovementListAPIView,
    ReceiveMachineAPIView,
    TransferMachineAPIView,
    inventory_dashboard_page,
    product_management_page,
    stock_location_page,
    machine_register_page,
    stock_movement_page,
    StockLocationDetailAPIView,
    SaleCustomerLookupAPIView,
    SalesEmployeeListAPIView,
    CreateSalesVisitAPIView,
    sales_create_page,
    sales_visits_page,
    SalesVisitListAPIView,
    sales_visit_detail_page,
    SalesVisitDetailAPIView,
    AvailableSaleProductsAPIView,
    AddSaleItemAPIView,
    SaleItemDetailAPIView,
    ConfirmSalesVisitAPIView,
    VisitPaymentAPIView,
    SalesInvoiceDetailAPIView
)


urlpatterns = [
    path(
        "inventory-dashboard/",
        inventory_dashboard_page,
        name="inventory-dashboard",
    ),

    path(
        "products-management/",
        product_management_page,
        name="sales-product-management",
    ),

    path(
        "stock-locations/",
        stock_location_page,
        name="sales-stock-locations-page",
    ),

    path(
        "machine-register/",
        machine_register_page,
        name="sales-machine-register",
    ),

    path(
        "stock-movements/",
        stock_movement_page,
        name="sales-stock-movements-page",
    ),

    # =====================================================
    # INVENTORY APIs
    # =====================================================

    path(
        "products/",
        ProductListCreateAPIView.as_view(),
        name="sales-products",
    ),

    path(
        "locations/",
        StockLocationListCreateAPIView.as_view(),
        name="sales-stock-locations-api",
    ),

    path(
        "inventory/",
        InventoryListAPIView.as_view(),
        name="sales-inventory",
    ),

    path(
        "machines/",
        MachineListAPIView.as_view(),
        name="sales-machines",
    ),

    path(
        "movements/",
        StockMovementListAPIView.as_view(),
        name="sales-stock-movements-api",
    ),

    path(
        "machines/receive/",
        ReceiveMachineAPIView.as_view(),
        name="sales-receive-machine",
    ),

    path(
        "machines/transfer/",
        TransferMachineAPIView.as_view(),
        name="sales-transfer-machine",
    ),

    path(
        "locations/<int:pk>/",
        StockLocationDetailAPIView.as_view(),
        name="sales-stock-location-detail",
    ),

    path(
        "customers-for-sale/",
        SaleCustomerLookupAPIView.as_view(),
        name="sales-customers-for-sale",
    ),

    path(
        "sales-employees/",
        SalesEmployeeListAPIView.as_view(),
        name="sales-employees",
    ),

    path(
        "visits/create/",
        CreateSalesVisitAPIView.as_view(),
        name="sales-create-visit",
    ),

    path(
        "create-sale/",
        sales_create_page,
        name="sales-create-page",
    ),

    path(
        "sales-visits/",
        sales_visits_page,
        name="sales-visits-page",
    ),

    path(
        "visits/",
        SalesVisitListAPIView.as_view(),
        name="sales-visits-api",
    ),

    path(
        "sales-visits/<int:pk>/",
        sales_visit_detail_page,
        name="sales-visit-detail-page",
    ),

    path(
        "visits/<int:pk>/",
        SalesVisitDetailAPIView.as_view(),
        name="sales-visit-detail-api",
    ),

    path(
        "visits/<int:pk>/available-products/",
        AvailableSaleProductsAPIView.as_view(),
        name="sales-available-products",
    ),

    path(
        "visits/<int:pk>/items/",
        AddSaleItemAPIView.as_view(),
        name="sales-add-item",
    ),

    path(
        "visits/<int:pk>/items/<int:item_id>/",
        SaleItemDetailAPIView.as_view(),
        name="sales-sale-item-detail",
    ),

    path(
        "visits/<int:pk>/confirm/",
        ConfirmSalesVisitAPIView.as_view(),
        name="sales-confirm-visit",
    ),

    path(
        "visits/<int:pk>/payments/",
        VisitPaymentAPIView.as_view(),
        name="sales-visit-payments",
    ),

    path(
        "visits/<int:pk>/invoice/",
        SalesInvoiceDetailAPIView.as_view(),
        name="sales-visit-invoice",
    ),
]

