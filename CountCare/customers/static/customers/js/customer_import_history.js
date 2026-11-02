
$(document).ready(function () {

    const API_BASE_URL = "/api/customer-imports/";

    let nextPageUrl = null;
    let previousPageUrl = null;
    let currentBatchId = null;
    let searchTimer = null;


    // ==========================================
    // Messages
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
    // Status Badge
    // ==========================================

    function getStatusBadge(status) {

        const colors = {
            PENDING: "warning",
            PROCESSING: "info",
            COMPLETED: "success",
            FAILED: "danger"
        };

        return $("<span>")
            .addClass("badge")
            .addClass("bg-" + (colors[status] || "secondary"))
            .text(status);
    }


    // ==========================================
    // Load Import History
    // ==========================================

    function loadHistory(url = null) {

        const requestUrl = url || (
            API_BASE_URL + "history/"
        );

        const search = $("#searchBatch").val().trim();
        const status = $("#statusFilter").val();

        $("#historyTableBody").html(`
            <tr>
                <td colspan="9" class="text-center">
                    Loading...
                </td>
            </tr>
        `);

        $.ajax({

            url: requestUrl,

            type: "GET",

            data: {
                search: search,
                status: status
            },

            success: function (response) {

                $("#historyTableBody").empty();

                nextPageUrl = response.next;
                previousPageUrl = response.previous;

                const batches = response.results || [];

                if (batches.length === 0) {

                    $("#historyTableBody").html(`
                        <tr>
                            <td colspan="9" class="text-center">
                                No import history found.
                            </td>
                        </tr>
                    `);

                }

                batches.forEach(function (batch) {

                    const row = $("<tr>");

                    row.append(
                        $("<td>").text(batch.id)
                    );

                    row.append(
                        $("<td>").text(batch.file_name)
                    );

                    row.append(
                        $("<td>").text(
                            (batch.file_type || "").toUpperCase()
                        )
                    );

                    row.append(
                        $("<td>").text(batch.total_rows)
                    );

                    row.append(
                        $("<td>")
                            .addClass("text-success fw-bold")
                            .text(batch.successful_rows)
                    );

                    row.append(
                        $("<td>")
                            .addClass("text-danger fw-bold")
                            .text(batch.failed_rows)
                    );

                    row.append(
                        $("<td>").append(
                            getStatusBadge(batch.status)
                        )
                    );

                    row.append(
                        $("<td>").text(
                            batch.created_at
                                ? new Date(batch.created_at).toLocaleString()
                                : "-"
                        )
                    );

                    const viewButton = $("<button>")
                        .attr("type", "button")
                        .addClass("btn btn-sm btn-primary view-batch-btn")
                        .attr("data-id", batch.id)
                        .text("View");

                    row.append(
                        $("<td>").append(viewButton)
                    );

                    $("#historyTableBody").append(row);

                });

                $("#paginationInfo").text(
                    "Total import batches: " + response.count
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

                $("#historyTableBody").html(`
                    <tr>
                        <td colspan="9" class="text-center text-danger">
                            Unable to load import history.
                        </td>
                    </tr>
                `);

                showMessage(
                    xhr.responseJSON?.detail ||
                    "Unable to load import history.",
                    "danger"
                );

            }

        });

    }


    // ==========================================
    // Format Validation Errors
    // ==========================================

    function formatErrors(errors) {

        if (!errors) {
            return "-";
        }

        if (Array.isArray(errors)) {

            return errors.map(function (error) {
                return formatErrors(error);
            }).join(" | ");

        }

        if (typeof errors === "object") {

            return Object.entries(errors)
                .map(function ([field, messages]) {

                    return field + ": " + formatErrors(messages);

                })
                .join(" | ");

        }

        return String(errors);

    }


    // ==========================================
    // Load Batch Details
    // ==========================================

    function loadBatchDetails(batchId) {

        currentBatchId = batchId;

        $("#batchDetailSection").show();

        $("#batchDetailTableBody").html(`
            <tr>
                <td colspan="5" class="text-center">
                    Loading batch details...
                </td>
            </tr>
        `);

        $.ajax({

            url: API_BASE_URL + "history/" + batchId + "/",

            type: "GET",

            success: function (response) {

                const batch = response.batch;

                const summary = $("<div>")
                    .addClass("row g-3");

                const items = [
                    ["File Name", batch.file_name],
                    ["Total Rows", batch.total_rows],
                    ["Successful Rows", batch.successful_rows],
                    ["Failed Rows", batch.failed_rows],
                    ["Status", batch.status],
                    ["Uploaded By", batch.uploaded_by || "Unknown"]
                ];

                items.forEach(function (item) {

                    const col = $("<div>")
                        .addClass("col-md-4");

                    const card = $("<div>")
                        .addClass("border rounded p-3 h-100");

                    card.append(
                        $("<small>")
                            .addClass("text-muted d-block")
                            .text(item[0])
                    );

                    card.append(
                        $("<strong>").text(item[1])
                    );

                    col.append(card);

                    summary.append(col);

                });

                $("#batchSummary").empty().append(summary);

                $("#batchDetailTableBody").empty();

                const rows = response.rows || [];

                if (rows.length === 0) {

                    $("#batchDetailTableBody").html(`
                        <tr>
                            <td colspan="5" class="text-center">
                                No rows found.
                            </td>
                        </tr>
                    `);

                }

                rows.forEach(function (row) {

                    const data = row.data || {};

                    const addresses = data.addresses || [];

                    const address = addresses.length
                        ? addresses[0]
                        : {};

                    const customerName =
                        data.customer_type === "BUSINESS"
                            ? data.business_name
                            : data.contact_person;

                    const tr = $("<tr>");

                    tr.append(
                        $("<td>").text(row.row_number)
                    );

                    tr.append(
                        $("<td>").text(customerName || "-")
                    );

                    tr.append(
                        $("<td>").text(data.mobile_number || "-")
                    );

                    const statusCell = $("<td>").append(
                        getStatusBadge(row.status)
                    );

                    tr.append(statusCell);

                    tr.append(
                        $("<td>")
                            .addClass("text-danger")
                            .text(formatErrors(row.errors))
                    );

                    $("#batchDetailTableBody").append(tr);

                });

                $("#batchDetailSection")[0].scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

            },

            error: function () {

                showMessage(
                    "Unable to load batch details.",
                    "danger"
                );

            }

        });

    }


    // ==========================================
    // View Batch
    // ==========================================

    $(document).on("click", ".view-batch-btn", function () {

        const batchId = $(this).data("id");

        loadBatchDetails(batchId);

    });


    // ==========================================
    // Close Batch Details
    // ==========================================

    $("#closeBatchDetails").on("click", function () {

        $("#batchDetailSection").hide();

        currentBatchId = null;

    });


    // ==========================================
    // Download Failed Excel Report
    // ==========================================

    $("#downloadFailedReport").on("click", function () {

        if (!currentBatchId) {
            return;
        }

        window.location.href =
            API_BASE_URL +
            "history/" +
            currentBatchId +
            "/failed-report/";

    });


    // ==========================================
    // Download Original CSV
    // ==========================================

    $("#downloadOriginalData").on("click", function () {

        if (!currentBatchId) {
            return;
        }

        window.location.href =
            API_BASE_URL +
            "history/" +
            currentBatchId +
            "/original-data/";

    });


    // ==========================================
    // Search
    // ==========================================

    $("#searchBatch").on("input", function () {

        clearTimeout(searchTimer);

        searchTimer = setTimeout(function () {

            loadHistory();

        }, 400);

    });


    // ==========================================
    // Status Filter
    // ==========================================

    $("#statusFilter").on("change", function () {

        loadHistory();

    });


    // ==========================================
    // Reset Filters
    // ==========================================

    $("#resetFilters").on("click", function () {

        $("#searchBatch").val("");

        $("#statusFilter").val("");

        loadHistory();

    });


    // ==========================================
    // Pagination
    // ==========================================

    $("#previousPage").on("click", function () {

        if (previousPageUrl) {
            loadHistory(previousPageUrl);
        }

    });


    $("#nextPage").on("click", function () {

        if (nextPageUrl) {
            loadHistory(nextPageUrl);
        }

    });


    // ==========================================
    // Initial Load
    // ==========================================

    loadHistory();

});
