
# sales/services/invoice_service.py

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import Company
from sales.models import (
    CustomerVisit,
    SalesInvoice,
    SalesInvoiceItem,
)


ZERO = Decimal("0.00")
ONE_HUNDRED = Decimal("100.00")
TWO_PLACES = Decimal("0.01")


def money(value):
    """Round monetary values to two decimal places."""
    return Decimal(value).quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )


def get_financial_year(invoice_date):
    """
    Indian financial year: April to March.

    Example:
    01-Apr-2026 to 31-Mar-2027 = 2026-27
    """
    if invoice_date.month >= 4:
        start_year = invoice_date.year
    else:
        start_year = invoice_date.year - 1

    end_year = start_year + 1

    return f"{start_year}-{str(end_year)[-2:]}"


def get_next_invoice_number(company, financial_year):
    """
    Generate the next invoice number for this company and FY.

    The company row is locked by create_invoice_for_visit()
    before this function is called.
    """
    last_invoice = (
        SalesInvoice.objects
        .filter(
            company=company,
            financial_year=financial_year,
        )
        .order_by("-sequence_number")
        .first()
    )

    sequence_number = (
        last_invoice.sequence_number + 1
        if last_invoice
        else 1
    )

    invoice_number = (
        f"CC/{financial_year}/{sequence_number:04d}"
    )

    return invoice_number, sequence_number


def get_seller_snapshot(company):
    return {
        "company_name": company.name,
        "gstin": company.gst_number,
        "registration_number": company.registration_number,
        "address": company.address,
        "city": company.city,
        "state": company.state,
        "pincode": company.pincode,
        "email": company.email,
        "phone": company.phone,
        "domain": company.domain,
    }


def get_buyer_snapshot(visit, billing_address):
    customer = visit.customer

    return {
        "customer_code": customer.customer_code,
        "business_name": (
            customer.business_name
            or customer.contact_person
        ),
        "contact_person": customer.contact_person,
        "gstin": customer.gst_number,
        "pan_number": customer.pan_number,
        "mobile_number": customer.mobile_number,
        "email": customer.email,
        "billing_address": {
            "address_line_1": billing_address.address_line_1,
            "address_line_2": billing_address.address_line_2,
            "city": billing_address.city,
            "district": billing_address.district,
            "state": billing_address.state,
            "pincode": billing_address.pincode,
            "country": billing_address.country,
        },
    }


def calculate_gst(taxable_value, gst_rate, intra_state):
    """
    Calculate GST for one invoice line.

    Intra-state: CGST + SGST.
    Inter-state: IGST.

    This uses the seller-state versus billing-state
    comparison as the initial place-of-supply rule.
    """
    taxable_value = money(taxable_value)
    gst_rate = Decimal(gst_rate)

    cgst_rate = ZERO
    cgst_amount = ZERO
    sgst_rate = ZERO
    sgst_amount = ZERO
    igst_rate = ZERO
    igst_amount = ZERO

    if intra_state:
        half_rate = gst_rate / Decimal("2")

        cgst_rate = half_rate
        sgst_rate = half_rate

        cgst_amount = money(
            taxable_value * cgst_rate / ONE_HUNDRED
        )
        sgst_amount = money(
            taxable_value * sgst_rate / ONE_HUNDRED
        )

    else:
        igst_rate = gst_rate
        igst_amount = money(
            taxable_value * igst_rate / ONE_HUNDRED
        )

    total_tax = (
        cgst_amount
        + sgst_amount
        + igst_amount
    )

    return {
        "cgst_rate": cgst_rate,
        "cgst_amount": cgst_amount,
        "sgst_rate": sgst_rate,
        "sgst_amount": sgst_amount,
        "igst_rate": igst_rate,
        "igst_amount": igst_amount,
        "total_tax": total_tax,
    }


