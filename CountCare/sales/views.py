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
)

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
    SalesVisitDetailSerializer
)

from sales.services.inventory_service import (
    receive_machine,
    transfer_machine,
)


from django.db import transaction
from rest_framework.generics import RetrieveUpdateAPIView

from customers.models import Customer
from sales.models import CustomerVisit
from django.db.models import Q
from django.utils.dateparse import parse_date

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
