
from django.core.management.base import BaseCommand

from accounts.models import Company, Permission, Role


class Command(BaseCommand):
    help = "Assign Email Marketing permissions to existing company owners."

    MODULE = "email_marketing"
    ACTIONS = [
        "view",
        "add",
        "change",
        "delete",
        "approve",
        "export",
    ]

    def handle(self, *args, **options):

        permissions = []

        for action in self.ACTIONS:
            codename = f"{self.MODULE}_{action}"

            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={
                    "module": self.MODULE,
                    "action": action,
                    "description": f"{action.title()} Email Marketing",
                },
            )

            permissions.append(permission)

        updated_count = 0

        for company in Company.objects.all():

            owner_role = Role.objects.filter(
                company=company,
                name="OWNER",
            ).first()

            if not owner_role:
                self.stdout.write(
                    self.style.WARNING(
                        f"No OWNER role found for {company.name}"
                    )
                )
                continue

            # Add only these permissions; preserve existing permissions.
            owner_role.permissions.add(*permissions)
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Email Marketing permissions assigned to "
                f"{updated_count} company owner roles."
            )
        )