@transaction.atomic
def create_invoice_for_visit(visit, user=None):
    """
    Create one GST invoice for a confirmed sales visit.

    Call this from the sales confirmation transaction.
    The invoice and its items will roll back if any
    part of invoice generation fails.
    """

    # Reload and lock the company row. This serializes
    # invoice-number allocation for this company.
    company = (
        Company.objects
        .select_for_update()
        .get(pk=visit.company_id)
    )

    # Lock and reload the visit with its related records.
    visit = (
        CustomerVisit.objects
        .select_for_update()
        .select_related(
            "customer",
            "billing_address",
        )
        .get(
            pk=visit.pk,
            company=company,
        )
    )

    if visit.status != CustomerVisit.VisitStatus.COMPLETED:
        raise ValidationError(
            "Only completed sales visits can be invoiced."
        )

    if SalesInvoice.objects.filter(visit=visit).exists():
        raise ValidationError(
            "An invoice already exists for this sales visit."
        )

    if not visit.billing_address:
        raise ValidationError({
            "billing_address": (
                "Please select a customer billing address "
                "before generating the invoice."
            )
        })

    seller_state = (company.state or "").strip()
    buyer_state = (visit.billing_address.state or "").strip()

    if not seller_state:
        raise ValidationError({
            "company_state": (
                "Company state is required for GST calculation."
            )
        })

    if not buyer_state:
        raise ValidationError({
            "billing_address_state": (
                "Customer billing state is required for GST calculation."
            )
        })

    if not visit.customer:
        raise ValidationError(
            "A customer is required to generate an invoice."
        )

    sale_items = list(
        visit.sale_items
        .select_related("product")
        .prefetch_related("machine_selections__machine")
        .order_by("id")
    )

    if not sale_items:
        raise ValidationError(
            "This sales visit does not contain any sale items."
        )

    intra_state = (
        seller_state.casefold() == buyer_state.casefold()
    )

    supply_type = (
        SalesInvoice.SupplyType.INTRA_STATE
        if intra_state
        else SalesInvoice.SupplyType.INTER_STATE
    )

    invoice_date = visit.visit_date
    financial_year = get_financial_year(invoice_date)

    invoice_number, sequence_number = (
        get_next_invoice_number(company, financial_year)
    )

    seller_snapshot = get_seller_snapshot(company)
    buyer_snapshot = get_buyer_snapshot(
        visit,
        visit.billing_address,
    )

    invoice = SalesInvoice.objects.create(
        company=company,
        visit=visit,
        invoice_number=invoice_number,
        financial_year=financial_year,
        sequence_number=sequence_number,
        invoice_date=invoice_date,
        supply_type=supply_type,
        place_of_supply_state=buyer_state,
        seller_snapshot=seller_snapshot,
        buyer_snapshot=buyer_snapshot,
        created_by=user,
    )

    total_taxable_value = ZERO
    total_cgst = ZERO
    total_sgst = ZERO
    total_igst = ZERO
    total_discount = ZERO
    grand_total = ZERO

    invoice_items = []

    for sale_item in sale_items:
        product = sale_item.product

        taxable_value = money(sale_item.taxable_amount)
        discount_amount = money(sale_item.discount_amount)
        unit_price = money(sale_item.unit_price)
        gst_rate = Decimal(sale_item.gst_rate)

        if taxable_value < ZERO:
            raise ValidationError(
                f"Invalid taxable value for {product.name}."
            )

        tax = calculate_gst(
            taxable_value=taxable_value,
            gst_rate=gst_rate,
            intra_state=intra_state,
        )

        line_total = money(
            taxable_value + tax["total_tax"]
        )

        serial_numbers = list(
            sale_item.machine_selections
            .select_related("machine")
            .order_by("machine__serial_number")
            .values_list(
                "machine__serial_number",
                flat=True,
            )
        )

        if len(serial_numbers) != sale_item.quantity:
            raise ValidationError(
                f"Machine serial number count does not match "
                f"the quantity for {product.name}."
            )

        invoice_items.append(
            SalesInvoiceItem(
                invoice=invoice,
                sale_item=sale_item,
                product_name=product.name,
                brand=product.brand,
                model_number=product.model_number,
                sku=product.sku,
                hsn_code=product.hsn_code,
                serial_numbers=serial_numbers,
                quantity=sale_item.quantity,
                unit_price=unit_price,
                discount_amount=discount_amount,
                taxable_value=taxable_value,
                gst_rate=gst_rate,
                cgst_rate=tax["cgst_rate"],
                cgst_amount=tax["cgst_amount"],
                sgst_rate=tax["sgst_rate"],
                sgst_amount=tax["sgst_amount"],
                igst_rate=tax["igst_rate"],
                igst_amount=tax["igst_amount"],
                total_amount=line_total,
            )
        )

        total_taxable_value += taxable_value
        total_discount += discount_amount
        total_cgst += tax["cgst_amount"]
        total_sgst += tax["sgst_amount"]
        total_igst += tax["igst_amount"]
        grand_total += line_total

    SalesInvoiceItem.objects.bulk_create(invoice_items)

    invoice.total_taxable_value = money(total_taxable_value)
    invoice.total_discount = money(total_discount)
    invoice.total_cgst = money(total_cgst)
    invoice.total_sgst = money(total_sgst)
    invoice.total_igst = money(total_igst)
    invoice.grand_total = money(grand_total)

    invoice.save(
        update_fields=[
            "total_taxable_value",
            "total_discount",
            "total_cgst",
            "total_sgst",
            "total_igst",
            "grand_total",
            "updated_at",
        ]
    )

    return invoice
