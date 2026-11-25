# sales/views.py

# =========================================================
# DJANGO IMPORTS
# =========================================================

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import (
    PermissionDenied,
    ValidationError as DjangoValidationError,
)
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie


# =========================================================
# REST FRAMEWORK IMPORTS
# =========================================================

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


# =========================================================
# APPLICATION IMPORTS
# =========================================================

from accounts.models import CompanyEmployee
from accounts.permissions import CashCountPermission

from customers.permissions import ToggleAPIPermission

from sales.models import (
    MachineProduct,
    StockLocation,
    InventoryStock,
    CustomerMachine,
    StockMovement,
    CustomerVisit,
    VisitSaleItem,
    VisitSaleItemMachine,
    InventoryStock,
    VisitPayment,
    SalesInvoice
)

from decimal import Decimal
from django.db.models import Sum

from sales.services.inventory_service import record_stock_movement

from sales.serializers import (
    MachineProductSerializer,
    StockLocationSerializer,
    InventoryStockSerializer,
    CustomerMachineSerializer,
    StockMovementSerializer,
    ReceiveMachineSerializer,
    TransferMachineSerializer,
    SaleCustomerLookupSerializer,
    SalesEmployeeSerializer,
    CreateSalesVisitSerializer,
    SalesVisitListSerializer,
    SalesVisitDetailSerializer,
    AvailableSaleProductSerializer,
    AddSaleItemSerializer,
    UpdateSaleItemSerializer,
    VisitPaymentSerializer,
    CreateVisitPaymentSerializer,
    SalesInvoiceDetailSerializer
)

from sales.services.inventory_service import (
    receive_machine,
    transfer_machine,
)


from django.db import models, transaction
from rest_framework.generics import RetrieveUpdateAPIView

from customers.models import Customer
from sales.models import CustomerVisit
from django.db.models import Q
from django.utils.dateparse import parse_date
from sales.services.invoice_service import create_invoice_for_visit

# =========================================================
# INVENTORY API PERMISSION MIXIN
# =========================================================

class InventoryPermissionMixin:

    permission_classes = [
        IsAuthenticated,
        ToggleAPIPermission,
        CashCountPermission,
    ]

    permission_map = {
        "GET": "inventory_view",
        "POST": "inventory_add",
    }

    def get_permissions(self):
        self.required_permission = self.permission_map.get(
            self.request.method
        )

        return super().get_permissions()

    def get_company(self):
        return self.request.company_membership.company


# =========================================================
# PRODUCT API
# =========================================================

class ProductListCreateAPIView(
    InventoryPermissionMixin,
    ListCreateAPIView,
):

    serializer_class = MachineProductSerializer

    def get_queryset(self):
        return (
            MachineProduct.objects
            .filter(company=self.get_company())
            .order_by("name")
        )

    def perform_create(self, serializer):
        serializer.save(company=self.get_company())


# =========================================================
# STOCK LOCATION API
# =========================================================

class StockLocationListCreateAPIView(
    InventoryPermissionMixin,
    ListCreateAPIView,
):

    serializer_class = StockLocationSerializer

    def get_queryset(self):
        return (
            StockLocation.objects
            .filter(company=self.get_company())
            .order_by("name")
        )

    @transaction.atomic
    def perform_create(self, serializer):

        company = self.get_company()

        if serializer.validated_data.get("is_default", False):

            StockLocation.objects.filter(
                company=company,
                is_default=True,
            ).update(is_default=False)

        serializer.save(company=company)


class StockLocationDetailAPIView(
    InventoryPermissionMixin,
    RetrieveUpdateAPIView,
):

    serializer_class = StockLocationSerializer

    permission_map = {
        "GET": "inventory_view",
        "PUT": "inventory_change",
        "PATCH": "inventory_change",
    }

    def get_queryset(self):

        return StockLocation.objects.filter(
            company=self.get_company()
        )

    @transaction.atomic
    def perform_update(self, serializer):

        company = self.get_company()

        is_default = serializer.validated_data.get(
            "is_default",
            serializer.instance.is_default,
        )

        is_active = serializer.validated_data.get(
            "is_active",
            serializer.instance.is_active,
        )

        location = serializer.instance

        if is_default and not is_active:
            raise ValidationError({
                "is_default": "An inactive location cannot be the default location."
            })

        # Do not deactivate a location containing stock.
        if not is_active:

            has_stock = InventoryStock.objects.filter(
                company=company,
                location=location,
                quantity_on_hand__gt=0,
            ).exists()

            has_registered_machines = CustomerMachine.objects.filter(
                company=company,
                location=location,
                status__in=[
                    CustomerMachine.MachineStatus.IN_STOCK,
                    CustomerMachine.MachineStatus.RESERVED,
                    CustomerMachine.MachineStatus.UNDER_REPAIR,
                ],
            ).exists()

            if has_stock or has_registered_machines:
                raise ValidationError({
                    "is_active": (
                        "This location cannot be deactivated because "
                        "it still contains inventory or registered machines. "
                        "Transfer the machines to another location first."
                    )
                })

        # Only one default location per company.
        if is_default:

            StockLocation.objects.filter(
                company=company,
                is_default=True,
            ).exclude(
                pk=location.pk
            ).update(is_default=False)

        serializer.save()


