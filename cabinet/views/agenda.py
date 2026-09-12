from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse, HttpResponse, Http404
from ..models import Patient, Consultation, Indisponibilite
from ..ics_utils import build_ics_feed
from accounts.models import Organization
from core.middleware import set_current_tenant


@login_required
def agenda(request):
    """Vue calendrier des consultations"""
    organization = request.user.organization
    patients = Patient.objects.filter(organization=organization)
    indisponibilites = Indisponibilite.objects.filter(
        date_fin__gte=timezone.now()
    ).order_by('date_debut')

    ics_path = f"/cabinet/agenda/feed/{organization.get_ics_token()}.ics"
    ics_url = request.build_absolute_uri(ics_path)
    webcal_url = 'webcal://' + ics_url.split('://', 1)[1]

    return render(request, 'cabinet/agenda.html', {
        'patients': patients,
        'indisponibilites': indisponibilites,
        'type_choices': Indisponibilite.TYPE_CHOICES,
        'ics_url': ics_url,
        'webcal_url': webcal_url,
    })


def agenda_ics_feed(request, token):
    """Flux .ics public (protégé par jeton secret) — abonnement calendrier téléphone."""
    try:
        organization = Organization.objects.get(ics_token=token, is_active=True)
    except Organization.DoesNotExist:
        raise Http404("Lien de synchronisation invalide.")

    set_current_tenant(organization)
    try:
        contenu = build_ics_feed(organization)
    finally:
        set_current_tenant(None)

    response = HttpResponse(contenu, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="agenda.ics"'
    return response


@login_required
def agenda_ics_regenerate(request):
    """Régénère le jeton de synchronisation (révoque l'ancien lien)."""
    if request.method == 'POST':
        request.user.organization.regenerate_ics_token()
        messages.success(request, "Le lien de synchronisation a été régénéré. L'ancien lien ne fonctionne plus.")
    return redirect('cabinet:agenda')


@login_required
def consultations_api(request):
    """API JSON pour FullCalendar"""
    if request.user.is_superadmin():
        consultations = Consultation.all_objects.select_related('patient').all()
    else:
        consultations = Consultation.objects.select_related('patient').all()

    events = []
    for consultation in consultations:
        # Calculer l'heure de fin en ajoutant la durée
        end_time = consultation.date_seance + timedelta(minutes=consultation.duree_minutes)

        events.append({
            'id': consultation.id,
            'title': f"{consultation.patient.prenom} {consultation.patient.nom}",
            'start': consultation.date_seance.isoformat(),
            'end': end_time.isoformat(),
            'extendedProps': {
                'event_type': 'consultation',
                'patient_id': consultation.patient.id,
                'type': consultation.type_consultation,
                'statut': consultation.statut_consultation,
                'duree': consultation.duree_minutes,
                'notes': consultation.notes_cliniques or ''
            }
        })

    return JsonResponse(events, safe=False)
