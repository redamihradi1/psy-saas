from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import require_test_access
from tests_psy.forms.brief import TestBRIEFNouveauForm, NotesImporteesBRIEFForm
from tests_psy.models.brief import (
    ECHELLE_CHOICES, REPONSE_CHOICES, ItemBRIEF, NoteBruteImporteeBRIEF, ReponseBRIEF, TestBRIEF,
)
from .scoring import calculer_resultats, LIBELLES


def _get_test(request, test_id):
    """Le superadmin n'a pas d'organisation : il passe par all_objects (voir projet.md §4)."""
    if request.user.is_superadmin():
        return get_object_or_404(TestBRIEF.all_objects.select_related('patient'), id=test_id)
    return get_object_or_404(
        TestBRIEF.objects.select_related('patient'), id=test_id, organization=request.user.organization,
    )


def _edit_url(test):
    """Lien d'édition selon le mode : notes importées -> page dédiée ; lien public pas encore
    soumis -> rien à éditer (le parent n'a pas répondu) ; sinon la page de passation."""
    if test.mode == 'importe':
        return reverse('tests_psy:brief_notes_importees', kwargs={'test_id': test.id})
    if test.mode == 'lien_public' and not test.lien_soumis_le:
        return None
    return reverse('tests_psy:brief_questionnaire', kwargs={'test_id': test.id})


@login_required
@require_test_access('brief')
def brief_liste(request):
    if request.user.is_superadmin():
        tests = TestBRIEF.all_objects.select_related('patient', 'psychologue')
    else:
        tests = TestBRIEF.objects.select_related('patient', 'psychologue')
    tests = list(tests.order_by('-date_passation'))
    for test in tests:
        test.edit_url = _edit_url(test)

    peut_creer, tests_restants = True, 'Illimité'
    if not request.user.is_superadmin():
        license = request.user.organization.license
        peut_creer = license.can_add_test('brief')
        tests_restants = license.get_tests_remaining('brief')

    return render(request, 'tests_psy/brief/liste.html', {
        'tests': tests,
        'now': timezone.now(),
        'peut_creer': peut_creer,
        'tests_restants': tests_restants,
        'items_charges': ItemBRIEF.objects.filter(forme='parent').exists(),
    })


@login_required
@require_test_access('brief')
def brief_nouveau(request, patient_id=None):
    """Créer un test BRIEF - 3 modes : passation en cabinet, scores bruts importés (déjà
    cotés sur papier), ou lien public envoyé au parent. Le quota de la licence s'applique
    aux 3 modes, puisque la ligne TestBRIEF est créée tout de suite."""
    if not request.user.is_superadmin():
        license = request.user.organization.license
        if not license.can_add_test('brief'):
            messages.error(
                request,
                f"Limite de tests BRIEF atteinte ! Votre licence autorise {license.max_tests_brief} tests BRIEF maximum.",
            )
            return redirect('tests_psy:brief_liste')

    form_kwargs = {'all_patients': True} if request.user.is_superadmin() else {'organization': request.user.organization}
    if request.method == 'POST':
        form = TestBRIEFNouveauForm(request.POST, **form_kwargs)
        if form.is_valid():
            patient = form.cleaned_data['patient']
            mode = form.cleaned_data['mode']
            test = TestBRIEF.objects.create(
                patient=patient,
                psychologue=request.user,
                organization=patient.organization if request.user.is_superadmin() else request.user.organization,
                sexe=form.cleaned_data['sexe'],
                repondant=form.cleaned_data['repondant'],
                mode=mode,
            )
            if mode == 'importe':
                messages.success(request, "Test BRIEF créé - saisis les scores bruts déjà cotés.")
                return redirect('tests_psy:brief_notes_importees', test_id=test.id)
            if mode == 'lien_public':
                test.generate_lien_public(int(form.cleaned_data['duree_jours']))
                messages.success(request, "Lien public généré.")
                return redirect('tests_psy:brief_lien_genere', test_id=test.id)
            messages.success(request, "Test BRIEF créé avec succès !")
            return redirect('tests_psy:brief_questionnaire', test_id=test.id)
    else:
        initial = {'patient': patient_id} if patient_id else {}
        form = TestBRIEFNouveauForm(initial=initial, **form_kwargs)

    return render(request, 'tests_psy/brief/nouveau.html', {
        'form': form,
        'items_charges': ItemBRIEF.objects.filter(forme='parent').exists(),
    })


def _build_passation_context(test):
    """Items du questionnaire avec la réponse déjà enregistrée posée sur chaque item -
    partagé entre la passation en cabinet et le lien public (public.py)."""
    reponses = dict(test.reponses.values_list('item__numero', 'reponse'))
    items = list(ItemBRIEF.objects.filter(forme=test.forme).order_by('numero'))
    for item in items:
        item.reponse_actuelle = reponses.get(item.numero)
    return {
        'items': items,
        'choix_reponses': REPONSE_CHOICES,
        'nb_reponses': len(reponses),
    }


def _save_passation_post(test, post_data):
    """Enregistre les réponses postées (champs item_<numéro> = J/P/S). Retourne le nombre
    d'items encore sans réponse. Les réponses manquantes sont tolérées (le manuel prévoit
    leur cotation), la fin de passation est donc une action explicite."""
    valides = dict(REPONSE_CHOICES)
    items = {item.numero: item for item in ItemBRIEF.objects.filter(forme=test.forme)}
    with transaction.atomic():
        for key, value in post_data.items():
            if not key.startswith('item_') or value not in valides:
                continue
            try:
                item = items[int(key[len('item_'):])]
            except (ValueError, KeyError):
                continue
            ReponseBRIEF.objects.update_or_create(
                test=test, item=item,
                defaults={'reponse': value, 'organization': test.organization},
            )
    return len(items) - test.reponses.count()


