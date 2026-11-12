
# sales/services/inventory_service.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from sales.models import (
    CustomerMachine,
    InventoryStock,
    StockMovement,
)


INWARD_TYPES = {
    StockMovement.MovementType.OPENING,
    StockMovement.MovementType.PURCHASE,
    StockMovement.MovementType.CUSTOMER_RETURN,
    StockMovement.MovementType.ADJUSTMENT_IN,
    StockMovement.MovementType.TRANSFER_IN,
}

OUTWARD_TYPES = {
    StockMovement.MovementType.SALE,
    StockMovement.MovementType.SUPPLIER_RETURN,
    StockMovement.MovementType.ADJUSTMENT_OUT,
    StockMovement.MovementType.TRANSFER_OUT,
    StockMovement.MovementType.REPLACEMENT,
}


@transaction.atomic
def record_stock_movement(
    *,
    company,
    product,
    location,
    movement_type,
    quantity,
    user,
    reference_number="",
    notes="",
    machine=None,
    visit=None,
    sale_item=None,
    unit_cost=0,
):
    """
    Update stock and create an audit record atomically.

    Use this service for all stock quantity changes.
    """

    if company is None or product is None or location is None:
        raise ValidationError("Company, product and location are required.")

    if product.company_id != company.id:
        raise ValidationError("Product belongs to another company.")

    if location.company_id != company.id:
        raise ValidationError("Location belongs to another company.")

    if type(quantity) is not int or quantity <= 0:
        raise ValidationError("Quantity must be a positive integer.")

    if movement_type not in INWARD_TYPES | OUTWARD_TYPES:
        raise ValidationError("Invalid stock movement type.")

    if machine is not None:
        if machine.company_id != company.id:
            raise ValidationError("Machine belongs to another company.")

        if machine.product_id != product.id:
            raise ValidationError("Machine product mismatch.")

        if quantity != 1:
            raise ValidationError(
                "A serial-numbered movement must have quantity 1."
            )

    if visit is not None and visit.company_id != company.id:
        raise ValidationError("Visit belongs to another company.")

    if sale_item is not None:
        if sale_item.visit.company_id != company.id:
            raise ValidationError("Sale item belongs to another company.")

        if sale_item.product_id != product.id:
            raise ValidationError("Sale item product mismatch.")

        if visit is not None and sale_item.visit_id != visit.id:
            raise ValidationError("Sale item does not belong to visit.")

    # Ensure the stock balance row exists.
    InventoryStock.objects.get_or_create(
        company=company,
        product=product,
        location=location,
        defaults={
            "quantity_on_hand": 0,
            "reserved_quantity": 0,
        },
    )

    # Lock the stock balance before modifying it.
    stock = (
        InventoryStock.objects
        .select_for_update()
        .get(
            company=company,
            product=product,
            location=location,
        )
    )

    if movement_type in INWARD_TYPES:
        stock.quantity_on_hand = F("quantity_on_hand") + quantity

    else:
        if stock.available_quantity < quantity:
            raise ValidationError(
                f"Insufficient stock. Available: "
                f"{stock.available_quantity}, requested: {quantity}."
            )

        stock.quantity_on_hand = F("quantity_on_hand") - quantity

    stock.save(update_fields=["quantity_on_hand", "updated_at"])

    movement = StockMovement.objects.create(
        company=company,
        product=product,
        location=location,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=unit_cost,
        reference_number=reference_number,
        notes=notes,
        machine=machine,
        visit=visit,
        sale_item=sale_item,
        created_by=user,
    )

    return movement


@transaction.atomic
def receive_machine(
    *,
    company,
    product,
    location,
    serial_number,
    user,
    movement_type=StockMovement.MovementType.PURCHASE,
    purchase_reference="",
    unit_cost=0,
):
    """
    Receive one physical machine into stock.
    Creates its serial record and increases inventory.
    """

    if movement_type not in {
        StockMovement.MovementType.OPENING,
        StockMovement.MovementType.PURCHASE,
    }:
        raise ValidationError("Invalid receiving movement type.")

    serial_number = serial_number.strip()

    if not serial_number:
        raise ValidationError("Serial number is required.")

    if CustomerMachine.objects.filter(
        company=company,
        serial_number=serial_number,
    ).exists():
        raise ValidationError(
            f"Serial number {serial_number} already exists."
        )

    machine = CustomerMachine.objects.create(
        company=company,
        product=product,
        location=location,
        serial_number=serial_number,
        status=CustomerMachine.MachineStatus.IN_STOCK,
        purchase_reference=purchase_reference,
    )

    record_stock_movement(
        company=company,
        product=product,
        location=location,
        movement_type=movement_type,
        quantity=1,
        user=user,
        reference_number=purchase_reference,
        unit_cost=unit_cost,
        machine=machine,
    )

    return machine


@transaction.atomic
def transfer_machine(
    *,
    company,
    machine_id,
    destination_location,
    user,
    reference_number="",
):
    """
    Move a machine between company stock locations.
    """

    machine = (
        CustomerMachine.objects
        .select_for_update()
        .select_related("product", "location")
        .get(pk=machine_id, company=company)
    )

    if machine.status != CustomerMachine.MachineStatus.IN_STOCK:
        raise ValidationError(
            "Only machines currently in stock can be transferred."
        )

    if machine.location_id is None:
        raise ValidationError("Machine has no source location.")

    if destination_location.company_id != company.id:
        raise ValidationError("Destination belongs to another company.")

    if machine.location_id == destination_location.id:
        raise ValidationError(
            "Source and destination cannot be the same."
        )

    source_location = machine.location

    record_stock_movement(
        company=company,
        product=machine.product,
        location=source_location,
        movement_type=StockMovement.MovementType.TRANSFER_OUT,
        quantity=1,
        user=user,
        machine=machine,
        reference_number=reference_number,
    )

    record_stock_movement(
        company=company,
        product=machine.product,
        location=destination_location,
        movement_type=StockMovement.MovementType.TRANSFER_IN,
        quantity=1,
        user=user,
        machine=machine,
        reference_number=reference_number,
    )

    machine.location = destination_location
    machine.save(update_fields=["location", "updated_at"])

    return machine
