import io
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate

from tests_psy.models import (
    QuestionVineland, ReponseVineland, NoteBruteImporteeVineland, PlageItemVineland,
    SousDomain, TestVineland,
)
from tests_psy.forms.vineland import TestVinelandModeForm, NoteBruteImporteeVinelandForm
from cabinet.models import Patient
from accounts.decorators import require_test_access

from .scoring import get_patient_age, get_age_tranches, calculate_all_scores, calculate_domain_scores, find_echelle_v_mapping, get_domain_mapping
from .comparisons import generate_domain_comparisons, generate_sous_domaine_comparisons, generate_interdomaine_comparisons
from .pdf import create_pdf_styles, create_cover_page, create_scores_summary, create_comparisons_section


@login_required
@require_test_access('vineland')
def vineland_liste(request):
    """Liste de tous les tests Vineland"""
    if request.user.is_superadmin():
        tests = TestVineland.all_objects.select_related('patient', 'psychologue').order_by('-date_passation')
    else:
        tests = TestVineland.objects.select_related('patient', 'psychologue').order_by('-date_passation')

    tests = list(tests)
    for test in tests:
        # Édition possible : cabinet et lien public soumis ont des réponses item par item
        # (vineland_questionnaire, déjà pré-rempli) ; notes importées a sa propre page ;
        # lien public pas encore soumis n'a rien à éditer (le parent n'a pas encore répondu).
        if test.mode == 'importe':
            test.edit_url = reverse('tests_psy:vineland_notes_importees', kwargs={'test_id': test.id})
        elif test.mode == 'lien_public':
            test.edit_url = (
                reverse('tests_psy:vineland_questionnaire', kwargs={'test_id': test.id})
                if test.lien_soumis_le else None
            )
        else:
            test.edit_url = reverse('tests_psy:vineland_questionnaire', kwargs={'test_id': test.id})

    context = {
        'tests': tests,
        'title': 'Tests Vineland',
        'now': timezone.now(),
    }

    return render(request, 'tests_psy/vineland/liste.html', context)


@login_required
@require_test_access('vineland')
def vineland_nouveau(request, patient_id=None):
    """Créer un nouveau test Vineland - 3 modes possibles : passation en cabinet
    (comportement historique, inchangé), notes déjà calculées importées manuellement,
    ou lien public envoyé aux parents pour une passation à distance."""

    # Vérification : limite de tests Vineland atteinte ? S'applique aux 3 modes de la
    # même façon, puisque créer la ligne TestVineland consomme le quota immédiatement.
    if not request.user.is_superadmin():
        license = request.user.organization.license
        if not license.can_add_test('vineland'):
            tests_restants = license.get_tests_remaining('vineland')
            if tests_restants == 'Illimité':
                # Ne devrait jamais arriver ici, mais au cas où
                pass
            else:
                messages.error(
                    request,
                    f"Limite de tests Vineland atteinte ! Votre licence autorise {license.max_tests_vineland} tests Vineland maximum. "
                    f"Vous avez déjà créé {license.max_tests_vineland - tests_restants} tests."
                )
                return redirect('tests_psy:vineland_liste')

    form_kwargs = {'all_patients': True} if request.user.is_superadmin() else {'organization': request.user.organization}

    if request.method == 'POST':
        form = TestVinelandModeForm(request.POST, **form_kwargs)
        if form.is_valid():
            patient = form.cleaned_data['patient']
            mode = form.cleaned_data['mode']

            test = TestVineland.objects.create(
                patient=patient,
                psychologue=request.user,
                organization=request.user.organization if not request.user.is_superadmin() else patient.organization,
                date_passation=timezone.now(),
                mode=mode,
            )

            if mode == 'importe':
                messages.success(request, "Test Vineland créé - saisis les notes brutes déjà calculées.")
                return redirect('tests_psy:vineland_notes_importees', test_id=test.id)
            elif mode == 'lien_public':
                test.generate_lien_public(int(form.cleaned_data['duree_jours']))
                messages.success(request, "Lien public généré.")
                return redirect('tests_psy:vineland_lien_genere', test_id=test.id)
            else:
                messages.success(request, "Test Vineland créé avec succès !")
                return redirect('tests_psy:vineland_questionnaire', test_id=test.id)
    else:
        initial = {}
        if patient_id:
            initial['patient'] = patient_id
        form = TestVinelandModeForm(initial=initial, **form_kwargs)

    return render(request, 'tests_psy/vineland/nouveau.html', {
        'form': form,
        'title': 'Nouveau Test Vineland',
    })


