from django.core.management.base import BaseCommand

from cabinet.push_utils import envoyer_rappels_consultations_proches


class Command(BaseCommand):
    help = (
        "Envoie une notification push pour chaque consultation démarrant dans ~1h. "
        "À lancer toutes les 10-15 minutes via tâche planifiée. Idempotent."
    )

    def handle(self, *args, **options):
        nb = envoyer_rappels_consultations_proches()
        self.stdout.write(self.style.SUCCESS(f"{nb} rappel(s) envoyé(s)."))