# =========================================================
# INVENTORY LIST API
# =========================================================

class InventoryListAPIView(
    InventoryPermissionMixin,
    ListAPIView,
):

    serializer_class = InventoryStockSerializer

    def get_queryset(self):
        return (
            InventoryStock.objects
            .filter(company=self.get_company())
            .select_related("product", "location")
            .order_by(
                "product__name",
                "location__name",
            )
        )


# =========================================================
# MACHINE REGISTER API
# =========================================================

class MachineListAPIView(
    InventoryPermissionMixin,
    ListAPIView,
):

    serializer_class = CustomerMachineSerializer

    def get_queryset(self):

        queryset = (
            CustomerMachine.objects
            .filter(company=self.get_company())
            .select_related(
                "product",
                "location",
                "customer",
            )
            .order_by("-created_at")
        )

        customer_id = self.request.query_params.get(
            "customer_id"
        )

        machine_status = self.request.query_params.get(
            "status"
        )

        if customer_id:
            queryset = queryset.filter(
                customer_id=customer_id
            )

        if machine_status:
            queryset = queryset.filter(
                status=machine_status
            )

        return queryset


# =========================================================
# STOCK MOVEMENTS API
# =========================================================

class StockMovementListAPIView(
    InventoryPermissionMixin,
    ListAPIView,
):

    serializer_class = StockMovementSerializer

    def get_queryset(self):

        queryset = (
            StockMovement.objects
            .filter(company=self.get_company())
            .select_related(
                "product",
                "location",
                "created_by",
            )
            .order_by("-created_at")
        )

        # Optional movement type filter
        movement_type = self.request.query_params.get(
            "movement_type"
        )

        if movement_type:
            queryset = queryset.filter(
                movement_type=movement_type
            )

        # Optional product filter
        product_id = self.request.query_params.get(
            "product_id"
        )

        if product_id:
            queryset = queryset.filter(
                product_id=product_id
            )

        # Optional location filter
        location_id = self.request.query_params.get(
            "location_id"
        )

        if location_id:
            queryset = queryset.filter(
                location_id=location_id
            )

        return queryset


# =========================================================
# RECEIVE MACHINE API
# =========================================================

