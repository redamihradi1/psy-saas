from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from ..models import Patient, Consultation


@login_required
def dashboard_view(request):
    """
    Vue principale du dashboard avec toutes les statistiques
    """
    user = request.user
    organization = user.organization
    today = timezone.now().date()

    # Début du mois et de la semaine
    debut_mois = today.replace(day=1)
    debut_semaine = today - timedelta(days=today.weekday())
    debut_mois_dernier = (debut_mois - timedelta(days=1)).replace(day=1)

    # --- PATIENTS ---
    total_patients = Patient.objects.filter(organization=organization).count()
    nouveaux_patients_mois = Patient.objects.filter(
        organization=organization,
        date_creation__gte=debut_mois
    ).count()
    nouveaux_patients_mois_dernier = Patient.objects.filter(
        organization=organization,
        date_creation__gte=debut_mois_dernier,
        date_creation__lt=debut_mois
    ).count()

    if nouveaux_patients_mois_dernier > 0:
        evolution_patients = round(
            (nouveaux_patients_mois - nouveaux_patients_mois_dernier) / nouveaux_patients_mois_dernier * 100
        )
    elif nouveaux_patients_mois > 0:
        evolution_patients = 100
    else:
        evolution_patients = 0

    patients_recents = Patient.objects.filter(
        organization=organization
    ).order_by('-date_creation')[:5]

    # --- CONSULTATIONS ---
    consultations_aujourdhui = Consultation.objects.filter(
        organization=organization,
        date_seance__date=today
    ).count()

    consultations_mois = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=debut_mois
    ).count()

    consultations_semaine = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=debut_semaine
    ).count()

    # Prochaines consultations
    prochaines_consultations = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=timezone.now()
    ).select_related('patient').order_by('date_seance')[:10]

    # Consultations du jour (vue "aujourd'hui" avec actions rapides)
    consultations_du_jour = Consultation.objects.filter(
        organization=organization,
        date_seance__date=today
    ).select_related('patient').order_by('date_seance')

    # --- CHIFFRE D'AFFAIRES ---
    ca_mois = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=debut_mois,
        statut_paiement='paye'
    ).aggregate(total=Sum('tarif'))['total'] or 0

    ca_semaine = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=debut_semaine,
        statut_paiement='paye'
    ).aggregate(total=Sum('tarif'))['total'] or 0

    # --- STATISTIQUES MOYENNES ---
    stats_moyennes = Consultation.objects.filter(
        organization=organization
    ).aggregate(
        tarif_moyen=Avg('tarif'),
        duree_moyenne=Avg('duree_minutes')
    )

    # --- TAUX DE PAIEMENT (consultations payées ce mois) ---
    consultations_mois_qs = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=debut_mois
    )
    consultations_payees_mois = consultations_mois_qs.filter(statut_paiement='paye').count()
    taux_paiement = round(
        (consultations_payees_mois / consultations_mois * 100) if consultations_mois > 0 else 0
    )

    # --- RÉPARTITION PAR LIEU ---
    stats_lieu = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=debut_mois
    ).values('lieu_consultation').annotate(count=Count('id'))

    total_lieu = sum([s['count'] for s in stats_lieu])
    stats_lieu_formatted = []
    lieu_dict = dict(Consultation.LIEU_CONSULTATION_CHOICES)

    for stat in stats_lieu:
        stats_lieu_formatted.append({
            'lieu_name': lieu_dict.get(stat['lieu_consultation'], stat['lieu_consultation']),
            'count': stat['count'],
            'pourcentage': round((stat['count'] / total_lieu * 100) if total_lieu > 0 else 0, 1)
        })

    # --- RÉPARTITION PAR TYPE ---
    stats_type = Consultation.objects.filter(
        organization=organization,
        date_seance__gte=debut_mois
    ).values('type_consultation').annotate(count=Count('id'))

    total_type = sum([s['count'] for s in stats_type])
    stats_type_formatted = []
    type_dict = dict(Consultation.TYPE_CONSULTATION_CHOICES)

    for stat in stats_type:
        stats_type_formatted.append({
            'type_name': type_dict.get(stat['type_consultation'], stat['type_consultation']),
            'count': stat['count'],
            'pourcentage': round((stat['count'] / total_type * 100) if total_type > 0 else 0, 1)
        })

    context = {
        'today': today,
        'total_patients': total_patients,
        'nouveaux_patients_mois': nouveaux_patients_mois,
        'evolution_patients': evolution_patients,
        'consultations_aujourdhui': consultations_aujourdhui,
        'consultations_mois': consultations_mois,
        'consultations_semaine': consultations_semaine,
        'ca_mois': ca_mois,
        'ca_semaine': ca_semaine,
        'prochaines_consultations': prochaines_consultations,
        'consultations_du_jour': consultations_du_jour,
        'patients_recents': patients_recents,
        'tarif_moyen': stats_moyennes['tarif_moyen'] or 0,
        'duree_moyenne': stats_moyennes['duree_moyenne'] or 60,
        'taux_paiement': taux_paiement,
        'stats_lieu': stats_lieu_formatted,
        'stats_type': stats_type_formatted,
    }

    return render(request, 'cabinet/dashboard.html', context)
