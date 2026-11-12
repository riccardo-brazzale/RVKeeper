import os

from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from accounts.models import User
from workshops.models import Membership, Role, Workshop


class Command(BaseCommand):
    help = "Crea in modo idempotente officina e dati demo per una nuova installazione."

    def handle(self, *args, **options):
        superusers = User.objects.filter(is_superuser=True, is_active=True).order_by("pk")
        admin = superusers.first()
        if admin is None:
            raise CommandError("Crea prima il superuser con manage.py createsuperuser.")

        slug = os.getenv("RVKEEPER_WORKSHOP_SLUG", "rvkeeper-demo").strip()
        name = os.getenv("RVKEEPER_WORKSHOP_NAME", "RVKeeper Demo Workshop").strip()
        if not slug or not name:
            raise CommandError("RVKEEPER_WORKSHOP_SLUG e RVKEEPER_WORKSHOP_NAME non possono essere vuoti.")

        with transaction.atomic():
            workshop, _ = Workshop.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "country": "US",
                    "default_language": "en-us",
                    "timezone": "America/Chicago",
                    "currency": "USD",
                    "is_active": True,
                },
            )
            if not workshop.is_active or workshop.country != "US":
                raise CommandError(
                    f"L'officina {slug!r} esiste ma non è attiva o non ha country=US; non è stata modificata."
                )

            role, _ = Role.objects.get_or_create(
                workshop=workshop,
                code="admin",
                defaults={
                    "name": "Amministratore",
                    "description": "Ruolo iniziale dell'installazione RVKeeper.",
                    "is_system": True,
                },
            )
            membership, created = Membership.objects.get_or_create(
                user=admin,
                workshop=workshop,
                defaults={"role": role, "is_active": True},
            )
            if not created and (membership.role_id != role.pk or not membership.is_active):
                raise CommandError(
                    "Il superuser principale ha già un'appartenenza incompatibile con l'officina demo; "
                    "verificarla nell'admin prima di continuare."
                )

        call_command("populate_demo_data", workshop=slug)
        self.stdout.write(self.style.SUCCESS(f"Installazione inizializzata per {workshop.name} ({slug})."))
