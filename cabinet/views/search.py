from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse

from ..models import Patient, Consultation


@login_required
def global_search(request):
    """Recherche globale (patients + consultations) pour la barre de la sidebar"""
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'patients': [], 'consultations': []})

    patients = Patient.objects.filter(
        Q(nom__icontains=query) | Q(prenom__icontains=query) | Q(telephone__icontains=query)
    ).order_by('nom', 'prenom')[:5]

    consultations = Consultation.objects.select_related('patient').filter(
        Q(patient__nom__icontains=query) | Q(patient__prenom__icontains=query)
    ).order_by('-date_seance')[:5]

    return JsonResponse({
        'patients': [
            {
                'label': patient.nom_complet,
                'sublabel': patient.telephone or patient.email or '',
                'url': reverse('cabinet:patient_detail', kwargs={'patient_id': patient.id}),
            }
            for patient in patients
        ],
        'consultations': [
            {
                'label': consultation.patient.nom_complet,
                'sublabel': consultation.date_seance.strftime('%d/%m/%Y à %H:%M'),
                'url': reverse('cabinet:consultation_detail', kwargs={'consultation_id': consultation.id}),
            }
            for consultation in consultations
        ],
    })