def _build_questionnaire_context(test, page_number):
    """Construit page_obj (questions paginées, avec unique_id/plage_age posés sur chaque
    question) et initial_data (réponses déjà enregistrées) - partagé entre la passation en
    cabinet (vineland_questionnaire) et le lien public envoyé aux parents (public.py)."""
    questions = QuestionVineland.objects.select_related(
        'sous_domaine',
        'sous_domaine__domain'
    ).order_by('created_at')

    for question in questions:
        question.unique_id = f"{question.sous_domaine.id}_{question.numero_item}"

    plages = {
        (plage.sous_domaine_id, plage.item_debut, plage.item_fin): plage
        for plage in PlageItemVineland.objects.all()
    }
    for question in questions:
        for (sous_domaine_id, item_debut, item_fin), plage in plages.items():
            if (question.sous_domaine_id == sous_domaine_id and
                item_debut <= question.numero_item <= item_fin):
                question.plage_age = plage
                break
        else:
            question.plage_age = None

    paginator = Paginator(questions, 20)
    page_obj = paginator.get_page(page_number)

    initial_data = {}
    for response in ReponseVineland.objects.filter(test_vineland=test):
        key = f'question_{response.question.sous_domaine.id}_{response.question.numero_item}'
        initial_data[key] = response.reponse

    return page_obj, initial_data


def _save_questionnaire_post(test, post_data, page_questions):
    """Enregistre les réponses postées pour la page courante, retourne les questions de
    cette page restées sans réponse."""
    for key, value in post_data.items():
        if key.startswith('question_'):
            parts = key.split('_')
            if len(parts) >= 3:
                sous_domaine_id = int(parts[1])
                numero_item = int(parts[2])

                question = QuestionVineland.objects.get(
                    sous_domaine_id=sous_domaine_id,
                    numero_item=numero_item
                )

                ReponseVineland.objects.update_or_create(
                    question=question,
                    test_vineland=test,
                    defaults={
                        'reponse': value,
                        'organization': test.organization
                    }
                )

    unanswered_current = []
    for question in page_questions:
        key = f'question_{question.unique_id}'
        if key not in post_data:
            unanswered_current.append(f"{question.sous_domaine.name}-{question.numero_item}")
    return unanswered_current


@login_required
@require_test_access('vineland')
def vineland_questionnaire(request, test_id):
    """Questionnaire Vineland - passation en cabinet"""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    page_number = request.GET.get('page', 1)
    page_obj, initial_data = _build_questionnaire_context(test, page_number)

    if request.method == 'POST':
        action = request.POST.get('action')
        unanswered_current = _save_questionnaire_post(test, request.POST, page_obj.object_list)

        if unanswered_current:
            messages.info(request, f"Questions sans réponse sur cette page : {', '.join(map(str, unanswered_current))}")

        if action == 'previous':
            prev_page = int(page_number) - 1
            return redirect(f'{request.path}?page={prev_page}')

        elif action == 'next':
            next_page = int(page_number) + 1
            return redirect(f'{request.path}?page={next_page}')

        elif action == 'submit':
            # Vérifier que toutes les questions ont une réponse
            all_unanswered = [
                f"{q.sous_domaine.name}-{q.numero_item}"
                for q in page_obj.paginator.object_list
                if not ReponseVineland.objects.filter(test_vineland=test, question=q).exists()
            ]

            if all_unanswered:
                messages.warning(request, f"Questions sans réponse : {', '.join(map(str, all_unanswered[:10]))}")

            messages.success(request, "Test Vineland complété avec succès !")
            return redirect('tests_psy:vineland_scores', test_id=test.id)

    return render(request, 'tests_psy/vineland/questionnaire.html', {
        'test': test,
        'patient': test.patient,
        'page_obj': page_obj,
        'initial_data': initial_data,
        'is_public': False,
    })