@login_required
@require_test_access('brief')
def brief_questionnaire(request, test_id):
    """Passation en cabinet (et édition des réponses d'un test déjà terminé)."""
    test = _get_test(request, test_id)
    if test.mode == 'importe':
        return redirect('tests_psy:brief_notes_importees', test_id=test.id)

    if request.method == 'POST':
        manquants = _save_passation_post(test, request.POST)
        if request.POST.get('action') == 'submit':
            if not test.termine_le:
                test.termine_le = timezone.now()
                test.save(update_fields=['termine_le'])
            if manquants:
                messages.warning(request, f"Test enregistré avec {manquants} item(s) sans réponse.")
            else:
                messages.success(request, "Test BRIEF complété !")
            return redirect('tests_psy:brief_resultats', test_id=test.id)
        messages.success(request, "Réponses enregistrées. Tu peux reprendre plus tard.")
        return redirect('tests_psy:brief_questionnaire', test_id=test.id)

    return render(request, 'tests_psy/brief/questionnaire.html', {
        'test': test,
        'patient': test.patient,
        'is_public': False,
        **_build_passation_context(test),
    })


@login_required
@require_test_access('brief')
def brief_notes_importees(request, test_id):
    """Mode 'importe' : saisie/édition des scores bruts par échelle déjà cotés sur papier."""
    test = _get_test(request, test_id)
    if test.mode != 'importe':
        messages.error(request, "Ce test n'est pas en mode notes importées.")
        return redirect('tests_psy:brief_liste')

    initial_notes = dict(test.notes_brutes_importees.values_list('echelle', 'note_brute'))
    if request.method == 'POST':
        form = NotesImporteesBRIEFForm(request.POST, initial_notes=initial_notes)
        if form.is_valid():
            with transaction.atomic():
                for code, _ in ECHELLE_CHOICES:
                    NoteBruteImporteeBRIEF.objects.update_or_create(
                        test=test, echelle=code,
                        defaults={'note_brute': form.cleaned_data[f'echelle_{code}'], 'organization': test.organization},
                    )
                test.negativite_importee = form.cleaned_data['negativite']
                test.incoherence_importee = form.cleaned_data['incoherence']
                test.save(update_fields=['negativite_importee', 'incoherence_importee'])
            messages.success(request, "Scores bruts enregistrés.")
            return redirect('tests_psy:brief_resultats', test_id=test.id)
    else:
        form = NotesImporteesBRIEFForm(initial_notes=initial_notes, initial={
            'negativite': test.negativite_importee,
            'incoherence': test.incoherence_importee,
        })

    return render(request, 'tests_psy/brief/notes_importees.html', {
        'test': test,
        'patient': test.patient,
        'form': form,
    })


@login_required
@require_test_access('brief')
def brief_resultats(request, test_id):
    test = _get_test(request, test_id)
    if test.mode == 'lien_public' and not test.lien_soumis_le and not test.reponses.exists():
        messages.info(request, "Le parent n'a pas encore rempli le questionnaire.")
        return redirect('tests_psy:brief_lien_genere', test_id=test.id)

    resultats = calculer_resultats(test)

    items_reponses = []
    if test.mode != 'importe':
        libelles_reponses = dict(REPONSE_CHOICES)
        for item in ItemBRIEF.objects.filter(forme=test.forme).order_by('numero'):
            valeur = resultats['reponses'].get(item.numero)
            items_reponses.append({
                'numero': item.numero,
                'texte': item.texte,
                'echelle': LIBELLES.get(item.echelle, '—') if item.echelle else 'Item additionnel',
                'valeur': valeur,
                'reponse': libelles_reponses[{1: 'J', 2: 'P', 3: 'S'}[valeur]] if valeur else None,
            })

    profil = {
        'labels': [ligne['libelle_court'] for ligne in resultats['lignes']],
        'scores_t': [ligne['score_t'] for ligne in resultats['lignes']],
    }

    return render(request, 'tests_psy/brief/resultats.html', {
        'test': test,
        'patient': test.patient,
        'r': resultats,
        'items_reponses': items_reponses,
        'profil': profil,
        'edit_url': _edit_url(test),
    })


@login_required
@require_test_access('brief')
def brief_lien_genere(request, test_id):
    """Lien à copier ou envoyer par WhatsApp au parent - destinée au psy uniquement."""
    test = _get_test(request, test_id)
    if test.mode != 'lien_public' or not test.lien_token:
        messages.error(request, "Ce test n'a pas de lien public.")
        return redirect('tests_psy:brief_liste')
    lien_url = request.build_absolute_uri(
        reverse('tests_psy:brief_public_questionnaire', kwargs={'token': test.lien_token})
    )
    return render(request, 'tests_psy/brief/lien_genere.html', {
        'test': test,
        'patient': test.patient,
        'lien_url': lien_url,
    })


@login_required
@require_test_access('brief')
def brief_reouvrir_lien(request, test_id):
    """Réouvre un lien soumis ou expiré en un clic - même jeton, le lien déjà envoyé au
    parent redevient utilisable."""
    test = _get_test(request, test_id)
    if request.method == 'POST' and test.mode == 'lien_public':
        test.reouvrir_lien()
        messages.success(request, "Le lien a été réouvert.")
    return redirect('tests_psy:brief_liste')


@login_required
@require_test_access('brief')
def brief_delete(request, test_id):
    test = _get_test(request, test_id)
    if request.method == 'POST':
        patient_nom = test.patient.nom_complet
        test.delete()
        messages.success(request, f"Test BRIEF de {patient_nom} supprimé.")
        return redirect('tests_psy:brief_liste')
    return render(request, 'tests_psy/brief/delete.html', {'test': test, 'patient': test.patient})
