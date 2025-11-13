from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from django.utils import timezone
from django.db.models import Sum
from .models import Patient, Consultation, PackMindOffice, Anamnese
from .forms import PatientForm, ConsultationForm, PackMindOfficeForm
from django.utils.dateparse import parse_datetime
from django.http import FileResponse, Http404
from .models import PatientFichier
from .forms import PatientFichierForm
import os



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
    
    # --- PATIENTS ---
    total_patients = Patient.objects.filter(organization=organization).count()
    nouveaux_patients_mois = Patient.objects.filter(
        organization=organization,
        date_creation__gte=debut_mois
    ).count()
    
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
    
    # --- PACKS ---
    packs_actifs = PackMindOffice.objects.filter(
        organization=organization,
        statut='actif'
    ).filter(nombre_seances_utilisees__lt=F('nombre_seances_total')).count()
    
    # Pour les séances restantes, on doit calculer manuellement
    seances_restantes = sum([
        pack.seances_restantes 
        for pack in PackMindOffice.objects.filter(
            organization=organization,
            statut='actif'
        ).filter(nombre_seances_utilisees__lt=F('nombre_seances_total'))
    ])
    
    # --- STATISTIQUES MOYENNES ---
    stats_moyennes = Consultation.objects.filter(
        organization=organization
    ).aggregate(
        tarif_moyen=Avg('tarif'),
        duree_moyenne=Avg('duree_minutes')
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
        'evolution_patients': 0,  # À calculer si nécessaire
        'consultations_aujourdhui': consultations_aujourdhui,
        'consultations_mois': consultations_mois,
        'consultations_semaine': consultations_semaine,
        'ca_mois': ca_mois,
        'ca_semaine': ca_semaine,
        'packs_actifs': packs_actifs,
        'seances_restantes': seances_restantes,
        'prochaines_consultations': prochaines_consultations,
        'patients_recents': patients_recents,
        'tarif_moyen': stats_moyennes['tarif_moyen'] or 0,
        'duree_moyenne': stats_moyennes['duree_moyenne'] or 60,
        'taux_remplissage': 75,  # À calculer selon ta logique
        'stats_lieu': stats_lieu_formatted,
        'stats_type': stats_type_formatted,
    }
    
    return render(request, 'cabinet/dashboard.html', context)


