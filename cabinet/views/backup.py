import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone

from ..models import Patient, Anamnese, Consultation, PatientFichier, Depense, MessageTemplate


def _peut_exporter(user):
    return user.is_superadmin() or user.can_export_backup


@login_required
def backup_page(request):
    if not _peut_exporter(request.user):
        messages.error(request, "Tu n'as pas l'autorisation d'exporter les sauvegardes. Demande à l'administrateur de l'activer sur ton compte.")
        return redirect('cabinet:dashboard')
    return render(request, 'cabinet/backup.html')


@login_required
def backup_export(request):
    """Exporte toutes les données de l'organisation en un fichier JSON téléchargeable"""
    if not _peut_exporter(request.user):
        return HttpResponseForbidden("Autorisation requise pour exporter les sauvegardes.")

    organization = request.user.organization

    data = {
        'exported_at': timezone.now().isoformat(),
        'organization': organization.name,
        'patients': json.loads(serializers.serialize('json', Patient.objects.all())),
        'anamneses': json.loads(serializers.serialize('json', Anamnese.objects.all())),
        'consultations': json.loads(serializers.serialize('json', Consultation.objects.all())),
        'fichiers': json.loads(serializers.serialize('json', PatientFichier.objects.all())),
        'depenses': json.loads(serializers.serialize('json', Depense.objects.all())),
        'modeles_messages': json.loads(serializers.serialize('json', MessageTemplate.objects.all())),
    }

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json',
    )
    filename = f"sauvegarde_{organization.slug}_{timezone.now().strftime('%Y%m%d_%H%M')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
