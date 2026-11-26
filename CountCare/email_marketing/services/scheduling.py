from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from email_marketing.models import EmailCampaign


def get_campaign_timezone(campaign):
    try:
        return ZoneInfo(campaign.timezone)
    except ZoneInfoNotFoundError:
        raise ValueError(
            f"Invalid campaign timezone: {campaign.timezone}"
        )


def make_local_datetime(campaign, target_date):
    campaign_tz = get_campaign_timezone(campaign)

    local_datetime = datetime.combine(
        target_date,
        campaign.send_time,
    )

    return local_datetime.replace(tzinfo=campaign_tz)


def calculate_next_run_at(campaign, after=None):
    """
    Return the next scheduled execution as an aware datetime.
    Return None when no future execution exists within the campaign dates.
    """
    after = after or timezone.now()
    campaign_tz = get_campaign_timezone(campaign)

    if timezone.is_naive(after):
        after = timezone.make_aware(after, timezone.get_current_timezone())

    after_local = after.astimezone(campaign_tz)

    # One-time campaign: use the explicitly selected datetime.
    if campaign.frequency == EmailCampaign.Frequency.ONCE:
        if not campaign.scheduled_at:
            raise ValueError(
                "Scheduled date and time are required for a one-time campaign."
            )

        scheduled_at = campaign.scheduled_at

        if timezone.is_naive(scheduled_at):
            scheduled_at = scheduled_at.replace(tzinfo=campaign_tz)
        else:
            scheduled_at = scheduled_at.astimezone(campaign_tz)

        if scheduled_at <= after_local:
            return None

        if campaign.end_date and scheduled_at.date() > campaign.end_date:
            return None

        return scheduled_at

    if not campaign.start_date or not campaign.send_time:
        raise ValueError("Campaign start date and send time are required.")

    if campaign.end_date and campaign.end_date < campaign.start_date:
        raise ValueError("Campaign end date cannot be before its start date.")

    # Start searching from the campaign start date or today's local date.
    first_date = max(campaign.start_date, after_local.date())

    # Search day by day. This supports weekly, monthly and custom schedules.
    # The upper bound prevents an invalid schedule from looping indefinitely.
    for offset in range(3660):
        candidate_date = first_date + timedelta(days=offset)

        if campaign.end_date and candidate_date > campaign.end_date:
            return None

        if candidate_date < campaign.start_date:
            continue

        if campaign.frequency == EmailCampaign.Frequency.DAILY:
            matches = True

        elif campaign.frequency == EmailCampaign.Frequency.WEEKLY:
            weekdays = campaign.weekdays or []

            if not weekdays:
                raise ValueError(
                    "Select at least one weekday for a weekly campaign."
                )

            if any(
                not isinstance(day, int) or day < 0 or day > 6
                for day in weekdays
            ):
                raise ValueError(
                    "Weekdays must be numbers from 0 (Monday) to 6 (Sunday)."
                )

            matches = candidate_date.weekday() in weekdays

        elif campaign.frequency == EmailCampaign.Frequency.MONTHLY:
            day = campaign.day_of_month

            if not day or not 1 <= day <= 31:
                raise ValueError(
                    "Monthly campaign day must be between 1 and 31."
                )

            # Months without this date are skipped.
            matches = candidate_date.day == day

        elif campaign.frequency == EmailCampaign.Frequency.CUSTOM:
            interval = campaign.interval_days

            if not interval or interval < 1:
                raise ValueError(
                    "Custom interval must be at least 1 day."
                )

            days_since_start = (
                candidate_date - campaign.start_date
            ).days

            matches = days_since_start % interval == 0

        else:
            raise ValueError("Unsupported campaign frequency.")

        if not matches:
            continue

        candidate_datetime = make_local_datetime(
            campaign,
            candidate_date,
        )

        if candidate_datetime > after_local:
            return candidate_datetime

    return None