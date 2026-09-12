import json
import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Organization
from cabinet.views.backup import auto_backup_dir, build_backup_data
from core.middleware import set_current_tenant

NB_SAUVEGARDES_CONSERVEES = 14


class Command(BaseCommand):
    help = (
        "Génère une sauvegarde JSON pour chaque organisation active et la stocke "
        "dans backups/<organisation>/. Ne conserve que les N dernières (rotation). "
        "À lancer une fois par jour via une tâche planifiée (cron / Scheduled Task PythonAnywhere)."
    )

    def handle(self, *args, **options):
        organisations = Organization.objects.filter(is_active=True)
        total = 0

        for organization in organisations:
            set_current_tenant(organization)
            try:
                data = build_backup_data(organization)

                directory = auto_backup_dir(organization)
                os.makedirs(directory, exist_ok=True)

                filename = f"{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
                filepath = os.path.join(directory, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                self._faire_rotation(directory)

                total += 1
                self.stdout.write(self.style.SUCCESS(f"OK : {organization.name} -> {filepath}"))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Échec pour {organization.name} : {exc}"))
            finally:
                set_current_tenant(None)

        self.stdout.write(self.style.SUCCESS(f"Sauvegarde automatique terminée ({total} organisation(s))."))

    def _faire_rotation(self, directory):
        fichiers = sorted(
            (f for f in os.listdir(directory) if f.endswith('.json')),
            reverse=True,
        )
        for ancien in fichiers[NB_SAUVEGARDES_CONSERVEES:]:
            os.remove(os.path.join(directory, ancien))
