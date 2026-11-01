
$(document).ready(function () {

    const API_BASE_URL = "/api/customers/";
    const CUSTOMER_URL = API_BASE_URL + CUSTOMER_ID + "/";

    let customerData = null;
    let addressModal = new bootstrap.Modal(
        document.getElementById("addressModal")
    );

    // Display messages
    function showMessage(message, type = "success") {
        $("#messageBox").html(`
            <div class="alert alert-${type} alert-dismissible fade show">
                ${message}
                <button type="button" class="btn-close"
                        data-bs-dismiss="alert"></button>
            </div>
        `);
    }


    // Load customer details
    function loadCustomerDetails() {

        $.ajax({
            url: CUSTOMER_URL,
            type: "GET",

            success: function (response) {

                customerData = response;

                $("#customerCode").val(response.customer_code);
                $("#customerType").val(response.customer_type);
                $("#businessName").val(response.business_name || "");
                $("#contactPerson").val(response.contact_person);
                $("#mobileNumber").val(response.mobile_number);
                $("#alternateMobile").val(response.alternate_mobile || "");
                $("#email").val(response.email || "");
                $("#gstNumber").val(response.gst_number || "");
                $("#panNumber").val(response.pan_number || "");
                $("#notes").val(response.notes || "");

                toggleBusinessName();

                renderAddresses(response.addresses || []);
            },

            error: function () {
                showMessage("Unable to load customer details.", "danger");
            }
        });
    }


    // Show business name only for business customers
    function toggleBusinessName() {

        if ($("#customerType").val() === "BUSINESS") {
            $("#businessNameGroup").show();
        } else {
            $("#businessNameGroup").hide();
        }
    }


    // Enable or disable customer fields
    function setEditMode(enabled) {

        $("#customerType, #businessName, #contactPerson, " +
          "#mobileNumber, #alternateMobile, #email, " +
          "#gstNumber, #panNumber, #notes")
            .prop("disabled", !enabled);

        $("#editButtons").toggle(enabled);
        $("#editCustomerBtn").toggle(!enabled);
    }


    $("#editCustomerBtn").on("click", function () {
        setEditMode(true);
    });


    $("#cancelEditBtn").on("click", function () {
        setEditMode(false);
        loadCustomerDetails();
    });


    $("#customerType").on("change", toggleBusinessName);


    // Update customer
    $("#customerDetailForm").on("submit", function (event) {

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
            notes: $("#notes").val().trim()
        };

        // Remove empty optional values
        [
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

        if (!payload.business_name) {
            delete payload.business_name;
        }

        $("#updateCustomerBtn")
            .prop("disabled", true)
            .text("Updating...");

        $.ajax({
            url: CUSTOMER_URL,
            type: "PATCH",
            contentType: "application/json",
            data: JSON.stringify(payload),

            success: function () {

                showMessage("Customer details updated successfully.");

                setEditMode(false);
                loadCustomerDetails();
            },

            error: function (xhr) {

                const errors = xhr.responseJSON
                    ? JSON.stringify(xhr.responseJSON)
                    : "Unable to update customer.";

                showMessage(errors, "danger");
            },

            complete: function () {
                $("#updateCustomerBtn")
                    .prop("disabled", false)
                    .text("Save Changes");
            }
        });
    });


    // Render address cards
    function renderAddresses(addresses) {

        $("#addressContainer").empty();

        if (!addresses.length) {
            $("#addressContainer").html(`
                <div class="col-12 text-center text-muted">
                    No addresses available.
                </div>
            `);
            return;
        }

        addresses.forEach(function (address) {

            const defaultBadge = address.is_default
                ? '<span class="badge bg-success">Default</span>'
                : "";

            const card = $(`
                <div class="col-md-6 mb-3">
                    <div class="card border h-100">
                        <div class="card-body">

                            <div class="d-flex justify-content-between mb-2">
                                <h6 class="mb-0 address-heading"></h6>
                                ${defaultBadge}
                            </div>

                            <div class="address-details"></div>

                            <div class="mt-3">
                                <button class="btn btn-sm btn-outline-primary edit-address">
                                    Edit
                                </button>

                                <button class="btn btn-sm btn-outline-danger delete-address">
                                    Delete
                                </button>
                            </div>

                        </div>
                    </div>
                </div>
            `);

            card.find(".address-heading").text(address.address_type);

            const details = [
                address.address_line_1,
                address.address_line_2,
                address.city,
                address.district,
                address.state,
                address.pincode,
                address.country
            ].filter(Boolean).join(", ");

            card.find(".address-details").text(details);

            card.find(".edit-address").on("click", function () {
                openAddressModal(address);
            });

            card.find(".delete-address").on("click", function () {
                deleteAddress(address.id);
            });

            $("#addressContainer").append(card);
        });
    }


    // Open address modal
    function openAddressModal(address = null) {

        $("#addressForm")[0].reset();

        $("#addressId").val("");

        if (address) {

            $("#addressModalTitle").text("Edit Address");

            $("#addressId").val(address.id);
            $("#addressType").val(address.address_type);
            $("#addressLine1").val(address.address_line_1);
            $("#addressLine2").val(address.address_line_2 || "");
            $("#city").val(address.city);
            $("#district").val(address.district || "");
            $("#state").val(address.state);
            $("#pincode").val(address.pincode);
            $("#country").val(address.country);
            $("#isDefault").prop("checked", address.is_default);

        } else {

            $("#addressModalTitle").text("Add Address");
            $("#country").val("India");

        }

        addressModal.show();
    }


    // Add address button
    $("#addAddressBtn").on("click", function () {
        openAddressModal();
    });


    // Save or update address
    $("#addressForm").on("submit", function (event) {

        event.preventDefault();

        const addressId = $("#addressId").val();

        const newAddress = {
            address_type: $("#addressType").val(),
            address_line_1: $("#addressLine1").val().trim(),
            address_line_2: $("#addressLine2").val().trim(),
            city: $("#city").val().trim(),
            district: $("#district").val().trim(),
            state: $("#state").val().trim(),
            pincode: $("#pincode").val().trim(),
            country: $("#country").val().trim() || "India",
            is_default: $("#isDefault").is(":checked")
        };

        // Keep existing address IDs when updating.
        let addresses = (customerData.addresses || []).map(function (item) {
            return {...item};
        });

        if (addressId) {

            addresses = addresses.map(function (item) {
                if (String(item.id) === String(addressId)) {
                    return {
                        ...item,
                        ...newAddress
                    };
                }
                return item;
            });

        } else {

            addresses.push(newAddress);

        }

        // Ensure only one default address.
        if (newAddress.is_default) {
            addresses = addresses.map(function (item) {
                if (addressId && String(item.id) === String(addressId)) {
                    return {...item, is_default: true};
                }

                if (!addressId && item === newAddress) {
                    return item;
                }

                return {...item, is_default: false};
            });
        }

        $("#saveAddressBtn")
            .prop("disabled", true)
            .text("Saving...");

        $.ajax({
            url: CUSTOMER_URL,
            type: "PATCH",
            contentType: "application/json",
            data: JSON.stringify({
                addresses: addresses
            }),

            success: function () {

                showMessage(
                    addressId
                        ? "Address updated successfully."
                        : "Address added successfully."
                );

                addressModal.hide();
                loadCustomerDetails();
            },

            error: function (xhr) {

                const errors = xhr.responseJSON
                    ? JSON.stringify(xhr.responseJSON)
                    : "Unable to save address.";

                showMessage(errors, "danger");
            },

            complete: function () {
                $("#saveAddressBtn")
                    .prop("disabled", false)
                    .text("Save Address");
            }
        });
    });


    // Delete address
    function deleteAddress(addressId) {

        if (!confirm("Are you sure you want to delete this address?")) {
            return;
        }

        const addresses = (customerData.addresses || [])
            .filter(function (address) {
                return String(address.id) !== String(addressId);
            });

        $.ajax({
            url: CUSTOMER_URL,
            type: "PATCH",
            contentType: "application/json",
            data: JSON.stringify({
                addresses: addresses
            }),

            success: function () {
                showMessage("Address deleted successfully.");
                loadCustomerDetails();
            },

            error: function (xhr) {

                const errors = xhr.responseJSON
                    ? JSON.stringify(xhr.responseJSON)
                    : "Unable to delete address.";

                showMessage(errors, "danger");
            }
        });
    }


    // Initial load
    loadCustomerDetails();

});