class ReceiveMachineAPIView(
    InventoryPermissionMixin,
    APIView,
):

    required_permission = "inventory_add"

    def post(self, request):

        serializer = ReceiveMachineSerializer(
            data=request.data,
            context={
                "company": self.get_company()
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        try:

            machine = receive_machine(
                company=self.get_company(),
                product=data["product"],
                location=data["location"],
                serial_number=data["serial_number"],
                movement_type=data["movement_type"],
                purchase_reference=data["purchase_reference"],
                unit_cost=data["unit_cost"],
                user=request.user,
            )

        except DjangoValidationError as exc:

            raise ValidationError({
                "detail": exc.messages
            })

        except IntegrityError:

            raise ValidationError({
                "detail": (
                    "Duplicate serial number or stock conflict."
                )
            })

        return Response(
            CustomerMachineSerializer(machine).data,
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# TRANSFER MACHINE API
# =========================================================

class TransferMachineAPIView(
    InventoryPermissionMixin,
    APIView,
):

    permission_map = {
        "POST": "inventory_change"
    }

    def post(self, request):

        serializer = TransferMachineSerializer(
            data=request.data,
            context={
                "company": self.get_company()
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        machine = get_object_or_404(
            CustomerMachine,
            pk=data["machine_id"],
            company=self.get_company(),
        )

        try:

            machine = transfer_machine(
                company=self.get_company(),
                machine_id=machine.id,
                destination_location=data["destination_location"],
                reference_number=data["reference_number"],
                user=request.user,
            )

        except DjangoValidationError as exc:

            raise ValidationError({
                "detail": exc.messages
            })

        return Response(
            CustomerMachineSerializer(machine).data,
            status=status.HTTP_200_OK,
        )


# =========================================================
# INVENTORY FRONTEND COMPANY ACCESS DECORATOR
# =========================================================

def inventory_company_required(view_func):

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        membership = (
            CompanyEmployee.objects
            .select_related(
                "company",
                "role",
            )
            .filter(
                user=request.user,
                is_active=True,
                company__is_active=True,
            )
            .first()
        )

        if not membership:

            raise PermissionDenied(
                "Your company access is inactive."
            )

        request.company_membership = membership

        return view_func(
            request,
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# INVENTORY DASHBOARD PAGE
# =========================================================

@login_required
@ensure_csrf_cookie
@inventory_company_required
def inventory_dashboard_page(request):

    return render(
        request,
        "sales/inventory_dashboard.html"
    )


# =========================================================
# PRODUCT MANAGEMENT PAGE
# =========================================================

@login_required
@ensure_csrf_cookie
@inventory_company_required
def product_management_page(request):

    return render(
        request,
        "sales/product_list.html"
    )


# =========================================================
# STOCK LOCATION PAGE
# =========================================================

@login_required
@ensure_csrf_cookie
@inventory_company_required
def stock_location_page(request):

    return render(
        request,
        "sales/stock_locations.html"
    )


# =========================================================
# MACHINE REGISTER PAGE
# =========================================================

@login_required
@ensure_csrf_cookie
@inventory_company_required
def machine_register_page(request):

    return render(
        request,
        "sales/machine_list.html"
    )


# =========================================================
# STOCK MOVEMENTS PAGE
# =========================================================

@login_required
@ensure_csrf_cookie
@inventory_company_required
def stock_movement_page(request):

    return render(
        request,
        "sales/stock_movements.html"
    )


@login_required
@ensure_csrf_cookie
@inventory_company_required
def sales_create_page(request):
    return render(
        request,
        "sales/sales_create.html",
    )



# =========================================================
# SALES CUSTOMER LOOKUP API
# =========================================================

class SaleCustomerLookupAPIView(
    InventoryPermissionMixin,
    ListAPIView,
):

    serializer_class = SaleCustomerLookupSerializer

    permission_map = {
        "GET": "sales_view",
    }

    def get_queryset(self):

        company = self.get_company()

        return (
            Customer.objects
            .filter(
                company=company,
                status="ACTIVE",
            )
            .order_by("business_name", "contact_person")
        )


# =========================================================
# SALES EMPLOYEE LIST API
# =========================================================

class SalesEmployeeListAPIView(
    InventoryPermissionMixin,
    ListAPIView,
):

    serializer_class = SalesEmployeeSerializer

    permission_map = {
        "GET": "sales_view",
    }

    def get_queryset(self):

        company = self.get_company()

        return (
            CompanyEmployee.objects
            .filter(
                company=company,
                company__is_active=True,
                is_active=True,
                user__is_active=True,
            )
            .select_related(
                "user",
                "role",
            )
            .order_by(
                "user__first_name",
                "user__last_name",
            )
        )


# =========================================================
# CREATE DRAFT SALES VISIT API
# =========================================================

class CreateSalesVisitAPIView(
    InventoryPermissionMixin,
    APIView,
):

    permission_map = {
        "POST": "sales_add",
    }

    def post(self, request):

        company = self.get_company()

        serializer = CreateSalesVisitSerializer(
            data=request.data,
            context={
                "request": request,
                "company": company,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        visit = serializer.save()

        return Response(
            {
                "message": "Draft sales visit created successfully.",
                "visit_id": visit.id,
                "visit_number": visit.visit_number,
                "status": visit.status,
                "customer_id": visit.customer_id,
                "salesman_id": visit.salesman_id,
                "stock_location_id": visit.stock_location_id,
                "billing_address": visit.location_address,
                "visit_date": visit.visit_date,
            },
            status=status.HTTP_201_CREATED,
        )


@login_required
@ensure_csrf_cookie
@inventory_company_required
def sales_visits_page(request):
    return render(
        request,
        "sales/sales_visits.html",
    )



# =========================================================
# SALES VISITS LIST API
# =========================================================

class SalesVisitListAPIView(
    InventoryPermissionMixin,
    ListAPIView,
):

    serializer_class = SalesVisitListSerializer

    permission_map = {
        "GET": "sales_view",
    }

    def get_company_queryset(self):
        return (
            CustomerVisit.objects
            .filter(company=self.get_company())
            .select_related(
                "customer",
                "salesman__user",
                "stock_location",
            )
            .prefetch_related("sale_items")
            .order_by("-visit_date", "-created_at")
        )

    def get_queryset(self):

        queryset = self.get_company_queryset()

        # Status filter
        status_filter = self.request.query_params.get("status")

        if status_filter:
            valid_statuses = [
                choice[0]
                for choice in CustomerVisit.VisitStatus.choices
            ]

            if status_filter not in valid_statuses:
                raise ValidationError({
                    "status": "Invalid visit status."
                })

            queryset = queryset.filter(status=status_filter)

        # Visit type filter
        visit_type = self.request.query_params.get("visit_type")

        if visit_type:
            valid_types = [
                choice[0]
                for choice in CustomerVisit.VisitType.choices
            ]

            if visit_type not in valid_types:
                raise ValidationError({
                    "visit_type": "Invalid visit type."
                })

            queryset = queryset.filter(visit_type=visit_type)

        # Salesman filter
        salesman_id = self.request.query_params.get("salesman_id")

        if salesman_id:
            if not salesman_id.isdigit():
                raise ValidationError({
                    "salesman_id": "Invalid salesman ID."
                })

            queryset = queryset.filter(
                salesman_id=int(salesman_id)
            )

        # Warehouse filter
        location_id = self.request.query_params.get("location_id")

        if location_id:
            if not location_id.isdigit():
                raise ValidationError({
                    "location_id": "Invalid warehouse ID."
                })

            queryset = queryset.filter(
                stock_location_id=int(location_id)
            )

        # Date range filters
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if date_from:
            parsed_from = parse_date(date_from)

            if not parsed_from:
                raise ValidationError({
                    "date_from": "Use YYYY-MM-DD format."
                })

            queryset = queryset.filter(
                visit_date__gte=parsed_from
            )

        if date_to:
            parsed_to = parse_date(date_to)

            if not parsed_to:
                raise ValidationError({
                    "date_to": "Use YYYY-MM-DD format."
                })

            queryset = queryset.filter(
                visit_date__lte=parsed_to
            )

        if date_from and date_to and parsed_from > parsed_to:
            raise ValidationError({
                "date_to": "End date cannot be before start date."
            })

        # Search by visit number, customer, mobile or code
        search = self.request.query_params.get("search", "").strip()

        if search:
            queryset = queryset.filter(
                Q(visit_number__icontains=search)
                | Q(customer__business_name__icontains=search)
                | Q(customer__contact_person__icontains=search)
                | Q(customer__customer_code__icontains=search)
                | Q(customer_contact_number__icontains=search)
            )

        return queryset

    def list(self, request, *args, **kwargs):

        response = super().list(request, *args, **kwargs)

        # Summary cards are based on all visits belonging
        # to the company, not just the currently filtered page.
        company_visits = self.get_company_queryset()

        response.data["summary"] = {
            "total": company_visits.count(),
            "draft": company_visits.filter(
                status=CustomerVisit.VisitStatus.DRAFT
            ).count(),
            "in_progress": company_visits.filter(
                status=CustomerVisit.VisitStatus.IN_PROGRESS
            ).count(),
            "completed": company_visits.filter(
                status=CustomerVisit.VisitStatus.COMPLETED
            ).count(),
            "cancelled": company_visits.filter(
                status=CustomerVisit.VisitStatus.CANCELLED
            ).count(),
        }

        return response



# =========================================================
# SALES VISIT DETAIL API
# =========================================================

class SalesVisitDetailAPIView(
    InventoryPermissionMixin,
    APIView,
):

    permission_map = {
        "GET": "sales_view",
    }

    def get(self, request, pk):

        visit = get_object_or_404(
            CustomerVisit.objects
            .filter(company=self.get_company())
            .select_related(
                "customer",
                "salesman__user",
                "stock_location",
            )
            .prefetch_related(
                "sale_items__product",
            ),
            pk=pk,
        )

        serializer = SalesVisitDetailSerializer(visit)

        return Response(serializer.data)


@login_required
@ensure_csrf_cookie
@inventory_company_required
def sales_visit_detail_page(request, pk):
    return render(
        request,
        "sales/sales_visit_detail.html",
        {"visit_id": pk},
    )



# =========================================================
# AVAILABLE PRODUCTS FOR A SALES VISIT
# =========================================================

class AvailableSaleProductsAPIView(
    InventoryPermissionMixin,
    ListAPIView,
):

    serializer_class = AvailableSaleProductSerializer

    permission_map = {
        "GET": "sales_view",
    }

    def get_queryset(self):

        company = self.get_company()

        visit = get_object_or_404(
            CustomerVisit,
            pk=self.kwargs["pk"],
            company=company,
        )

        self.visit = visit

        if not visit.stock_location:
            return MachineProduct.objects.none()

        # Only show products with available stock.
        stock_product_ids = (
            InventoryStock.objects
            .filter(
                company=company,
                location=visit.stock_location,
                quantity_on_hand__gt=0,
            )
            .exclude(
                quantity_on_hand__lte=models.F("reserved_quantity")
            )
            .values_list("product_id", flat=True)
        )

        return (
            MachineProduct.objects
            .filter(
                company=company,
                is_active=True,
                id__in=stock_product_ids,
            )
            .order_by("name")
        )

    def get_serializer_context(self):

        context = super().get_serializer_context()

        context.update({
            "company": self.get_company(),
            "visit": self.visit,
            "location": self.visit.stock_location,
        })

        return context

    def list(self, request, *args, **kwargs):

        queryset = self.get_queryset()

        serializer = self.get_serializer(
            queryset,
            many=True,
        )

        data = serializer.data

        # Only show products with at least one available serial number.
        data = [
            product for product in data
            if product["available_machines"]
        ]

        for product in data:
            product["available_quantity"] = len(
                product["available_machines"]
            )

        return Response(data)


# =========================================================
# ADD PRODUCT TO DRAFT SALES VISIT
# =========================================================

class AddSaleItemAPIView(
    InventoryPermissionMixin,
    APIView,
):

    permission_map = {
        "POST": "sales_add",
    }

    @transaction.atomic
    def post(self, request, pk):

        company = self.get_company()

        visit = get_object_or_404(
            CustomerVisit.objects.select_for_update(),
            pk=pk,
            company=company,
        )

        serializer = AddSaleItemSerializer(
            data=request.data,
            context={
                "company": company,
                "visit": visit,
            },
        )

        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                sale_item = serializer.save()

        except IntegrityError:
            raise ValidationError({
                "machine_ids": (
                    "A selected machine was selected by another "
                    "draft sale. Refresh available stock and try again."
                )
            })

        return Response(
            {
                "message": "Product added to draft sale successfully.",
                "item_id": sale_item.id,
                "product_id": sale_item.product_id,
                "product_name": sale_item.product.name,
                "quantity": sale_item.quantity,
                "unit_price": sale_item.unit_price,
                "discount_amount": sale_item.discount_amount,
                "gst_rate": sale_item.gst_rate,
                "gross_amount": sale_item.gross_amount,
                "taxable_amount": sale_item.taxable_amount,
                "gst_amount": sale_item.gst_amount,
                "total_amount": sale_item.total_amount,
            },
            status=status.HTTP_201_CREATED,
        )



# =====================================================
# EDIT AND REMOVE SALE ITEM
# =====================================================

class SaleItemDetailAPIView(
    InventoryPermissionMixin,
    APIView,
):

    permission_map = {
        "PATCH": "sales_change",
        "DELETE": "sales_delete",
    }

    def get_visit_and_item(self, request, pk, item_id):

        company = self.get_company()

        visit = get_object_or_404(
            CustomerVisit.objects.select_for_update(),
            pk=pk,
            company=company,
        )

        if visit.status != CustomerVisit.VisitStatus.DRAFT:
            raise ValidationError({
                "visit": "Only draft sales visits can be modified."
            })

        sale_item = get_object_or_404(
            VisitSaleItem.objects.select_for_update().select_related(
                "product"
            ),
            pk=item_id,
            visit=visit,
        )

        return visit, sale_item

    @transaction.atomic
    def patch(self, request, pk, item_id):

        visit, sale_item = self.get_visit_and_item(
            request,
            pk,
            item_id,
        )

        serializer = UpdateSaleItemSerializer(
            sale_item,
            data=request.data,
            partial=True,
            context={
                "visit": visit,
            },
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            "message": "Sale item updated successfully.",
            "item_id": sale_item.id,
            "unit_price": str(sale_item.unit_price),
            "discount_amount": str(sale_item.discount_amount),
            "gst_rate": str(sale_item.gst_rate),
            "total_amount": str(sale_item.total_amount),
        })

    @transaction.atomic
    def delete(self, request, pk, item_id):

        visit, sale_item = self.get_visit_and_item(
            request,
            pk,
            item_id,
        )

        sale_item_id = sale_item.id

        # Deleting the sale item also deletes its
        # VisitSaleItemMachine selection records through
        # the existing foreign-key cascade.
        # First release all machine selections associated
        # with this draft sale item.
        VisitSaleItemMachine.objects.filter(
            sale_item=sale_item
        ).delete()

        # Now remove the sale item itself.
        sale_item.delete()

        return Response({
            "message": "Sale item removed successfully.",
            "item_id": sale_item_id,
        })



class ConfirmSalesVisitAPIView(InventoryPermissionMixin, APIView):
    permission_map = {
        "POST": "sales_approve",
    }

    @transaction.atomic
    def post(self, request, pk):
        company = self.get_company()

        # Lock the visit to prevent simultaneous confirmation.
        visit = get_object_or_404(
            CustomerVisit.objects.select_for_update().select_related(
                "customer",
                "stock_location",
            ),
            pk=pk,
            company=company,
        )

        if visit.status != CustomerVisit.VisitStatus.DRAFT:
            raise ValidationError({
                "visit": "Only draft sales visits can be confirmed."
            })

        if not visit.stock_location:
            raise ValidationError({
                "stock_location": "Please select a stock location before confirming."
            })

        sale_items = list(
            VisitSaleItem.objects.select_for_update()
            .filter(visit=visit)
            .select_related("product")
            .order_by("id")
        )

        if not sale_items:
            raise ValidationError({
                "sale_items": "Add at least one product before confirming the sale."
            })

        for sale_item in sale_items:
            # Find the physical machines selected for this sale item.
            selections = list(
                VisitSaleItemMachine.objects.filter(
                    sale_item=sale_item
                ).values_list("machine_id", flat=True)
            )

            if len(selections) != sale_item.quantity:
                raise ValidationError({
                    "sale_items": (
                        f"Selected machine count does not match the quantity "
                        f"for product {sale_item.product.name}."
                    )
                })

            # Lock the selected machine records.
            machines = list(
                CustomerMachine.objects.select_for_update()
                .filter(
                    pk__in=selections,
                    company=company,
                )
                .order_by("id")
            )

            if len(machines) != len(selections):
                raise ValidationError({
                    "machines": "One or more selected machines are unavailable."
                })

            for machine in machines:
                if machine.product_id != sale_item.product_id:
                    raise ValidationError({
                        "machines": (
                            f"Machine {machine.serial_number} does not belong "
                            "to the selected product."
                        )
                    })

                if machine.location_id != visit.stock_location_id:
                    raise ValidationError({
                        "machines": (
                            f"Machine {machine.serial_number} is not available "
                            "at the selected stock location."
                        )
                    })

                if machine.status != CustomerMachine.MachineStatus.IN_STOCK:
                    raise ValidationError({
                        "machines": (
                            f"Machine {machine.serial_number} is no longer "
                            "in stock."
                        )
                    })

                if machine.customer_id is not None or machine.sale_item_id is not None:
                    raise ValidationError({
                        "machines": (
                            f"Machine {machine.serial_number} has already "
                            "been assigned to another sale."
                        )
                    })

                # Deduct one physical machine and create its SALE audit record.
                try:
                    record_stock_movement(
                        company=company,
                        product=sale_item.product,
                        location=visit.stock_location,
                        movement_type=StockMovement.MovementType.SALE,
                        quantity=1,
                        user=request.user,
                        reference_number=visit.visit_number,
                        notes=f"Sale confirmed for visit {visit.visit_number}",
                        machine=machine,
                        visit=visit,
                        sale_item=sale_item,
                    )
                except DjangoValidationError as exc:
                    detail = getattr(exc, "message_dict", None) or exc.messages
                    raise ValidationError(detail)

                # Assign the machine to the customer and sale item.
                machine.status = CustomerMachine.MachineStatus.SOLD
                machine.customer = visit.customer
                machine.sale_item = sale_item

                machine.save(
                    update_fields=[
                        "status",
                        "customer",
                        "sale_item",
                        "updated_at",
                    ]
                )

        # Mark the visit completed only after every machine is processed.
        visit.status = CustomerVisit.VisitStatus.COMPLETED
        visit.save(update_fields=["status", "updated_at"])

        # Generate GST invoice within the same transaction.
        invoice = create_invoice_for_visit(
            visit=visit,
            user=request.user,
        )

        visit.refresh_from_db()

        return Response(
            {
                "message": "Sale confirmed and GST invoice generated successfully.",
                "visit": SalesVisitDetailSerializer(visit).data,
                "invoice": {
                    "id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "invoice_date": invoice.invoice_date,
                    "supply_type": invoice.supply_type,
                    "total_taxable_value": str(invoice.total_taxable_value),
                    "total_cgst": str(invoice.total_cgst),
                    "total_sgst": str(invoice.total_sgst),
                    "total_igst": str(invoice.total_igst),
                    "total_discount": str(invoice.total_discount),
                    "grand_total": str(invoice.grand_total),
                },
            },
            status=status.HTTP_200_OK,
        )


class VisitPaymentAPIView(InventoryPermissionMixin, APIView):

    permission_map = {
        "GET": "payments_view",
        "POST": "payments_add",
    }

    def get_visit(self, pk):
        return get_object_or_404(
            CustomerVisit.objects.filter(
                company=self.get_company()
            ),
            pk=pk,
        )

    def get_payment_summary(self, visit):

        total_amount = sum(
            (
                item.total_amount
                for item in visit.sale_items.all()
            ),
            Decimal("0.00"),
        )

        total_received = (
            VisitPayment.objects.filter(
                visit=visit,
                payment_status=VisitPayment.PaymentStatus.RECEIVED,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        balance_amount = total_amount - total_received

        return {
            "total_amount": total_amount,
            "total_received": total_received,
            "balance_amount": balance_amount,
        }

    def get(self, request, pk):

        visit = self.get_visit(pk)

        payments = (
            VisitPayment.objects.filter(visit=visit)
            .select_related("received_by")
            .order_by("-payment_date", "-created_at")
        )

        summary = self.get_payment_summary(visit)

        return Response({
            "visit_id": visit.id,
            "visit_number": visit.visit_number,
            "payments": VisitPaymentSerializer(
                payments,
                many=True,
            ).data,
            "summary": summary,
        })

    @transaction.atomic
    def post(self, request, pk):

        company = self.get_company()

        visit = get_object_or_404(
            CustomerVisit.objects.select_for_update(),
            pk=pk,
            company=company,
        )

        if visit.status != CustomerVisit.VisitStatus.COMPLETED:
            raise ValidationError({
                "visit": "Payments can only be recorded for completed sales visits."
            })

        serializer = CreateVisitPaymentSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        summary = self.get_payment_summary(visit)

        amount = data["amount"]

        if summary["balance_amount"] <= Decimal("0.00"):
            raise ValidationError({
                "amount": "This sale has already been fully paid."
            })

        if amount > summary["balance_amount"]:
            raise ValidationError({
                "amount": (
                    f"Payment exceeds the outstanding balance of "
                    f"{summary['balance_amount']}."
                )
            })

        payment = VisitPayment.objects.create(
            visit=visit,
            amount=amount,
            payment_mode=data["payment_mode"],
            payment_status=VisitPayment.PaymentStatus.RECEIVED,
            transaction_reference=data.get(
                "transaction_reference", ""
            ),
            notes=data.get("notes", ""),
            received_by=request.user,
        )

        updated_summary = self.get_payment_summary(visit)

        return Response({
            "message": "Payment recorded successfully.",
            "payment": VisitPaymentSerializer(payment).data,
            "summary": updated_summary,
        }, status=status.HTTP_201_CREATED)



class SalesInvoiceDetailAPIView(
    InventoryPermissionMixin,
    APIView,
):
    permission_map = {
        "GET": "sales_view",
    }

    def get(self, request, pk):
        company = self.get_company()

        invoice = get_object_or_404(
            SalesInvoice.objects
            .filter(
                company=company,
                visit_id=pk,
            )
            .prefetch_related("items"),
        )

        serializer = SalesInvoiceDetailSerializer(invoice)

        return Response(serializer.data)
