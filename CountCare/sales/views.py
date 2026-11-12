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
)

from sales.services.inventory_service import (
    receive_machine,
    transfer_machine,
)


from django.db import transaction
from rest_framework.generics import RetrieveUpdateAPIView

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
