
$(document).ready(function () {

    const API_BASE_URL = "/api/";

    let currentPage = 1;
    let nextPageUrl = null;
    let previousPageUrl = null;
    let searchTimer = null;


    // ==========================================
    // Show Messages
    // ==========================================

    function showMessage(message, type = "success") {

        $("#messageBox").empty();

        const alert = $("<div>")
            .addClass(`alert alert-${type} alert-dismissible fade show`)
            .append($("<span>").text(message))
            .append(`
                <button type="button"
                        class="btn-close"
                        data-bs-dismiss="alert">
                </button>
            `);

        $("#messageBox").append(alert);
    }


    // ==========================================
    // Customer Type Handling
    // ==========================================

    function toggleBusinessName() {

        const customerType = $("#customerType").val();

        if (customerType === "BUSINESS") {

            $("#businessNameGroup").show();
            $("#businessName").prop("required", true);

        } else {

            $("#businessNameGroup").hide();

            $("#businessName")
                .prop("required", false)
                .val("");
        }
    }

    $("#customerType").on("change", toggleBusinessName);

    toggleBusinessName();


    // ==========================================
    // Load Customers
    // ==========================================

    function loadCustomers(url = null) {

        const requestUrl = url || (
            API_BASE_URL + "customers/?page=" + currentPage
        );

        const searchValue = $("#searchCustomer").val().trim();

        $("#customerTableBody").html(`
            <tr>
                <td colspan="7" class="text-center">
                    Loading customers...
                </td>
            </tr>
        `);

        $.ajax({

            url: requestUrl,
            type: "GET",

            data: {
                search: searchValue,
                customer_type: $("#customerTypeFilter").val() || "",
                status: $("#customerStatusFilter").val() || ""
            },

            success: function (response) {

                $("#customerTableBody").empty();

                nextPageUrl = response.next;
                previousPageUrl = response.previous;

                const customers = response.results || [];

                if (customers.length === 0) {

                    $("#customerTableBody").html(`
                        <tr>
                            <td colspan="7" class="text-center">
                                No customers found.
                            </td>
                        </tr>
                    `);

                }

                customers.forEach(function (customer) {

                    const customerName =
                        customer.customer_type === "BUSINESS"
                            ? customer.business_name
                            : customer.contact_person;


                    // Customer status
                    const statusClass =
                        customer.status === "ACTIVE"
                            ? "status-active"
                            : "status-inactive";


                    // View Button
                    const profileButton = $("<a>")
                        .attr(
                            "href",
                            `/api/customer-management/${customer.id}/`
                        )
                        .addClass("btn btn-sm btn-primary me-2")
                        .text("View");


                    // Activate / Deactivate Button
                    let actionButton;

                    if (customer.status === "ACTIVE") {

                        actionButton = $("<button>")
                            .attr("type", "button")
                            .addClass("btn btn-sm btn-danger deactivate-btn")
                            .attr("data-id", customer.id)
                            .text("Deactivate");

                    } else {

                        actionButton = $("<button>")
                            .attr("type", "button")
                            .addClass("btn btn-sm btn-success activate-btn")
                            .attr("data-id", customer.id)
                            .text("Activate");
                    }


                    // Build Table Row
                    const row = $("<tr>");

                    row.append(
                        $("<td>").text(customer.customer_code)
                    );

                    row.append(
                        $("<td>").text(customerName || "")
                    );

                    row.append(
                        $("<td>").text(customer.customer_type)
                    );

                    row.append(
                        $("<td>").text(customer.mobile_number)
                    );

                    row.append(
                        $("<td>").text(customer.email || "")
                    );

                    row.append(
                        $("<td>")
                            .append(
                                $("<span>")
                                    .addClass(statusClass)
                                    .text(customer.status)
                            )
                    );


                    // Action Column
                    const actionCell = $("<td>");

                    actionCell.append(profileButton);
                    actionCell.append(actionButton);

                    row.append(actionCell);

                    $("#customerTableBody").append(row);

                });


                // Pagination Information
                $("#paginationInfo").text(
                    "Total customers: " + response.count
                );

                $("#previousPage").prop(
                    "disabled",
                    !previousPageUrl
                );

                $("#nextPage").prop(
                    "disabled",
                    !nextPageUrl
                );

            },

            error: function (xhr) {

                $("#customerTableBody").html(`
                    <tr>
                        <td colspan="7" class="text-center text-danger">
                            Unable to load customers.
                        </td>
                    </tr>
                `);

                showMessage(
                    xhr.responseJSON?.detail || "Unable to load customers.",
                    "danger"
                );
            }

        });

    }


    // ==========================================
    // Register Customer
    // ==========================================

    $("#customerForm").on("submit", function (event) {

        event.preventDefault();

        const payload = {

            customer_type: $("#customerType").val(),

            business_name: $("#businessName").val().trim(),

            contact_person: $("#contactPerson").val().trim(),

            mobile_number: $("#mobileNumber").val().trim(),

            alternate_mobile: $("#alternateMobile").val().trim(),

            email: $("#email").val().trim(),

            gst_number: $("#gstNumber").val().trim(),

            pan_number: $("#panNumber").val().trim(),

            notes: $("#notes").val().trim(),

            addresses: [
                {
                    address_type: "BILLING",

                    address_line_1: $("#addressLine1").val().trim(),

                    address_line_2: $("#addressLine2").val().trim(),

                    city: $("#city").val().trim(),

                    district: $("#district").val().trim(),

                    state: $("#state").val().trim(),

                    pincode: $("#pincode").val().trim(),

                    country: "India",

                    is_default: true
                }
            ]
        };


        // Remove empty optional fields
        [
            "business_name",
            "alternate_mobile",
            "email",
            "gst_number",
            "pan_number",
            "notes"
        ].forEach(function (field) {

            if (!payload[field]) {
                delete payload[field];
            }

        });


        if (!payload.addresses[0].address_line_2) {
            delete payload.addresses[0].address_line_2;
        }

        if (!payload.addresses[0].district) {
            delete payload.addresses[0].district;
        }


        $("#saveCustomerBtn")
            .prop("disabled", true)
            .text("Saving...");


        $.ajax({

            url: API_BASE_URL + "customers/create/",

            type: "POST",

            contentType: "application/json",

            data: JSON.stringify(payload),

            success: function (response) {

                showMessage(
                    "Customer registered successfully. Customer Code: " +
                    response.customer_code
                );

                $("#customerForm")[0].reset();

                toggleBusinessName();

                bootstrap.Collapse
                    .getOrCreateInstance(
                        document.getElementById("customerFormSection")
                    )
                    .hide();

                currentPage = 1;

                loadCustomers();

            },

            error: function (xhr) {

                let errorMessage = "Unable to register customer.";

                if (xhr.responseJSON) {

                    errorMessage = Object.entries(xhr.responseJSON)
                        .map(function ([field, errors]) {

                            const messages = Array.isArray(errors)
                                ? errors.join(", ")
                                : JSON.stringify(errors);

                            return field + ": " + messages;

                        })
                        .join(" | ");
                }

                showMessage(errorMessage, "danger");

            },

            complete: function () {

                $("#saveCustomerBtn")
                    .prop("disabled", false)
                    .text("Save Customer");

            }

        });

    });


    // ==========================================
    // Search Customers
    // ==========================================

    $("#searchCustomer").on("input", function () {

        clearTimeout(searchTimer);

        searchTimer = setTimeout(function () {

            currentPage = 1;

            loadCustomers();

        }, 400);

    });


    // ==========================================
    // Previous Page
    // ==========================================

    $("#previousPage").on("click", function () {

        if (previousPageUrl) {

            loadCustomers(previousPageUrl);

        }

    });


    // ==========================================
    // Next Page
    // ==========================================

    $("#nextPage").on("click", function () {

        if (nextPageUrl) {

            loadCustomers(nextPageUrl);

        }

    });


    // ==========================================
    // Deactivate Customer
    // ==========================================

    $(document).on("click", ".deactivate-btn", function () {

        const customerId = $(this).data("id");

        if (!confirm("Are you sure you want to deactivate this customer?")) {
            return;
        }

        $.ajax({

            url: API_BASE_URL +
                "customers/" + customerId + "/deactivate/",

            type: "POST",

            success: function () {

                showMessage("Customer deactivated successfully.");

                loadCustomers();

            },

            error: function (xhr) {

                showMessage(
                    xhr.responseJSON?.detail ||
                    "Unable to deactivate customer.",
                    "danger"
                );

            }

        });

    });


    // ==========================================
    // Activate Customer
    // ==========================================

    $(document).on("click", ".activate-btn", function () {

        const customerId = $(this).data("id");

        $.ajax({

            url: API_BASE_URL +
                "customers/" + customerId + "/activate/",

            type: "POST",

            success: function () {

                showMessage("Customer activated successfully.");

                loadCustomers();

            },

            error: function (xhr) {

                showMessage(
                    xhr.responseJSON?.detail ||
                    "Unable to activate customer.",
                    "danger"
                );

            }

        });

    });


    // ==========================================
    // Customer Type Filter
    // ==========================================

    $("#customerTypeFilter").on("change", function () {

        currentPage = 1;

        loadCustomers();

    });


    // ==========================================
    // Customer Status Filter
    // ==========================================

    $("#customerStatusFilter").on("change", function () {

        currentPage = 1;

        loadCustomers();

    });


    // ==========================================
    // Customer Export
    // ==========================================

    function exportCustomers(format) {

        const params = new URLSearchParams({

            format: format,

            search: $("#searchCustomer").val().trim(),

            customer_type: $("#customerTypeFilter").val() || "",

            status: $("#customerStatusFilter").val() || ""

        });

        const exportUrl =
            API_BASE_URL + "customers/export/?" + params.toString();

        window.location.href = exportUrl;

    }


    // ==========================================
    // Export Excel
    // ==========================================

    $("#exportExcel").on("click", function (event) {

        event.preventDefault();

        exportCustomers("xlsx");

    });


    // ==========================================
    // Export CSV
    // ==========================================

    $("#exportCSV").on("click", function (event) {

        event.preventDefault();

        exportCustomers("csv");

    });


    // ==========================================
    // Initial Page Load
    // ==========================================

    loadCustomers();

});
