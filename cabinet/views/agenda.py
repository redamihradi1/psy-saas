from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from ..models import Patient, Consultation


def agenda(request):
    """Vue calendrier des consultations"""
    organization = request.user.organization
    patients = Patient.objects.filter(organization=organization)
    return render(request, 'cabinet/agenda.html', {
        'patients': patients
    })


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
                'patient_id': consultation.patient.id,
                'type': consultation.type_consultation,
                'statut': consultation.statut_consultation,
                'duree': consultation.duree_minutes,
                'notes': consultation.notes_cliniques or ''
            }
        })

    return JsonResponse(events, safe=False)