def _champs_par_domaine(form):
    """Regroupe les champs du formulaire de notes importées par domaine, pour
    l'affichage template (évite de refaire le regroupement côté template)."""
    groupes = []
    domaine_courant = None
    for field in form:
        domaine = field.field.sous_domaine.domain
        if domaine != domaine_courant:
            groupes.append({'domaine': domaine, 'champs': []})
            domaine_courant = domaine
        groupes[-1]['champs'].append(field)
    return groupes


@login_required
@require_test_access('vineland')
def vineland_notes_importees(request, test_id):
    """Saisie/édition des notes brutes déjà calculées à la main (mode='importe') -
    pas de réponses item par item, une note brute directe par sous-domaine."""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    if test.mode != 'importe':
        messages.error(request, "Ce test n'est pas en mode notes importées.")
        return redirect('tests_psy:vineland_liste')

    if request.method == 'POST':
        initial_notes = {
            note.sous_domaine_id: note.note_brute
            for note in test.notes_brutes_importees.all()
        }
        form = NoteBruteImporteeVinelandForm(request.POST, initial_notes=initial_notes)
        if form.is_valid():
            for field_name, value in form.cleaned_data.items():
                sous_domaine_id = int(field_name.replace('sous_domaine_', ''))
                NoteBruteImporteeVineland.objects.update_or_create(
                    test_vineland=test, sous_domaine_id=sous_domaine_id,
                    defaults={'note_brute': value, 'organization': test.organization},
                )
            messages.success(request, "Notes brutes enregistrées.")
            return redirect('tests_psy:vineland_scores', test_id=test.id)
    else:
        initial_notes = {
            note.sous_domaine_id: note.note_brute
            for note in test.notes_brutes_importees.all()
        }
        form = NoteBruteImporteeVinelandForm(initial_notes=initial_notes)

    return render(request, 'tests_psy/vineland/notes_importees.html', {
        'test': test,
        'patient': test.patient,
        'form': form,
        'groupes': _champs_par_domaine(form),
    })


@login_required
@require_test_access('vineland')
def vineland_lien_genere(request, test_id):
    """Page de confirmation après génération d'un lien public - lien à copier ou à
    envoyer par WhatsApp, jamais de résultat/score sur cette page (destinée au psy)."""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    if test.mode != 'lien_public' or not test.lien_token:
        messages.error(request, "Ce test n'a pas de lien public.")
        return redirect('tests_psy:vineland_liste')

    lien_url = request.build_absolute_uri(
        reverse('tests_psy:vineland_public_questionnaire', kwargs={'token': test.lien_token})
    )

    return render(request, 'tests_psy/vineland/lien_genere.html', {
        'test': test,
        'patient': test.patient,
        'lien_url': lien_url,
    })


@login_required
@require_test_access('vineland')
def vineland_reouvrir_lien(request, test_id):
    """Réouvre un lien public déjà soumis (ou expiré) en un clic, sans confirmation -
    le jeton ne change pas, le lien déjà envoyé au parent redevient utilisable."""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    if request.method == 'POST' and test.mode == 'lien_public':
        test.reouvrir_lien()
        messages.success(request, "Le lien a été réouvert.")

    return redirect('tests_psy:vineland_liste')


@login_required
@require_test_access('vineland')
def vineland_delete(request, test_id):
    """Supprimer un test Vineland (avec confirmation) - quel que soit son mode."""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    if request.method == 'POST':
        patient_nom = test.patient.nom_complet
        test.delete()
        messages.success(request, f"Test Vineland de {patient_nom} supprimé.")
        return redirect('tests_psy:vineland_liste')

    return render(request, 'tests_psy/vineland/delete.html', {
        'test': test,
        'patient': test.patient,
    })


