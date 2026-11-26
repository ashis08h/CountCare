
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class EmailCampaign(models.Model):

    class Frequency(models.TextChoices):
        ONCE = "ONCE", "One time"
        DAILY = "DAILY", "Every day"
        WEEKLY = "WEEKLY", "Every week"
        MONTHLY = "MONTHLY", "Every month"
        CUSTOM = "CUSTOM", "Custom interval"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        COMPLETED = "COMPLETED", "Completed"
        DELETED = "DELETED", "Deleted"

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="email_campaigns",
    )

    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=255)
    message = models.TextField()

    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.ONCE,
    )

    # Scheduling configuration
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    send_time = models.TimeField()
    timezone = models.CharField(
        max_length=64,
        default="Asia/Kolkata",
    )

    # Weekly: weekday numbers, Monday=0 and Sunday=6.
    # Example: [0, 2, 6] means Monday, Wednesday and Sunday.
    weekdays = models.JSONField(default=list, blank=True)

    # Monthly: day of month, from 1 to 31.
    day_of_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    # Custom: repeat every N days.
    interval_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    # Used for one-time campaigns.
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=False)

    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_campaigns_created",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_campaigns_updated",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_campaigns"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "status"],
                name="email_campaign_company_status",
            ),
            models.Index(
                fields=["is_active", "next_run_at"],
                name="email_campaign_next_run",
            ),
        ]

    def __str__(self):
        return self.name


class EmailCampaignRecipient(models.Model):

    campaign = models.ForeignKey(
        EmailCampaign,
        on_delete=models.PROTECT,
        related_name="recipients",
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_campaign_recipients",
    )

    customer_name = models.CharField(
        max_length=255,
        blank=True,
    )

    email_address = models.EmailField(max_length=254)

    is_unsubscribed = models.BooleanField(default=False)

    unsubscribed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_campaign_recipients"
        ordering = ["customer_name", "email_address"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "email_address"],
                name="unique_campaign_recipient_email",
            ),
        ]
        indexes = [
            models.Index(
                fields=["campaign", "is_unsubscribed"],
                name="email_recipient_unsubscribe",
            ),
        ]

    def __str__(self):
        return self.email_address


class EmailCampaignRun(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        PARTIAL = "PARTIAL", "Partially completed"
        FAILED = "FAILED", "Failed"
        SKIPPED = "SKIPPED", "Skipped"

    campaign = models.ForeignKey(
        EmailCampaign,
        on_delete=models.PROTECT,
        related_name="runs",
    )

    scheduled_for = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_campaign_runs"
        ordering = ["-scheduled_for"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "scheduled_for"],
                name="unique_campaign_scheduled_run",
            ),
        ]
        indexes = [
            models.Index(
                fields=["campaign", "status"],
                name="email_run_campaign_status",
            ),
        ]

    def __str__(self):
        return f"{self.campaign.name} - {self.scheduled_for}"


class EmailDeliveryLog(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENDING = "SENDING", "Sending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        SKIPPED = "SKIPPED", "Skipped"

    campaign_run = models.ForeignKey(
        EmailCampaignRun,
        on_delete=models.PROTECT,
        related_name="delivery_logs",
    )

    recipient = models.ForeignKey(
        EmailCampaignRecipient,
        on_delete=models.PROTECT,
        related_name="delivery_logs",
    )

    email_address = models.EmailField(max_length=254)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    attempt_count = models.PositiveSmallIntegerField(default=0)

    provider_message_id = models.CharField(
        max_length=255,
        blank=True,
    )

    error_message = models.TextField(blank=True)

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_delivery_logs"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign_run", "recipient"],
                name="unique_delivery_per_run_recipient",
            ),
        ]
        indexes = [
            models.Index(
                fields=["campaign_run", "status"],
                name="email_delivery_run_status",
            ),
        ]

    def __str__(self):
        return f"{self.email_address} - {self.status}"
