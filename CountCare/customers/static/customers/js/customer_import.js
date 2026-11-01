
$(document).ready(function () {

    const API_BASE_URL = "/api/customer-imports/";

    let currentBatchId = null;


    // ==========================================
    // Display Messages
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

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
    }


    // ==========================================
    // Upload and Preview File
    // ==========================================

    $("#importForm").on("submit", function (event) {

        event.preventDefault();

        const fileInput = $("#importFile")[0];

        if (!fileInput.files.length) {
            showMessage("Please select a file.", "warning");
            return;
        }

        const file = fileInput.files[0];

        const allowedExtensions = [".xlsx", ".csv"];

        const extension = "." + file.name.split(".").pop().toLowerCase();

        if (!allowedExtensions.includes(extension)) {
            showMessage("Only XLSX and CSV files are supported.", "danger");
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            showMessage("File size cannot exceed 5 MB.", "danger");
            return;
        }

        const formData = new FormData();

        formData.append("file", file);

        $("#previewBtn")
            .prop("disabled", true)
            .text("Uploading and Validating...");

        $("#previewSection").hide();
        $("#summarySection").hide();
        $("#resultSection").hide();

        $.ajax({

            url: API_BASE_URL + "preview/",

            type: "POST",

            data: formData,

            processData: false,

            contentType: false,

            success: function (response) {

                currentBatchId = response.batch.batch_id;

                $("#totalRows").text(response.batch.total_rows);
                $("#validRows").text(response.valid_rows);
                $("#invalidRows").text(response.invalid_rows);

                $("#summarySection").show();

                // Render rows before displaying the preview section.
                renderPreview(response.rows);

                $("#previewSection").show();

                // Enable confirmation only if valid records exist.
                $("#confirmImportBtn")
                    .prop("disabled", response.valid_rows === 0)
                    .text("Confirm Import");

                showMessage(
                    "File validated successfully. Please review the records."
                );

            },

            error: function (xhr) {

                const message =
                    xhr.responseJSON?.detail ||
                    "Unable to process the uploaded file.";

                showMessage(message, "danger");

            },

            complete: function () {

                $("#previewBtn")
                    .prop("disabled", false)
                    .text("Upload and Preview");

            }

        });

    });


    // ==========================================
    // Render Preview
    // ==========================================

    function formatErrors(errors) {

        if (!errors) {
            return "-";
        }

        // Serializer errors are usually returned as an object.
        if (typeof errors === "object" && !Array.isArray(errors)) {

            return Object.entries(errors)
                .map(function ([field, messages]) {

                    if (Array.isArray(messages)) {
                        messages = messages.join(", ");
                    }

                    return field + ": " + formatErrors(messages);

                })
                .join(" | ");
        }

        if (Array.isArray(errors)) {

            return errors.map(function (error) {
                return formatErrors(error);
            }).join(", ");
        }

        return String(errors);
    }


    function renderPreview(rows) {

        $("#previewTableBody").empty();

        rows.forEach(function (row) {

            const data = row.data || {};

            const address =
                data.addresses && data.addresses.length
                    ? data.addresses[0]
                    : {};

            const customerName =
                data.customer_type === "BUSINESS"
                    ? data.business_name
                    : data.contact_person;

            const tr = $("<tr>");

            tr.append($("<td>").text(row.row_number));

            tr.append($("<td>").text(customerName || ""));

            tr.append($("<td>").text(data.mobile_number || ""));

            tr.append($("<td>").text(address.city || ""));

            // Status badge
            const statusBadge = $("<span>")
                .addClass(
                    row.status === "VALID"
                        ? "badge bg-success"
                        : "badge bg-danger"
                )
                .text(row.status);

            tr.append(
                $("<td>").append(statusBadge)
            );

            // Validation errors
            const errorText = formatErrors(row.errors);

            tr.append(
                $("<td>")
                    .addClass("text-danger")
                    .text(errorText)
            );

            $("#previewTableBody").append(tr);

        });

    }

    // ==========================================
    // Confirm Import
    // ==========================================

    $("#confirmImportBtn").on("click", function () {

        if (!currentBatchId) {
            showMessage("Please upload a file first.", "warning");
            return;
        }

        if (!confirm(
            "Are you sure you want to import all valid customer records?"
        )) {
            return;
        }

        $("#confirmImportBtn")
            .prop("disabled", true)
            .text("Importing...");

        $.ajax({

            url: API_BASE_URL + currentBatchId + "/confirm/",

            type: "POST",

            success: function (response) {

                const batch = response.batch;

                $("#resultTotal").text(batch.total_rows);

                $("#resultSuccess").text(batch.successful_rows);

                $("#resultFailed").text(batch.failed_rows);

                $("#resultSection").show();

                $("#confirmImportBtn")
                    .prop("disabled", true)
                    .text("Import Completed");

                showMessage(
                    "Customer import completed successfully."
                );

            },

            error: function (xhr) {

                const message =
                    xhr.responseJSON?.detail ||
                    "Unable to import customer records.";

                showMessage(message, "danger");

                $("#confirmImportBtn")
                    .prop("disabled", false)
                    .text("Confirm Import");

            }

        });

    });

});