@login_required
@require_test_access('vineland')
def vineland_scores(request, test_id):
    """Afficher les scores bruts"""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    scores = calculate_all_scores(test)

    return render(request, 'tests_psy/vineland/scores.html', {
        'test': test,
        'patient': test.patient,
        'scores': scores
    })


@login_required
@require_test_access('vineland')
def vineland_echelle_v(request, test_id):
    """Afficher les notes échelle-V"""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    scores = calculate_all_scores(test)
    age_info = get_patient_age(test)

    echelle_v_scores = {}

    for domain_name, domain_scores in scores.items():
        if domain_name != "Comportements problématiques":
            echelle_v_scores[domain_name] = {}

            for sous_domain, score in domain_scores.items():
                sous_domain_obj = SousDomain.objects.get(name=sous_domain)
                echelle_v = find_echelle_v_mapping(sous_domain_obj, score['note_brute'], age_info)

                if echelle_v:
                    echelle_v_scores[domain_name][sous_domain] = {
                        'note_brute': score['note_brute'],
                        'note_echelle_v': echelle_v.note_echelle_v
                    }
                else:
                    echelle_v_scores[domain_name][sous_domain] = {
                        'note_brute': score['note_brute'],
                        'note_echelle_v': None,
                        'error': 'Aucune correspondance trouvée'
                    }

    return render(request, 'tests_psy/vineland/echelle_v.html', {
        'test': test,
        'patient': test.patient,
        'echelle_v_scores': echelle_v_scores,
        'age': age_info
    })


@login_required
@require_test_access('vineland')
def vineland_resultats(request, test_id):
    """Afficher tous les résultats complets"""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    scores = calculate_all_scores(test)
    age_info = get_patient_age(test)
    tranche_age, tranche_age_intervalle = get_age_tranches(age_info['years'])

    # Récupérer le niveau de confiance depuis l'URL (par défaut 90)
    niveau_confiance = int(request.GET.get('niveau_confiance', 90))
    if niveau_confiance not in [85, 90, 95]:
        niveau_confiance = 90

    # Calculer les scores complets avec le niveau choisi
    complete_scores = calculate_domain_scores(
        scores, age_info, tranche_age, tranche_age_intervalle, test,
        niveau_confiance=niveau_confiance
    )

    context = {
        'test': test,
        'patient': test.patient,
        'complete_scores': complete_scores,
        'age': age_info,
        'niveau_confiance': niveau_confiance
    }

    return render(request, 'tests_psy/vineland/resultats.html', context)


@login_required
@require_test_access('vineland')
def vineland_pdf(request, test_id):
    """Génère et retourne un PDF avec le rapport d'évaluation Vineland complet."""

    # Récupérer les paramètres d'export depuis la query string
    niveau_confiance = int(request.GET.get('niveau_confiance', 90))
    niveau_significativite = request.GET.get('niveau_significativite', '.05')

    # Validation des paramètres
    if niveau_confiance not in [85, 90, 95]:
        niveau_confiance = 90
    if niveau_significativite not in ['.05', '.01']:
        niveau_significativite = '.05'

    # Récupérer les données de base
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    patient = test.patient

    # Calculer l'âge
    age_info = get_patient_age(test)

    # Obtenir les tranches d'âge
    tranche_age, tranche_age_intervalle = get_age_tranches(age_info['years'])

    # Calculer tous les scores
    scores = calculate_all_scores(test)

    # Calculer les scores complets avec intervalles
    complete_scores = calculate_domain_scores(
        scores, age_info, tranche_age, tranche_age_intervalle, test, niveau_confiance
    )

    # Préparer la réponse HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="vineland_rapport_{patient.nom}_{datetime.now().strftime("%Y%m%d")}.pdf"'

    # Créer le document PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)

    # Obtenir les styles
    styles = create_pdf_styles()

    # Liste pour stocker tous les éléments du document
    elements = []

    # Page 1: Couverture
    create_cover_page(elements, patient, test, age_info, styles, niveau_confiance, niveau_significativite)

    # Page 2: Synthèse des scores
    create_scores_summary(elements, test, complete_scores, styles)

    # Page 3: Comparaisons par paires
    create_comparisons_section(elements, test, scores, age_info, styles, niveau_significativite)

    # Construire le PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response


