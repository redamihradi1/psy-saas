from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from accounts.decorators import require_module_access
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from ..models import Patient, Anamnese, Tag
from ..forms import PatientForm

# (label affiché, clé de permission/licence, modèle, vue résultats, vue passation/édition)
_TEST_SOURCES = [
    ('Vineland', 'vineland', 'tests_psy:vineland_resultats', 'tests_psy:vineland_questionnaire'),
    ('Beck', 'beck', 'tests_psy:beck_resultats', 'tests_psy:beck_passation'),
    ('STAI', 'stai', 'tests_psy:stai_resultats', 'tests_psy:stai_passation'),
    ('D2R', 'd2r', 'tests_psy:d2r_resultats', 'tests_psy:d2r_passation'),
]


def _patient_tests_par_categorie(user, patient):
    """Tests psychométriques de ce patient, groupés par catégorie - uniquement celles que
    l'utilisateur peut voir (licence de l'organisation ET permission utilisateur sur le test),
    pour que le psychologue (ou l'assistant(e) autorisé(e)) retrouve l'historique directement
    depuis la fiche patient, comme sur la vue d'ensemble du super admin."""
    from tests_psy.models import TestVineland, TestBeck, TestSTAI, TestD2R
    models_by_key = {'vineland': TestVineland, 'beck': TestBeck, 'stai': TestSTAI, 'd2r': TestD2R}

    organization = patient.organization
    license = getattr(organization, 'license', None)

    categories = []
    for label, key, resultats_name, edit_name in _TEST_SOURCES:
        if not (license and getattr(license, f'has_{key}', False)):
            continue
        if not user.has_test_permission(key):
            continue

        model = models_by_key[key]
        if user.is_superadmin():
            queryset = model.all_objects.filter(organization=organization, patient=patient)
        else:
            queryset = model.objects.filter(patient=patient)

        tests = []
        for test in queryset.order_by('-date_passation'):
            # Vineland "notes importées" n'a pas de réponses item par item à éditer (édition
            # dédiée), et un lien public pas encore soumis par le parent n'a rien à éditer.
            if key == 'vineland' and getattr(test, 'mode', 'cabinet') == 'importe':
                edit_url = reverse('tests_psy:vineland_notes_importees', kwargs={'test_id': test.id})
            elif key == 'vineland' and getattr(test, 'mode', 'cabinet') == 'lien_public' and not test.lien_soumis_le:
                edit_url = None
            else:
                edit_url = reverse(edit_name, kwargs={'test_id': test.id})

            tests.append({
                'date': test.date_passation,
                'resultats_url': reverse(resultats_name, kwargs={'test_id': test.id}),
                'edit_url': edit_url,
            })
        categories.append({'label': label, 'tests': tests})

    return categories


@login_required
@require_module_access('patients')
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

    # Filtre par tag
    tag_id = request.GET.get('tag', '')
    if tag_id:
        patients = patients.filter(tags__id=tag_id)

    # Pagination
    paginator = Paginator(patients.order_by('nom', 'prenom').distinct(), 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'tag_id': tag_id,
        'all_tags': Tag.objects.all(),
        'total_patients': patients.count(),
    }

    return render(request, 'cabinet/patients_list.html', context)


@login_required
@require_module_access('patients')
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
@require_module_access('patients')
def patient_detail(request, patient_id):
    if request.user.is_superadmin():
        patient = get_object_or_404(Patient.all_objects, id=patient_id)
    else:
        patient = get_object_or_404(Patient, id=patient_id)

    # Anamnèse, consultations, fichiers, statistiques et journal clinique sont du suivi
    # clinique - réservés au module Consultations, pas juste Patients (identité/contact).
    # Si l'utilisateur n'y a pas accès, on ne calcule/n'expose même pas ces données dans le
    # contexte : les masquer seulement côté template laisserait ces infos (dont les montants
    # payés) visibles dans le source HTML.
    can_consultations = request.user.has_module_access('consultations')

    anamnese = None
    consultations = []
    journal_consultations = []
    total_consultations = 0
    total_paye = 0
    derniere_consultation = None
    prochaine_consultation = None

    if can_consultations:
        try:
            anamnese = patient.anamnese
        except Anamnese.DoesNotExist:
            anamnese = None

        consultations = patient.consultation_set.order_by('-date_seance')[:10]
        journal_consultations = patient.consultation_set.order_by('-date_seance')

        total_consultations = patient.consultation_set.count()
        total_paye = patient.consultation_set.aggregate(total=Sum('tarif'))['total'] or 0

        derniere_consultation = patient.consultation_set.order_by('-date_seance').first()
        prochaine_consultation = patient.consultation_set.filter(
            date_seance__gte=timezone.now().date()
        ).order_by('date_seance').first()

    tests_categories = _patient_tests_par_categorie(request.user, patient)

    context = {
        'patient': patient,
        'can_consultations': can_consultations,
        'can_tags': request.user.has_module_access('tags'),
        'anamnese': anamnese,
        'consultations': consultations,
        'journal_consultations': journal_consultations,
        'total_consultations': total_consultations,
        'total_paye': total_paye,
        'derniere_consultation': derniere_consultation,
        'prochaine_consultation': prochaine_consultation,
        'all_tags': Tag.objects.all(),
        'tests_categories': tests_categories,
    }

    return render(request, 'cabinet/patient_detail.html', context)


@login_required
@require_module_access('patients')
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
@require_module_access('patients')
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
