
import csv
import io
import math

from openpyxl import load_workbook


MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_ROWS = 5000

ALLOWED_EXTENSIONS = [".xlsx", ".csv"]


# Excel/CSV headers mapped to our API fields
HEADER_MAPPING = {
    "customer_type": "customer_type",
    "business_name": "business_name",
    "contact_person": "contact_person",
    "mobile_number": "mobile_number",
    "alternate_mobile": "alternate_mobile",
    "email": "email",
    "gst_number": "gst_number",
    "pan_number": "pan_number",
    "notes": "notes",

    "address_type": "address_type",
    "address_line_1": "address_line_1",
    "address_line_2": "address_line_2",
    "city": "city",
    "district": "district",
    "state": "state",

    # Support both Excel header formats
    "pin_code": "pincode",
    "pincode": "pincode",

    "country": "country",
}


def normalize_cell(value):

    if value is None:
        return ""

    if isinstance(value, float) and math.isfinite(value):
        if value.is_integer():
            return str(int(value))

    return str(value).strip()


def normalize_header(value):

    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def read_csv_file(uploaded_file):

    content = uploaded_file.read()

    text = content.decode("utf-8-sig")

    sample = text[:4096]

    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)

    return list(reader)


def read_excel_file(uploaded_file):

    workbook = load_workbook(
        uploaded_file,
        read_only=True,
        data_only=True
    )

    worksheet = workbook.active

    rows = list(worksheet.iter_rows(values_only=True))

    workbook.close()

    return rows


def parse_uploaded_file(uploaded_file):

    file_name = uploaded_file.name.lower()

    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValueError("File size cannot exceed 5 MB.")

    if file_name.endswith(".csv"):
        rows = read_csv_file(uploaded_file)

    elif file_name.endswith(".xlsx"):
        rows = read_excel_file(uploaded_file)

    else:
        raise ValueError(
            "Unsupported file format. Upload only XLSX or CSV."
        )

    if not rows:
        raise ValueError("The uploaded file is empty.")

    headers = [
        normalize_header(header)
        for header in rows[0]
    ]

    if not any(headers):
        raise ValueError("The uploaded file has no column headers.")

    if len(headers) != len(set(headers)):
        raise ValueError("Duplicate column headers are not allowed.")

    mapped_headers = [
        HEADER_MAPPING.get(header)
        for header in headers
    ]

    if "contact_person" not in mapped_headers:
        raise ValueError("Contact Person column is required.")

    if "mobile_number" not in mapped_headers:
        raise ValueError("Mobile Number column is required.")

    if "address_line_1" not in mapped_headers:
        raise ValueError("Address Line 1 column is required.")

    if "city" not in mapped_headers:
        raise ValueError("City column is required.")

    if "state" not in mapped_headers:
        raise ValueError("State column is required.")

    if "pincode" not in mapped_headers:
        raise ValueError("PIN Code column is required.")

    if len(rows) - 1 > MAX_ROWS:
        raise ValueError(
            f"Maximum {MAX_ROWS} data rows are allowed."
        )

    parsed_records = []

    for row_number, row in enumerate(rows[1:], start=2):

        if not any(value not in (None, "") for value in row):
            continue

        record = {}

        for index, field in enumerate(mapped_headers):

            if field is None:
                continue

            value = row[index] if index < len(row) else None

            record[field] = normalize_cell(value)

        # Set defaults
        record["customer_type"] = (
                record.get("customer_type") or "INDIVIDUAL"
        ).upper()

        record["address_type"] = (
                record.get("address_type") or "BILLING"
        ).upper()

        record["country"] = (
                record.get("country") or "India"
        )

        record["addresses"] = [
            {
                "address_type": record.pop("address_type", "BILLING"),
                "address_line_1": record.pop("address_line_1", ""),
                "address_line_2": record.pop("address_line_2", ""),
                "city": record.pop("city", ""),
                "district": record.pop("district", ""),
                "state": record.pop("state", ""),
                "pincode": record.pop("pincode", ""),
                "country": record.pop("country", "India"),
                "is_default": True,
            }
        ]

        parsed_records.append({
            "row_number": row_number,
            "data": record
        })

    if not parsed_records:
        raise ValueError("No customer records found in the file.")

    return parsed_records
