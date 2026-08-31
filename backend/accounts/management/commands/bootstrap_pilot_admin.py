import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from employees.models import Employee


class Command(BaseCommand):
    help = "Create the initial pilot superuser and linked Employee from environment variables."

    def add_arguments(self, parser):
        parser.add_argument("--rotate-password", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        email = os.getenv("PILOT_ADMIN_EMAIL", "").strip().lower()
        username = os.getenv("PILOT_ADMIN_USERNAME", "pilot-admin").strip()
        password = os.getenv("PILOT_ADMIN_PASSWORD", "")
        first_name = os.getenv("PILOT_ADMIN_FIRST_NAME", "Pilot").strip()
        last_name = os.getenv("PILOT_ADMIN_LAST_NAME", "Administrator").strip()
        if not email or not password:
            raise CommandError("PILOT_ADMIN_EMAIL and PILOT_ADMIN_PASSWORD are required.")
        if len(password) < 12:
            raise CommandError("Pilot administrator password must contain at least 12 characters.")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": username, "first_name": first_name, "last_name": last_name},
        )
        if not created:
            if not user.is_superuser:
                raise CommandError("A non-superuser with this email already exists.")
            if options["rotate_password"]:
                user.set_password(password)
                user.save(update_fields=["password"])
                self.stdout.write(self.style.SUCCESS("Pilot administrator password rotated."))
            else:
                self.stdout.write("Pilot administrator already exists; credentials were not changed.")
            Employee.objects.get_or_create(
                user=user, defaults={"first_name": first_name, "last_name": last_name}
            )
            return
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save(update_fields=["password", "is_staff", "is_superuser"])
        Employee.objects.create(user=user, first_name=first_name, last_name=last_name)
        self.stdout.write(self.style.SUCCESS("Pilot administrator and Employee created."))
