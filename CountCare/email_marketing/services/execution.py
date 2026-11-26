from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from email_marketing.models import (
    EmailCampaign,
    EmailCampaignRun,
    EmailDeliveryLog,
)
from email_marketing.services.scheduling import calculate_next_run_at


def create_campaign_run(campaign_id):
    """
    Atomically claim one due campaign and create its run and delivery logs.
    Returns the run ID, or None if the campaign is no longer due.
    """
    now = timezone.now()

    with transaction.atomic():
        campaign = (
            EmailCampaign.objects
            .select_for_update()
            .filter(
                id=campaign_id,
                status=EmailCampaign.Status.ACTIVE,
                is_active=True,
                next_run_at__lte=now,
            )
            .first()
        )

        if campaign is None:
            return None

        scheduled_for = campaign.next_run_at

        # The unique constraint on (campaign, scheduled_for) prevents
        # duplicate runs for the same scheduled occurrence.
        run, created = EmailCampaignRun.objects.get_or_create(
            campaign=campaign,
            scheduled_for=scheduled_for,
            defaults={
                "status": EmailCampaignRun.Status.RUNNING,
                "started_at": now,
            },
        )

        if not created:
            # A run already exists for this scheduled occurrence.
            # Do not send it a second time.
            if run.status in [
                EmailCampaignRun.Status.RUNNING,
                EmailCampaignRun.Status.COMPLETED,
                EmailCampaignRun.Status.PARTIAL,
                EmailCampaignRun.Status.FAILED,
            ]:
                return None

            run.status = EmailCampaignRun.Status.RUNNING
            run.started_at = now
            run.save(update_fields=["status", "started_at"])

        recipients = campaign.recipients.filter(
            is_unsubscribed=False,
        )

        logs = []
        for recipient in recipients:
            logs.append(
                EmailDeliveryLog(
                    campaign_run=run,
                    recipient=recipient,
                    email_address=recipient.email_address,
                    status=EmailDeliveryLog.Status.PENDING,
                )
            )

        EmailDeliveryLog.objects.bulk_create(
            logs,
            ignore_conflicts=True,
        )

        run.total_recipients = recipients.count()
        run.save(update_fields=["total_recipients"])

        # Advance the campaign schedule immediately after claiming the run.
        # This prevents another scheduler process from claiming the same
        # occurrence while the current process sends its emails.
        campaign.last_run_at = now

        if campaign.frequency == EmailCampaign.Frequency.ONCE:
            campaign.status = EmailCampaign.Status.COMPLETED
            campaign.is_active = False
            campaign.next_run_at = None
        else:
            try:
                campaign.next_run_at = calculate_next_run_at(
                    campaign,
                    after=now,
                )
            except ValueError as exc:
                campaign.next_run_at = None
                campaign.status = EmailCampaign.Status.PAUSED
                campaign.is_active = False
                run.error_message = str(exc)
                run.save(update_fields=["error_message"])

            if campaign.next_run_at is None:
                campaign.status = EmailCampaign.Status.COMPLETED
                campaign.is_active = False

        campaign.save(
            update_fields=[
                "last_run_at",
                "status",
                "is_active",
                "next_run_at",
            ]
        )

        return run.id


def send_campaign_delivery(log_id):
    """
    Send one pending delivery and persist its result.
    """
    with transaction.atomic():
        log = (
            EmailDeliveryLog.objects
            .select_for_update()
            .select_related(
                "campaign_run__campaign",
                "recipient",
            )
            .get(id=log_id)
        )

        if log.status != EmailDeliveryLog.Status.PENDING:
            return log.status

        if log.recipient.is_unsubscribed:
            log.status = EmailDeliveryLog.Status.SKIPPED
            log.error_message = "Recipient has unsubscribed."
            log.save(
                update_fields=[
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )
            return log.status

        log.status = EmailDeliveryLog.Status.SENDING
        log.attempt_count += 1
        log.save(
            update_fields=[
                "status",
                "attempt_count",
                "updated_at",
            ]
        )

        campaign = log.campaign_run.campaign

        subject = campaign.subject
        message = campaign.message
        recipient_email = log.email_address

    # Do not hold a database transaction open while connecting to the
    # email server.
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )

        if sent_count != 1:
            raise RuntimeError("Email backend did not confirm the email send.")

        with transaction.atomic():
            log = EmailDeliveryLog.objects.select_for_update().get(
                id=log_id
            )
            log.status = EmailDeliveryLog.Status.SENT
            log.sent_at = timezone.now()
            log.error_message = ""
            log.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "error_message",
                    "updated_at",
                ]
            )

        return EmailDeliveryLog.Status.SENT

    except Exception as exc:
        with transaction.atomic():
            log = EmailDeliveryLog.objects.select_for_update().get(
                id=log_id
            )
            log.status = EmailDeliveryLog.Status.FAILED
            log.error_message = str(exc)[:5000]
            log.save(
                update_fields=[
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )

        return EmailDeliveryLog.Status.FAILED


def process_campaign_run(run_id):
    """
    Process all pending delivery logs for a campaign run and finalize it.
    """
    run = EmailCampaignRun.objects.select_related("campaign").get(
        id=run_id
    )

    pending_log_ids = list(
        run.delivery_logs.filter(
            status=EmailDeliveryLog.Status.PENDING,
        ).values_list("id", flat=True)
    )

    for log_id in pending_log_ids:
        send_campaign_delivery(log_id)

    with transaction.atomic():
        run = EmailCampaignRun.objects.select_for_update().get(id=run_id)

        logs = run.delivery_logs.all()

        sent_count = logs.filter(
            status=EmailDeliveryLog.Status.SENT,
        ).count()

        failed_count = logs.filter(
            status=EmailDeliveryLog.Status.FAILED,
        ).count()

        skipped_count = logs.filter(
            status=EmailDeliveryLog.Status.SKIPPED,
        ).count()

        pending_count = logs.filter(
            status__in=[
                EmailDeliveryLog.Status.PENDING,
                EmailDeliveryLog.Status.SENDING,
            ],
        ).count()

        run.sent_count = sent_count
        run.failed_count = failed_count
        run.skipped_count = skipped_count
        run.finished_at = timezone.now()

        if pending_count:
            run.status = EmailCampaignRun.Status.PARTIAL
            run.error_message = (
                f"{pending_count} delivery record(s) remain pending or sending."
            )
        elif failed_count and sent_count:
            run.status = EmailCampaignRun.Status.PARTIAL
        elif failed_count:
            run.status = EmailCampaignRun.Status.FAILED
        else:
            run.status = EmailCampaignRun.Status.COMPLETED

        run.save(
            update_fields=[
                "sent_count",
                "failed_count",
                "skipped_count",
                "finished_at",
                "status",
                "error_message",
            ]
        )

    return run