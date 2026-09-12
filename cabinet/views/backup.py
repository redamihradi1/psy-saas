import json
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone

from ..models import Patient, Anamnese, Consultation, PatientFichier, Depense, MessageTemplate


def _peut_exporter(user):
    return user.is_superadmin() or user.can_export_backup


def build_backup_data(organization):
    """Construit le dict de sauvegarde pour une organisation.

    Suppose que le tenant courant (thread-local) est déjà positionné sur
    `organization` (cas d'une requête normale via TenantMiddleware, ou
    positionné manuellement avec `set_current_tenant` dans un script/commande).
    """
    return {
        'exported_at': timezone.now().isoformat(),
        'organization': organization.name,
        'patients': json.loads(serializers.serialize('json', Patient.objects.all())),
        'anamneses': json.loads(serializers.serialize('json', Anamnese.objects.all())),
        'consultations': json.loads(serializers.serialize('json', Consultation.objects.all())),
        'fichiers': json.loads(serializers.serialize('json', PatientFichier.objects.all())),
        'depenses': json.loads(serializers.serialize('json', Depense.objects.all())),
        'modeles_messages': json.loads(serializers.serialize('json', MessageTemplate.objects.all())),
    }


def auto_backup_dir(organization):
    """Dossier de sauvegarde automatique pour une organisation (hors static/media, non servi publiquement)."""
    return os.path.join(settings.BASE_DIR, 'backups', organization.slug)


def latest_auto_backup(organization):
    """Retourne (chemin, date de modification) de la dernière sauvegarde auto, ou (None, None)."""
    directory = auto_backup_dir(organization)
    if not os.path.isdir(directory):
        return None, None
    files = [f for f in os.listdir(directory) if f.endswith('.json')]
    if not files:
        return None, None
    files.sort(reverse=True)
    latest = os.path.join(directory, files[0])
    return latest, timezone.datetime.fromtimestamp(os.path.getmtime(latest), tz=timezone.get_current_timezone())


@login_required
def backup_page(request):
    if not _peut_exporter(request.user):
        messages.error(request, "Tu n'as pas l'autorisation d'exporter les sauvegardes. Demande à l'administrateur de l'activer sur ton compte.")
        return redirect('cabinet:dashboard')

    _, derniere_date = latest_auto_backup(request.user.organization)
    return render(request, 'cabinet/backup.html', {
        'derniere_sauvegarde_auto': derniere_date,
    })


@login_required
def backup_export(request):
    """Exporte toutes les données de l'organisation en un fichier JSON téléchargeable"""
    if not _peut_exporter(request.user):
        return HttpResponseForbidden("Autorisation requise pour exporter les sauvegardes.")

    organization = request.user.organization
    data = build_backup_data(organization)

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json',
    )
    filename = f"sauvegarde_{organization.slug}_{timezone.now().strftime('%Y%m%d_%H%M')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