@login_required
def patients_list(request):
    """Liste des patients"""
    
    # Filtrer par organisation (multi-tenant)
    if request.user.is_superadmin():
        patients = Patient.all_objects.all()
    else:
        patients = Patient.objects.all()
    
    # Recherche
    search_query = request.GET.get('search', '')
    if search_query:
        patients = patients.filter(
            Q(nom__icontains=search_query) |
            Q(prenom__icontains=search_query) |
            Q(telephone__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(patients.order_by('nom', 'prenom'), 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_patients': patients.count(),
    }
    
    return render(request, 'cabinet/patients_list.html', context)


@login_required
def patient_create(request):
    """Créer un patient"""
    
    # VÉRIFICATION : Limite de patients atteinte ?
    if not request.user.is_superadmin():
        license = request.user.organization.license
        if not license.can_add_patient():
            patients_restants = license.get_patients_remaining()
            messages.error(
                request, 
                f"Limite de patients atteinte ! Votre licence autorise {license.max_patients} patients maximum. "
                f"Vous avez actuellement {license.max_patients - patients_restants} patients."
            )
            return redirect('cabinet:patients_list')
    
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save(commit=False)
            # Auto-assigner l'organisation
            if not request.user.is_superadmin():
                patient.organization = request.user.organization
            patient.save()
            messages.success(request, f"Patient {patient.nom_complet} créé avec succès!")
            return redirect('cabinet:patient_detail', patient_id=patient.id)
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        form = PatientForm()
    
    context = {
        'form': form,
        'title': 'Nouveau Patient',
    }
    
    return render(request, 'cabinet/patient_form.html', context)


@login_required
def patient_detail(request, patient_id):
    if request.user.is_superadmin():
        patient = get_object_or_404(Patient.all_objects, id=patient_id)
    else:
        patient = get_object_or_404(Patient, id=patient_id)
    
    try:
        anamnese = patient.anamnese
    except Anamnese.DoesNotExist:
        anamnese = None
    
    consultations = patient.consultation_set.order_by('-date_seance')[:10]
    
    packs_utilises = PackMindOffice.objects.filter(patient=patient) if hasattr(patient, 'pack_set') else []
    
    total_consultations = patient.consultation_set.count()
    total_paye = patient.consultation_set.aggregate(total=Sum('tarif'))['total'] or 0
    
    derniere_consultation = patient.consultation_set.order_by('-date_seance').first()
    prochaine_consultation = patient.consultation_set.filter(
        date_seance__gte=timezone.now().date()
    ).order_by('date_seance').first()
    
    context = {
        'patient': patient,
        'anamnese': anamnese,
        'consultations': consultations,
        'packs_utilises': packs_utilises,
        'total_consultations': total_consultations,
        'total_paye': total_paye,
        'derniere_consultation': derniere_consultation,
        'prochaine_consultation': prochaine_consultation,
    }
    
    return render(request, 'cabinet/patient_detail.html', context)


@login_required
def patient_edit(request, patient_id):
    """Modifier un patient"""
    
    if request.user.is_superadmin():
        patient = get_object_or_404(Patient.all_objects, id=patient_id)
    else:
        patient = get_object_or_404(Patient, id=patient_id)
    
    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, f"Patient {patient.nom_complet} modifié!")
            return redirect('cabinet:patient_detail', patient_id=patient.id)
    else:
        form = PatientForm(instance=patient)
    
    context = {
        'form': form,
        'patient': patient,
        'title': f'Modifier {patient.nom_complet}',
    }
    
    return render(request, 'cabinet/patient_form.html', context)


@login_required
def patient_delete(request, patient_id):
    """Supprimer un patient"""
    
    if request.user.is_superadmin():
        patient = get_object_or_404(Patient.all_objects, id=patient_id)
    else:
        patient = get_object_or_404(Patient, id=patient_id)
    
    if request.method == 'POST':
        nom = patient.nom_complet
        patient.delete()
        messages.success(request, f"Patient {nom} supprimé.")
        return redirect('cabinet:patients_list')
    
    context = {'patient': patient}
    return render(request, 'cabinet/patient_delete.html', context)


@login_required
def anamnese_create(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    
    if request.method == 'POST':
        anamnese = Anamnese.objects.create(
            patient=patient,
            motif_consultation=request.POST.get('motif_consultation'),
            antecedents_medicaux=request.POST.get('antecedents_medicaux', ''),
            situation_professionnelle=request.POST.get('situation_professionnelle', ''),
            objectifs_therapie=request.POST.get('objectifs_therapie', ''),
            niveau_stress=request.POST.get('niveau_stress', 5),
            deja_consulte_psy=request.POST.get('deja_consulte_psy') == 'on'
        )
        messages.success(request, 'Anamnèse créée avec succès')
        return redirect('cabinet:patient_detail', patient_id=patient.id)
    
    return render(request, 'cabinet/anamnese_create.html', {'patient': patient})

@login_required
def anamnese_edit(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    anamnese = get_object_or_404(Anamnese, patient=patient)
    
    if request.method == 'POST':
        anamnese.motif_consultation = request.POST.get('motif_consultation')
        anamnese.antecedents_medicaux = request.POST.get('antecedents_medicaux', '')
        anamnese.antecedents_familiaux = request.POST.get('antecedents_familiaux', '')
        anamnese.medicaments_actuels = request.POST.get('medicaments_actuels', '')
        anamnese.consommation_substances = request.POST.get('consommation_substances', '')
        anamnese.situation_professionnelle = request.POST.get('situation_professionnelle', '')
        anamnese.situation_familiale = request.POST.get('situation_familiale', '')
        anamnese.troubles_sommeil = request.POST.get('troubles_sommeil', '')
        anamnese.troubles_alimentaires = request.POST.get('troubles_alimentaires', '')
        anamnese.activite_physique = request.POST.get('activite_physique', '')
        anamnese.hobbies_bien_etre = request.POST.get('hobbies_bien_etre', '')
        anamnese.objectifs_therapie = request.POST.get('objectifs_therapie', '')
        anamnese.attentes_patient = request.POST.get('attentes_patient', '')
        anamnese.changements_souhaites = request.POST.get('changements_souhaites', '')
        anamnese.contraintes_horaires = request.POST.get('contraintes_horaires', '')
        anamnese.niveau_stress = request.POST.get('niveau_stress', 5)
        anamnese.deja_consulte_psy = request.POST.get('deja_consulte_psy') == 'on'
        anamnese.save()
        
        messages.success(request, 'Anamnèse modifiée avec succès')
        return redirect('cabinet:patient_detail', patient_id=patient.id)
    
    return render(request, 'cabinet/anamnese_edit.html', {'patient': patient, 'anamnese': anamnese})


@login_required
def consultations_list(request):
    """Liste des consultations"""
    
    if request.user.is_superadmin():
        consultations = Consultation.all_objects.select_related('patient').all()
    else:
        consultations = Consultation.objects.select_related('patient').all()
    
    # Filtres
    lieu_filter = request.GET.get('lieu', '')
    if lieu_filter:
        consultations = consultations.filter(lieu_consultation=lieu_filter)
    
    statut_filter = request.GET.get('statut', '')
    if statut_filter:
        consultations = consultations.filter(statut_paiement=statut_filter)
    
    # Pagination
    paginator = Paginator(consultations.order_by('-date_seance'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'lieu_filter': lieu_filter,
        'statut_filter': statut_filter,
    }
    
    return render(request, 'cabinet/consultations_list.html', context)


@login_required
def consultation_create(request):
    """Créer une consultation"""
    
    if request.method == 'POST':
        form = ConsultationForm(request.POST, request=request)
        if form.is_valid():
            consultation = form.save(commit=False)
            if not request.user.is_superadmin():
                consultation.organization = request.user.organization
            consultation.save()
            
            # IMPORTANT : Déduire une séance du PackMindOffice si utilisé
            if consultation.pack_mind_office_utilise:
                PackMindOffice = consultation.pack_mind_office_utilise
                PackMindOffice.nombre_seances_utilisees += 1
                PackMindOffice.save()
                messages.success(request, f"Consultation créée ! Une séance a été déduite du PackMindOffice {PackMindOffice.nom_pack}. ({PackMindOffice.seances_restantes} séances restantes)")
            else:
                messages.success(request, "Consultation créée!")
            
            return redirect('cabinet:consultation_detail', consultation_id=consultation.id)
    else:
        form = ConsultationForm(request=request)
    
    context = {
        'form': form,
        'title': 'Nouvelle Consultation',
    }
    
    return render(request, 'cabinet/consultation_form.html', context)


@login_required
def consultation_detail(request, consultation_id):
    """Détails d'une consultation"""
    
    if request.user.is_superadmin():
        consultation = get_object_or_404(
            Consultation.all_objects.select_related('patient'), 
            id=consultation_id
        )
    else:
        consultation = get_object_or_404(
            Consultation.objects.select_related('patient'), 
            id=consultation_id
        )
    
    context = {'consultation': consultation}
    return render(request, 'cabinet/consultation_detail.html', context)


@login_required
def consultation_edit(request, consultation_id):
    """Modifier une consultation"""
    
    if request.user.is_superadmin():
        consultation = get_object_or_404(Consultation.all_objects, id=consultation_id)
    else:
        consultation = get_object_or_404(Consultation, id=consultation_id)
    
    if request.method == 'POST':
        form = ConsultationForm(request.POST, instance=consultation, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Consultation modifiée!")
            return redirect('cabinet:consultation_detail', consultation_id=consultation.id)
    else:
        form = ConsultationForm(instance=consultation, request=request)
    
    context = {
        'form': form,
        'consultation': consultation,
        'title': 'Modifier Consultation',
    }
    
    return render(request, 'cabinet/consultation_form.html', context)


from django.utils.dateparse import parse_datetime

@login_required
def consultation_reporter(request, consultation_id):
    """Reporter une consultation"""
    consultation = get_object_or_404(
        Consultation, 
        id=consultation_id,
        patient__organization=request.user.organization
    )
    
    if request.method == 'POST':
        # Sauvegarder la date originale si première fois
        if not consultation.date_seance_originale:
            consultation.date_seance_originale = consultation.date_seance
        
        # Nouvelle date - parser la string en datetime
        nouvelle_date_str = request.POST.get('nouvelle_date')
        nouvelle_date = parse_datetime(nouvelle_date_str)
        
        if not nouvelle_date:
            messages.error(request, "Format de date invalide")
            return redirect('cabinet:consultation_reporter', consultation_id=consultation.id)
        
        motif_report = request.POST.get('motif_report', '')
        
        consultation.date_seance = nouvelle_date
        consultation.statut_consultation = 'reportee'
        consultation.nombre_reports += 1
        consultation.motif_report = motif_report
        consultation.save()
        
        messages.success(request, f"Consultation reportée au {nouvelle_date.strftime('%d/%m/%Y à %H:%M')}")
        return redirect('cabinet:consultation_detail', consultation_id=consultation.id)
    
    context = {
        'consultation': consultation,
        'title': 'Reporter la consultation'
    }
    return render(request, 'cabinet/consultation_reporter.html', context)


@login_required
def consultation_annuler(request, consultation_id):
    """Annuler une consultation"""
    consultation = get_object_or_404(
        Consultation, 
        id=consultation_id,
        patient__organization=request.user.organization
    )
    
    if request.method == 'POST':
        motif_annulation = request.POST.get('motif_annulation', '')
        
        # IMPORTANT : Rendre la séance au PackMindOffice si elle avait été utilisée
        if consultation.pack_mind_office_utilise:
            PackMindOffice = consultation.pack_mind_office_utilise
            PackMindOffice.nombre_seances_utilisees -= 1
            PackMindOffice.save()
            messages.success(request, f"La séance a été rendue au PackMindOffice {PackMindOffice.nom_pack}")
        
        consultation.statut_consultation = 'annulee'
        consultation.motif_report = motif_annulation  # On utilise ce champ pour le motif
        consultation.save()
        
        messages.warning(request, "Consultation annulée")
        return redirect('cabinet:consultation_detail', consultation_id=consultation.id)
    
    context = {
        'consultation': consultation,
        'title': 'Annuler la consultation'
    }
    return render(request, 'cabinet/consultation_annuler.html', context)

@login_required
def consultation_delete(request, consultation_id):
    """Supprimer une consultation"""
    
    if request.user.is_superadmin():
        consultation = get_object_or_404(Consultation.all_objects, id=consultation_id)
    else:
        consultation = get_object_or_404(Consultation, id=consultation_id)
    
    if request.method == 'POST':
        consultation.delete()
        messages.success(request, "Consultation supprimée.")
        return redirect('cabinet:consultations_list')
    
    context = {'consultation': consultation}
    return render(request, 'cabinet/consultation_delete.html', context)


@login_required
def packs_list(request):
    organization = request.user.organization
    
    # Récupérer tous les packs
    packs = PackMindOffice.objects.filter(organization=organization).order_by('-date_achat')
    
    # Filtres
    search_query = request.GET.get('search', '')
    statut_filter = request.GET.get('statut', '')
    
    if search_query:
        packs = packs.filter(nom_pack__icontains=search_query)
    
    if statut_filter:
        packs = packs.filter(statut=statut_filter)
    
    # Statistiques
    total_packs = packs.count()
    packs_actifs = packs.filter(statut='actif').count()
    seances_totales_restantes = sum([p.seances_restantes for p in packs])
    chiffre_affaires_packs = packs.aggregate(total=Sum('prix_pack'))['total'] or 0
    
    context = {
        'packs': packs,
        'search_query': search_query,
        'statut_filter': statut_filter,
        'total_packs': total_packs,
        'packs_actifs': packs_actifs,
        'seances_totales_restantes': seances_totales_restantes,
        'chiffre_affaires_packs': chiffre_affaires_packs,
    }
    
    return render(request, 'cabinet/packs_list.html', context)


@login_required
def pack_create(request):
    """Créer un PackMindOffice"""
    
    if request.method == 'POST':
        form = PackMindOfficeForm(request.POST)
        if form.is_valid():
            pack = form.save(commit=False)
            if not request.user.is_superadmin():
                pack.organization = request.user.organization
            pack.save()
            messages.success(request, "Pack Mind Office créé!")
            return redirect('cabinet:pack_detail', pack_id=pack.id)
    else:
        form = PackMindOfficeForm()
    
    context = {
        'form': form,
        'title': 'Nouveau Pack Mind Office',
    }
    
    return render(request, 'cabinet/pack_form.html', context)


@login_required
def pack_detail(request, pack_id):
    """Détails d'un PackMindOffice"""
    
    if request.user.is_superadmin():
        pack = get_object_or_404(PackMindOffice.all_objects, id=pack_id)
    else:
        pack = get_object_or_404(PackMindOffice, id=pack_id)
    
    # Récupérer les consultations qui ont utilisé ce pack
    consultations_pack = Consultation.objects.filter(
        pack_mind_office_utilise=pack
    ).select_related('patient').order_by('-date_seance')
    
    context = {
        'pack': pack,
        'consultations_pack': consultations_pack
    }
    return render(request, 'cabinet/pack_detail.html', context)


@login_required
def pack_edit(request, pack_id):
    pack = get_object_or_404(PackMindOffice, id=pack_id, organization=request.user.organization)
    
    if request.method == 'POST':
        form = PackMindOfficeForm(request.POST, instance=pack)
        if form.is_valid():
            form.save()
            messages.success(request, "Pack Mind Office modifié avec succès!")
            return redirect('cabinet:pack_detail', pack_id=pack.id)
    else:
        form = PackMindOfficeForm(instance=pack)
    
    context = {
        'form': form,
        'pack': pack,
        'title': 'Modifier Pack Mind Office',
    }
    
    return render(request, 'cabinet/pack_form.html', context)


@login_required
def pack_delete(request, pack_id):
    pack = get_object_or_404(PackMindOffice, id=pack_id, organization=request.user.organization)
    pack.delete()
    messages.success(request, "Pack Mind Office supprimé avec succès!")
    return redirect('cabinet:packs_list')


@login_required
def anamnese_create(request, patient_id):
    """Créer une anamnèse"""
    if request.user.is_superadmin():
        patient = get_object_or_404(Patient.all_objects, id=patient_id)
    else:
        patient = get_object_or_404(Patient, id=patient_id)
    
    # Vérifier si anamnèse existe déjà
    if hasattr(patient, 'anamnese'):
        messages.warning(request, "Une anamnèse existe déjà pour ce patient.")
        return redirect('cabinet:patient_detail', patient_id=patient.id)
    
    if request.method == 'POST':
        # Créer l'anamnèse directement depuis POST
        from cabinet.models import Anamnese
        anamnese = Anamnese(
            patient=patient,
            motif_consultation=request.POST.get('motif_consultation', ''),
            antecedents_medicaux=request.POST.get('antecedents_medicaux', ''),
            antecedents_familiaux=request.POST.get('antecedents_familiaux', ''),
            medicaments_actuels=request.POST.get('medicaments_actuels', ''),
            situation_professionnelle=request.POST.get('situation_professionnelle', ''),
            situation_familiale=request.POST.get('situation_familiale', ''),
            troubles_sommeil=request.POST.get('troubles_sommeil', ''),
            troubles_alimentaires=request.POST.get('troubles_alimentaires', ''),
            activite_physique=request.POST.get('activite_physique', ''),
            hobbies_bien_etre=request.POST.get('hobbies_bien_etre', ''),
            changements_souhaites=request.POST.get('changements_souhaites', ''),
            consommation_substances=request.POST.get('consommation_substances', ''),
            niveau_stress=int(request.POST.get('niveau_stress', 5)),
            objectifs_therapie=request.POST.get('objectifs_therapie', ''),
            attentes_patient=request.POST.get('attentes_patient', ''),
            contraintes_horaires=request.POST.get('contraintes_horaires', ''),
            deja_consulte_psy=request.POST.get('deja_consulte_psy') == 'true',
        )
        if not request.user.is_superadmin():
            anamnese.organization = request.user.organization
        anamnese.save()
        messages.success(request, "Anamnèse créée avec succès!")
        return redirect('cabinet:patient_detail', patient_id=patient.id)
    
    return render(request, 'cabinet/anamnese_create.html', {'patient': patient, 'form': {}})

# Vue agenda
def agenda(request):
    """Vue calendrier des consultations"""
    # Récupère l'organisation du user
    organization = request.user.organization
    patients = Patient.objects.filter(organization=organization)
    return render(request, 'cabinet/agenda.html', {
        'patients': patients
    })

# API pour récupérer les consultations (format FullCalendar)
# API pour récupérer les consultations (format FullCalendar)
@login_required
def consultations_api(request):
    """API JSON pour FullCalendar"""
    organization = request.user.organization
    
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
                'statut': consultation.statut_consultation,  # ← Corrigé (c'était 'statut')
                'duree': consultation.duree_minutes,
                'notes': consultation.notes_cliniques or ''  # ← Corrigé (c'était 'notes')
            }
        })
    
    return JsonResponse(events, safe=False)


# Créer consultation (AJAX)
@login_required
@require_http_methods(["POST"])
def consultation_create_ajax(request):
    """Création de consultation via AJAX"""
    try:
        organization = request.user.organization
        patient_id = request.POST.get('patient')
        patient = Patient.objects.get(id=patient_id, organization=organization)
        
        # Combiner date et heure en un seul DateTimeField
        date_str = request.POST.get('date')
        heure_str = request.POST.get('heure')
        date_seance = timezone.datetime.strptime(f"{date_str} {heure_str}", "%Y-%m-%d %H:%M")
        date_seance = timezone.make_aware(date_seance)
        
        consultation = Consultation.objects.create(
            patient=patient,
            organization=organization,
            date_seance=date_seance,
            duree_minutes=int(request.POST.get('duree', 60)),
            type_consultation=request.POST.get('type_consultation', 'individuelle'),
            statut_consultation=request.POST.get('statut', 'planifie'),  # ← Corrigé
            notes_cliniques=request.POST.get('notes', ''),  # ← Corrigé
            tarif=0,  # Tu peux adapter selon tes besoins
            lieu_consultation='visio'  # Valeur par défaut
        )
        
        return JsonResponse({'success': True, 'id': consultation.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# Modifier consultation (AJAX)
@login_required
@require_http_methods(["POST"])
def consultation_edit_ajax(request, pk):
    """Modification de consultation via AJAX"""
    try:
        if request.user.is_superadmin():
            consultation = Consultation.all_objects.get(pk=pk)
        else:
            consultation = Consultation.objects.get(pk=pk)
        
        # Combiner date et heure
        date_str = request.POST.get('date')
        heure_str = request.POST.get('heure')
        date_seance = timezone.datetime.strptime(f"{date_str} {heure_str}", "%Y-%m-%d %H:%M")
        date_seance = timezone.make_aware(date_seance)
        
        consultation.date_seance = date_seance
        consultation.duree_minutes = int(request.POST.get('duree', 60))
        consultation.type_consultation = request.POST.get('type_consultation')
        consultation.statut_consultation = request.POST.get('statut')  # ← Corrigé
        consultation.notes_cliniques = request.POST.get('notes', '')  # ← Corrigé
        consultation.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def fichier_upload(request, patient_id):
    """Upload un fichier pour un patient"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    
    if request.method == 'POST':
        form = PatientFichierForm(request.POST, request.FILES)
        if form.is_valid():
            fichier = form.save(commit=False)
            fichier.patient = patient
            fichier.organization = request.user.organization
            fichier.save()
            messages.success(request, f"Fichier '{fichier.nom_fichier}' uploadé avec succès !")
            return redirect('cabinet:patient_detail', patient_id=patient.id)
        else:
            messages.error(request, "Erreur lors de l'upload du fichier.")
    else:
        form = PatientFichierForm()
    
    context = {
        'form': form,
        'patient': patient,
        'title': f'Ajouter un fichier pour {patient.nom_complet}'
    }
    
    return render(request, 'cabinet/fichier_upload.html', context)


@login_required
def fichier_delete(request, patient_id, fichier_id):
    """Supprimer un fichier"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    fichier = get_object_or_404(PatientFichier, id=fichier_id, patient=patient)
    
    if request.method == 'POST':
        nom = fichier.nom_fichier
        # Supprimer le fichier physique
        if fichier.fichier:
            if os.path.isfile(fichier.fichier.path):
                os.remove(fichier.fichier.path)
        fichier.delete()
        messages.success(request, f"Fichier '{nom}' supprimé.")
        return redirect('cabinet:patient_detail', patient_id=patient.id)
    
    context = {
        'fichier': fichier,
        'patient': patient
    }
    
    return render(request, 'cabinet/fichier_delete.html', context)


@login_required
def fichier_download(request, patient_id, fichier_id):
    """Télécharger un fichier"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    fichier = get_object_or_404(PatientFichier, id=fichier_id, patient=patient)
    
    if not fichier.fichier or not os.path.isfile(fichier.fichier.path):
        raise Http404("Fichier introuvable")
    
    response = FileResponse(open(fichier.fichier.path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{fichier.nom_fichier}"'
    
    return response


@login_required
def fichier_preview(request, patient_id, fichier_id):
    """Prévisualiser un fichier (images et PDF)"""
    patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    fichier = get_object_or_404(PatientFichier, id=fichier_id, patient=patient)
    
    if not fichier.fichier or not os.path.isfile(fichier.fichier.path):
        raise Http404("Fichier introuvable")
    
    # Pour les images et PDF, on peut les afficher directement
    if fichier.est_image or fichier.est_pdf:
        response = FileResponse(open(fichier.fichier.path, 'rb'))
        response['Content-Disposition'] = f'inline; filename="{fichier.nom_fichier}"'
        return response
    else:
        # Pour les autres types, on télécharge
        return fichier_download(request, patient_id, fichier_id)