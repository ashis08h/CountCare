from django.core.management.base import BaseCommand
from django.utils import timezone

from email_marketing.models import EmailCampaign
from email_marketing.services.execution import (
    create_campaign_run,
    process_campaign_run,
)


class Command(BaseCommand):
    help = "Execute due email marketing campaigns."

    def handle(self, *args, **options):
        now = timezone.now()

        due_campaign_ids = list(
            EmailCampaign.objects.filter(
                status=EmailCampaign.Status.ACTIVE,
                is_active=True,
                next_run_at__lte=now,
            )
            .order_by("next_run_at")
            .values_list("id", flat=True)
        )

        if not due_campaign_ids:
            self.stdout.write(
                self.style.WARNING("No email campaigns are due.")
            )
            return

        self.stdout.write(
            f"Found {len(due_campaign_ids)} due campaign(s)."
        )

        for campaign_id in due_campaign_ids:
            try:
                run_id = create_campaign_run(campaign_id)

                if run_id is None:
                    self.stdout.write(
                        f"Campaign {campaign_id}: already claimed or no longer due."
                    )
                    continue

                run = process_campaign_run(run_id)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Campaign run {run.id} completed with status "
                        f"{run.status}. Sent: {run.sent_count}, "
                        f"Failed: {run.failed_count}, "
                        f"Skipped: {run.skipped_count}."
                    )
                )

            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"Campaign {campaign_id} failed: {exc}"
                    )
                )