@login_required
@require_test_access('vineland')
def vineland_comparaisons(request, test_id):
    """Afficher les comparaisons par paires"""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)

    # Récupérer le niveau de significativité
    niveau_significativite = request.GET.get('niveau_significativite', '.05')
    if niveau_significativite not in ['.05', '.01']:
        niveau_significativite = '.05'

    age_info = get_patient_age(test)
    age_years = age_info['years']

    # Déterminer les tranches d'âge
    tranche_age, _ = get_age_tranches(age_years)

    # Tranche d'âge spécifique pour les comparaisons
    if age_years < 3:
        tranche_age_simple = '1' if age_years < 2 else '2'
    elif age_years < 7:
        tranche_age_simple = str(age_years)
    elif age_years < 9:
        tranche_age_simple = '7-8'
    elif age_years < 12:
        tranche_age_simple = '9-11'
    elif age_years < 15:
        tranche_age_simple = '12-14'
    elif age_years < 19:
        tranche_age_simple = '15-18'
    elif age_years < 30:
        tranche_age_simple = '19-29'
    elif age_years < 50:
        tranche_age_simple = '30-49'
    else:
        tranche_age_simple = '50-90'

    # Récupérer les scores
    scores = calculate_all_scores(test)

    # Préparer les structures de données
    domaine_scores = {}
    sous_domaine_scores = {}

    # Collecter les scores de domaines et sous-domaines
    for domain_name, domain_data in scores.items():
        if domain_name != "Comportements problématiques":
            domain_note_v_sum = 0

            for sous_domain, score in domain_data.items():
                from tests_psy.models import Domain
                sous_domain_obj = SousDomain.objects.get(name=sous_domain)
                echelle_v = find_echelle_v_mapping(sous_domain_obj, score['note_brute'], age_info)

                if echelle_v:
                    sous_domaine_scores[sous_domain] = {
                        'note_echelle_v': echelle_v.note_echelle_v,
                        'domaine': domain_name,
                        'sous_domaine_obj': sous_domain_obj
                    }
                    domain_note_v_sum += echelle_v.note_echelle_v

            # Obtenir la note standard du domaine
            domain_mapping = get_domain_mapping(domain_name, domain_note_v_sum, tranche_age)
            if domain_mapping:
                domaine_scores[domain_name] = {
                    'note_standard': domain_mapping.note_standard,
                    'domaine_obj': Domain.objects.get(name=domain_name),
                    'somme_notes_v': domain_note_v_sum
                }

    # Générer les comparaisons de domaines
    domain_comparisons = generate_domain_comparisons(
        domaine_scores, tranche_age_simple, tranche_age, niveau_significativite
    )

    # Générer les comparaisons de sous-domaines par domaine
    sous_domaine_comparisons = generate_sous_domaine_comparisons(
        sous_domaine_scores, tranche_age, niveau_significativite
    )

    # Générer les comparaisons inter-domaines
    interdomaine_comparisons = generate_interdomaine_comparisons(
        sous_domaine_scores, tranche_age, niveau_significativite
    )

    return render(request, 'tests_psy/vineland/comparaisons.html', {
        'test': test,
        'patient': test.patient,
        'niveau_significativite': niveau_significativite,
        'tranche_age': tranche_age,
        'age': age_info,
        'domain_comparisons': domain_comparisons,
        'sous_domaine_comparisons': sous_domaine_comparisons,
        'interdomaine_comparisons': interdomaine_comparisons,
        'selection_comparisons': []
    })
