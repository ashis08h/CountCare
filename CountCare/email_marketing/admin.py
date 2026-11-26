
from django.contrib import admin

from .models import (
    EmailCampaign,
    EmailCampaignRecipient,
    EmailCampaignRun,
    EmailDeliveryLog,
)


class EmailCampaignRecipientInline(admin.TabularInline):
    model = EmailCampaignRecipient
    extra = 0
    readonly_fields = ("added_at",)


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "frequency",
        "status",
        "is_active",
        "next_run_at",
        "created_at",
    )
    list_filter = ("status", "frequency", "is_active")
    search_fields = ("name", "subject", "company__name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_run_at",
        "next_run_at",
    )
    inlines = [EmailCampaignRecipientInline]


@admin.register(EmailCampaignRun)
class EmailCampaignRunAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "scheduled_for",
        "status",
        "total_recipients",
        "sent_count",
        "failed_count",
    )
    list_filter = ("status",)
    readonly_fields = (
        "created_at",
        "started_at",
        "finished_at",
    )


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(admin.ModelAdmin):
    list_display = (
        "email_address",
        "status",
        "attempt_count",
        "sent_at",
        "campaign_run",
    )
    list_filter = ("status",)
    search_fields = ("email_address", "provider_message_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmailCampaignRecipient)
class EmailCampaignRecipientAdmin(admin.ModelAdmin):
    list_display = (
        "customer_name",
        "email_address",
        "campaign",
        "is_unsubscribed",
    )
    list_filter = ("is_unsubscribed",)
    search_fields = ("customer_name", "email_address")
