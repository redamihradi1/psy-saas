from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta

from .models import Patient, Consultation, PackMindOffice
from .forms import PatientForm, ConsultationForm, PackMindOfficeForm


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
    """Détails d'un patient"""
    
    if request.user.is_superadmin():
        patient = get_object_or_404(Patient.all_objects, id=patient_id)
    else:
        patient = get_object_or_404(Patient, id=patient_id)
    
    # Consultations récentes
    consultations = patient.consultation_set.order_by('-date_seance')[:10]
    
    # Stats
    total_consultations = patient.consultation_set.count()
    total_paye = patient.consultation_set.filter(
        statut_paiement='paye'
    ).aggregate(total=Sum('tarif'))['total'] or 0
    
    context = {
        'patient': patient,
        'consultations': consultations,
        'total_consultations': total_consultations,
        'total_paye': total_paye,
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
    """Liste des packs"""
    
    if request.user.is_superadmin():
        packs = PackMindOffice.all_objects.all()
    else:
        packs = PackMindOffice.objects.all()
    
    paginator = Paginator(packs.order_by('-date_achat'), 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {'page_obj': page_obj}
    return render(request, 'cabinet/packs_list.html', context)


@login_required
def pack_create(request):
    """Créer un pack"""
    
    if request.method == 'POST':
        form = PackMindOfficeForm(request.POST)
        if form.is_valid():
            pack = form.save(commit=False)
            if not request.user.is_superadmin():
                pack.organization = request.user.organization
            pack.save()
            messages.success(request, "Pack créé!")
            return redirect('cabinet:pack_detail', pack_id=pack.id)
    else:
        form = PackMindOfficeForm()
    
    context = {
        'form': form,
        'title': 'Nouveau Pack',
    }
    
    return render(request, 'cabinet/pack_form.html', context)


@login_required
def pack_detail(request, pack_id):
    """Détails d'un pack"""
    
    if request.user.is_superadmin():
        pack = get_object_or_404(PackMindOffice.all_objects, id=pack_id)
    else:
        pack = get_object_or_404(PackMindOffice, id=pack_id)
    
    context = {'pack': pack}
    return render(request, 'cabinet/pack_detail.html', context)