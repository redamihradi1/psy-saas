import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q
from dateutil.relativedelta import relativedelta
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from tests_psy.models import (
    AgeEquivalentSousDomaine, ComparaisonDomaineVineland, ComparaisonSousDomaineVineland,
    FrequenceDifferenceDomaineVineland, FrequenceDifferenceSousDomaineVineland,
    QuestionVineland, ReponseVineland, PlageItemVineland, EchelleVMapping,
    NoteDomaineVMapping, IntervaleConfianceSousDomaine, IntervaleConfianceDomaine,
    NiveauAdaptatif, TestVineland
)
from cabinet.models import Patient
from accounts.decorators import require_test_access


# ========== FONCTIONS UTILITAIRES ==========

def get_patient_age(test_vineland):
    """Calcule l'âge précis du patient au moment du test."""
    patient = test_vineland.patient
    
    # Utiliser date_passation si elle existe, sinon created_at
    if hasattr(test_vineland, 'date_passation') and test_vineland.date_passation:
        date_reference = test_vineland.date_passation.date() if hasattr(test_vineland.date_passation, 'date') else test_vineland.date_passation
    else:
        date_reference = test_vineland.created_at.date()
    
    age_at_test = relativedelta(date_reference, patient.date_naissance)
    
    return {
        'relativedelta': age_at_test,
        'years': age_at_test.years,
        'months': age_at_test.months,
        'days': age_at_test.days,
        'date_reference': date_reference
    }


def get_age_tranches(age_years):
    """Détermine les tranches d'âge pour les différents tableaux."""
    if age_years < 1:
        return None, None
    
    # Tranche d'âge pour les domaines
    if age_years < 3:
        tranche_age = '1-2'
    elif age_years < 7:
        tranche_age = '3-6'
    elif age_years < 19:
        tranche_age = '7-18'
    elif age_years < 50:
        tranche_age = '19-49'
    else:
        tranche_age = '50-90'
    
    # Tranche d'âge pour les intervalles
    if age_years == 1:
        tranche_age_intervalle = '1'
    elif age_years == 2:
        tranche_age_intervalle = '2'
    elif age_years == 3:
        tranche_age_intervalle = '3'
    elif age_years == 4:
        tranche_age_intervalle = '4'
    elif age_years == 5:
        tranche_age_intervalle = '5'
    elif age_years == 6:
        tranche_age_intervalle = '6'
    elif 7 <= age_years <= 8:
        tranche_age_intervalle = '7-8'
    elif 9 <= age_years <= 11:
        tranche_age_intervalle = '9-11'
    elif 12 <= age_years <= 14:
        tranche_age_intervalle = '12-14'
    elif 15 <= age_years <= 18:
        tranche_age_intervalle = '15-18'
    elif 19 <= age_years <= 29:
        tranche_age_intervalle = '19-29'
    elif 30 <= age_years <= 49:
        tranche_age_intervalle = '30-49'
    else:
        tranche_age_intervalle = '50-90'
    
    return tranche_age, tranche_age_intervalle

def calculate_item_plancher(reponses_sous_domaine):
    """Calcule l'item plancher (4 réponses consécutives de 2)"""
    consecutive_count = 0
    for reponse in reponses_sous_domaine:
        if reponse.reponse == '2':
            consecutive_count += 1
            if consecutive_count == 4:
                return reponse.question.numero_item - 3  # -3 car on veut le premier des 4
        else:
            consecutive_count = 0
    return 0


def calculate_all_scores(test_vineland):
    """
    Calcule tous les scores bruts pour un test Vineland.
    Utilise la VRAIE logique Vineland avec item plancher.
    """
    from collections import defaultdict
    from tests_psy.models import Domain
    
    # Récupérer toutes les réponses du test, triées par numéro d'item
    reponses = ReponseVineland.objects.filter(
        test_vineland=test_vineland
    ).select_related(
        'question', 
        'question__sous_domaine', 
        'question__sous_domaine__domain'
    ).order_by(
        'question__sous_domaine__domain',
        'question__sous_domaine',
        'question__numero_item'
    )
    
    # Grouper les réponses par domaine > sous-domaine
    scores = {}
    
    # Récupérer tous les domaines
    domains = Domain.objects.prefetch_related('sous_domaines').all()
    
    for domain in domains:
        scores[domain.name] = {}
        
        for sous_domaine in domain.sous_domaines.all():
            # Filtrer les réponses pour ce sous-domaine
            reponses_sd = [r for r in reponses if r.question.sous_domaine == sous_domaine]
            
            # Calculer l'item plancher
            item_plancher = calculate_item_plancher(reponses_sd)
            
            # Compter NSP/sans réponse
            nsp_count = sum(1 for r in reponses_sd if r.reponse in ['NSP', '', None, '?'])
            
            # Compter N/A
            na_count = sum(1 for r in reponses_sd if r.reponse == 'NA')
            
            # Somme des items APRÈS l'item plancher (uniquement 1 et 2)
            sum_1_2 = sum(
                int(r.reponse) 
                for r in reponses_sd 
                if r.question.numero_item > item_plancher 
                and r.reponse in ['1', '2']
            )
            
            # Calcul de la note brute selon Vineland
            # Note brute = (item_plancher × 2) + somme(1,2 après plancher) + NSP
            note_brute = (item_plancher * 2) + sum_1_2 + nsp_count
            
            # Vérifier si à refaire (plus de 2 NSP)
            a_refaire = nsp_count > 2
            
            scores[domain.name][sous_domaine.name] = {
                'note_brute': note_brute,
                'item_plancher': item_plancher,
                'nsp_count': nsp_count,
                'na_count': na_count,
                'sum_1_2': sum_1_2,
                'a_refaire': a_refaire,
                'items': [
                    {
                        'numero': r.question.numero_item,
                        'valeur': r.reponse
                    }
                    for r in reponses_sd
                ]
            }
    
    return scores

def find_echelle_v_mapping(sous_domain_obj, note_brute, age_info):
    """Trouve le mapping échelle-v correspondant à la note brute et l'âge."""
    age_years = age_info['years']
    age_months = age_info['months']
    age_days = age_info['days']
    
    mappings = EchelleVMapping.objects.filter(
        sous_domaine=sous_domain_obj,
        note_brute_min__lte=note_brute,
        note_brute_max__gte=note_brute
    )
    
    for mapping in mappings:
        if mapping.age_debut_jour is not None and mapping.age_fin_jour is not None:
            # Vérification avec jours
            if ((mapping.age_debut_annee < age_years or 
                (mapping.age_debut_annee == age_years and mapping.age_debut_mois <= age_months) or
                (mapping.age_debut_annee == age_years and mapping.age_debut_mois == age_months and mapping.age_debut_jour <= age_days))):
                if ((mapping.age_fin_annee > age_years or
                    (mapping.age_fin_annee == age_years and mapping.age_fin_mois >= age_months) or
                    (mapping.age_fin_annee == age_years and mapping.age_fin_mois == age_months and mapping.age_fin_jour >= age_days))):
                    return mapping
        else:
            # Vérification sans jours
            if ((mapping.age_debut_annee < age_years or 
                (mapping.age_debut_annee == age_years and mapping.age_debut_mois <= age_months))):
                if ((mapping.age_fin_annee > age_years or
                    (mapping.age_fin_annee == age_years and mapping.age_fin_mois >= age_months))):
                    return mapping
    return None


def get_domain_mapping(domain_name, domain_note_v_sum, tranche_age):
    """Trouve le mapping de domaine correspondant."""
    filter_kwargs = {'tranche_age': tranche_age}
    
    if 'Communication' in domain_name:
        filter_kwargs.update({
            'communication_min__lte': domain_note_v_sum,
            'communication_max__gte': domain_note_v_sum
        })
    elif 'Vie quotidienne' in domain_name:
        filter_kwargs.update({
            'vie_quotidienne_min__lte': domain_note_v_sum,
            'vie_quotidienne_max__gte': domain_note_v_sum
        })
    elif 'Socialisation' in domain_name:
        filter_kwargs.update({
            'socialisation_min__lte': domain_note_v_sum,
            'socialisation_max__gte': domain_note_v_sum
        })
    elif 'Motricité' in domain_name:
        filter_kwargs.update({
            'motricite_min__lte': domain_note_v_sum,
            'motricite_max__gte': domain_note_v_sum
        })
    
    return NoteDomaineVMapping.objects.filter(**filter_kwargs).first()


def calculate_domain_scores(scores, age_info, tranche_age, tranche_age_intervalle, test_vineland, niveau_confiance=90):
    """Calcule les scores complets pour tous les domaines."""
    from tests_psy.models import Domain, SousDomain
    
    complete_scores = []
    
    for domain_name, domain_scores_data in scores.items():
        if domain_name != "Comportements problématiques":
            domain_data = {
                'name': domain_name,
                'name_slug': domain_name.replace(' ', '_'),
                'niveau_confiance': niveau_confiance,
                'sous_domaines': [],
                'domain_score': None
            }
            
            domain_note_v_sum = 0
            
            # Traiter chaque sous-domaine
            for sous_domain, score in domain_scores_data.items():
                sous_domain_obj = SousDomain.objects.get(name=sous_domain)
                
                # Trouver le mapping échelle-v
                echelle_v = find_echelle_v_mapping(sous_domain_obj, score['note_brute'], age_info)
                
                if echelle_v:
                    domain_note_v_sum += echelle_v.note_echelle_v
                    
                    # Ajouter les données du sous-domaine
                    sous_domaine_data = {
                        'name': sous_domain,
                        'note_brute': score['note_brute'],
                        'note_echelle_v': echelle_v.note_echelle_v
                    }
                    
                    # Ajouter l'intervalle de confiance si demandé
                    if niveau_confiance:
                        intervalle = IntervaleConfianceSousDomaine.objects.filter(
                            age=tranche_age_intervalle,
                            niveau_confiance=niveau_confiance,
                            sous_domaine=sous_domain_obj
                        ).first()
                        sous_domaine_data['intervalle'] = intervalle.intervalle if intervalle else None
                    
                    # Ajouter le niveau adaptatif si nécessaire
                    niveau_adaptatif = NiveauAdaptatif.objects.filter(
                        echelle_v_min__lte=echelle_v.note_echelle_v,
                        echelle_v_max__gte=echelle_v.note_echelle_v
                    ).first()
                    if niveau_adaptatif:
                        sous_domaine_data['niveau_adaptatif'] = niveau_adaptatif.get_niveau_display()
                    
                    # Ajouter l'âge équivalent si nécessaire
                    age_equivalent = AgeEquivalentSousDomaine.objects.filter(
                        sous_domaine=sous_domain_obj,
                        note_brute_min__lte=score['note_brute']
                    ).filter(
                        Q(note_brute_max__isnull=True, note_brute_min=score['note_brute']) |
                        Q(note_brute_max__isnull=False, note_brute_max__gte=score['note_brute'])
                    ).first()
                    if age_equivalent:
                        sous_domaine_data['age_equivalent'] = age_equivalent.get_age_equivalent_display()
                    
                    domain_data['sous_domaines'].append(sous_domaine_data)
            
            # Trouver le mapping du domaine
            domain_mapping = get_domain_mapping(domain_name, domain_note_v_sum, tranche_age)
            
            if domain_mapping:
                domain_data['domain_score'] = {
                    'somme_notes_v': domain_note_v_sum,
                    'note_standard': domain_mapping.note_standard,
                    'rang_percentile': domain_mapping.rang_percentile
                }
                
                # Ajouter l'intervalle de confiance du domaine si demandé
                if niveau_confiance:
                    intervalle_domaine = IntervaleConfianceDomaine.objects.filter(
                        age=tranche_age_intervalle,
                        niveau_confiance=niveau_confiance,
                        domain__name=domain_name
                    ).first()
                    if intervalle_domaine:
                        domain_data['domain_score']['intervalle'] = intervalle_domaine.intervalle
                        domain_data['domain_score']['note_composite'] = intervalle_domaine.note_composite
                
                # Ajouter le niveau adaptatif du domaine
                niveau_adaptatif_domain = NiveauAdaptatif.objects.filter(
                    note_standard_min__lte=domain_mapping.note_standard,
                    note_standard_max__gte=domain_mapping.note_standard
                ).first()
                if niveau_adaptatif_domain:
                    domain_data['domain_score']['niveau_adaptatif'] = niveau_adaptatif_domain.get_niveau_display()
            
            complete_scores.append(domain_data)
    
    return complete_scores


# ========== VUES PRINCIPALES ==========

@login_required
@require_test_access('vineland')
def vineland_liste(request):
    """Liste de tous les tests Vineland"""
    if request.user.is_superadmin():
        tests = TestVineland.all_objects.select_related('patient', 'psychologue').order_by('-date_passation')
    else:
        tests = TestVineland.objects.select_related('patient', 'psychologue').order_by('-date_passation')
    
    context = {
        'tests': tests,
        'title': 'Tests Vineland'
    }
    
    return render(request, 'tests_psy/vineland/liste.html', context)


@login_required
@require_test_access('vineland')
def vineland_nouveau(request, patient_id=None):
    """Créer un nouveau test Vineland"""
    
    # 🆕 VÉRIFICATION : Limite de tests Vineland atteinte ?
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
    
    # Si patient_id fourni, le sélectionner
    patient = None
    if patient_id:
        if request.user.is_superadmin():
            patient = get_object_or_404(Patient.all_objects, id=patient_id)
        else:
            patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
    
    # Récupérer tous les patients
    if request.user.is_superadmin():
        patients = Patient.all_objects.all()
    else:
        patients = Patient.objects.filter(organization=request.user.organization)
    
    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        
        if request.user.is_superadmin():
            patient = get_object_or_404(Patient.all_objects, id=patient_id)
        else:
            patient = get_object_or_404(Patient, id=patient_id, organization=request.user.organization)
        
        # Créer le test
        test = TestVineland.objects.create(
            patient=patient,
            psychologue=request.user,
            organization=request.user.organization if not request.user.is_superadmin() else patient.organization,
            date_passation=timezone.now()
        )
        
        messages.success(request, "Test Vineland créé avec succès !")
        return redirect('tests_psy:vineland_questionnaire', test_id=test.id)
    
    context = {
        'patients': patients,
        'patient': patient,
        'title': 'Nouveau Test Vineland'
    }
    
    return render(request, 'tests_psy/vineland/nouveau.html', context)


@login_required
@require_test_access('vineland')
def vineland_questionnaire(request, test_id):
    """Questionnaire Vineland"""
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)
    
    # Récupérer les questions avec leurs relations
    questions = QuestionVineland.objects.select_related(
        'sous_domaine',
        'sous_domaine__domain'
    ).order_by('created_at')

    # Génération d'une clé unique pour chaque question
    for question in questions:
        question.unique_id = f"{question.sous_domaine.id}_{question.numero_item}"

    # Récupérer toutes les plages d'âge
    plages = {
        (plage.sous_domaine_id, plage.item_debut, plage.item_fin): plage 
        for plage in PlageItemVineland.objects.all()
    }

    # Associer les plages d'âge aux questions
    for question in questions:
        for (sous_domaine_id, item_debut, item_fin), plage in plages.items():
            if (question.sous_domaine_id == sous_domaine_id and 
                item_debut <= question.numero_item <= item_fin):
                question.plage_age = plage
                break
        else:
            question.plage_age = None

    paginator = Paginator(questions, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Gérer les données initiales depuis les réponses déjà sauvegardées
    initial_data = {}
    existing_responses = ReponseVineland.objects.filter(test_vineland=test)
    for response in existing_responses:
        key = f'question_{response.question.sous_domaine.id}_{response.question.numero_item}'
        initial_data[key] = response.reponse

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Sauvegarder les réponses
        for key, value in request.POST.items():
            if key.startswith('question_'):
                parts = key.split('_')
                if len(parts) >= 3:
                    sous_domaine_id = int(parts[1])
                    numero_item = int(parts[2])
                    
                    question = QuestionVineland.objects.get(
                        sous_domaine_id=sous_domaine_id,
                        numero_item=numero_item
                    )
                    
                    # Mettre à jour ou créer la réponse
                    reponse_obj, created = ReponseVineland.objects.update_or_create(
                        question=question,
                        test_vineland=test,
                        defaults={
                            'reponse': value,
                            'organization': test.organization
                        }
                    )

        # Vérifier les questions non répondues sur la page courante
        current_page_questions = page_obj.object_list
        unanswered_current = []
        for question in current_page_questions:
            key = f'question_{question.unique_id}'
            if key not in request.POST:
                unanswered_current.append(f"{question.sous_domaine.name}-{question.numero_item}")

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
            all_unanswered = []
            for question in questions:
                if not ReponseVineland.objects.filter(
                    test_vineland=test,
                    question=question
                ).exists():
                    all_unanswered.append(f"{question.sous_domaine.name}-{question.numero_item}")

            if all_unanswered:
                messages.warning(request, f"Questions sans réponse : {', '.join(map(str, all_unanswered[:10]))}")

            messages.success(request, "Test Vineland complété avec succès !")
            return redirect('tests_psy:vineland_scores', test_id=test.id)

    return render(request, 'tests_psy/vineland/questionnaire.html', {
        'test': test,
        'patient': test.patient,
        'page_obj': page_obj,
        'initial_data': initial_data,
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
    
    # DEBUG - Afficher la structure
    print("="*50)
    print("STRUCTURE DES SCORES:")
    for key, value in scores.items():
        print(f"\n{key}: {type(value)}")
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                print(f"  - {sub_key}: {type(sub_value)}")
    print("="*50)
    
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
    
    from tests_psy.models import SousDomain
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
    
    # 🆕 Récupérer le niveau de confiance depuis l'URL (par défaut 90)
    niveau_confiance = int(request.GET.get('niveau_confiance', 90))
    if niveau_confiance not in [85, 90, 95]:
        niveau_confiance = 90
    
    # Calculer les scores complets avec le niveau choisi
    complete_scores = calculate_domain_scores(
        scores, age_info, tranche_age, tranche_age_intervalle, test, 
        niveau_confiance=niveau_confiance  # ← DYNAMIQUE !
    )
    
    context = {
        'test': test,
        'patient': test.patient,
        'complete_scores': complete_scores,
        'age': age_info,
        'niveau_confiance': niveau_confiance  # 🆕 Pour afficher dans le template
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
    reponses = ReponseVineland.objects.filter(test_vineland=test).select_related('question')
    
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


# ========== FONCTIONS UTILITAIRES PDF ==========

def create_pdf_styles():
    """Crée et retourne les styles nécessaires pour le PDF."""
    styles = getSampleStyleSheet()
    
    # Style pour les questions
    question_style = ParagraphStyle(
        name='QuestionStyle',
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        wordWrap='CJK',
        alignment=0
    )
    
    # Style pour les cellules compactes
    compact_cell_style = ParagraphStyle(
        name='CompactCell',
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        wordWrap='CJK',
        alignment=0
    )
    
    return {
        'title': styles["Heading1"],
        'subtitle': styles["Heading2"],
        'heading3': styles["Heading3"],
        'normal': styles["Normal"],
        'question': question_style,
        'compact': compact_cell_style
    }


def create_cover_page(elements, patient, test, age_info, styles, niveau_confiance=90, niveau_significativite='.05'):
    """Crée la page de couverture du rapport."""
    elements.append(Paragraph("Rapport d'évaluation Vineland-II", styles['title']))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"Patient: {patient.nom_complet}", styles['subtitle']))
    elements.append(Paragraph(f"Date de naissance: {patient.date_naissance.strftime('%d/%m/%Y')}", styles['normal']))
    elements.append(Paragraph(
        f"Âge au moment du test: {age_info['years']} ans, {age_info['months']} mois, {age_info['days']} jours",
        styles['normal']
    ))
    elements.append(Paragraph(f"Date d'évaluation: {test.date_passation.strftime('%d/%m/%Y')}", styles['normal']))
    elements.append(Paragraph(
        f"Évaluateur: {test.psychologue.get_full_name() or test.psychologue.username}",
        styles['normal']
    ))
    
    # Paramètres d'analyse
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("Paramètres d'analyse", styles['subtitle']))
    elements.append(Paragraph(f"Niveau de confiance: {niveau_confiance}%", styles['normal']))
    elements.append(Paragraph(f"Niveau de significativité: {niveau_significativite}", styles['normal']))
    
    elements.append(PageBreak())


def create_scores_summary(elements, test, complete_scores, styles):
    """Crée la section de synthèse des résultats."""
    elements.append(Paragraph("Synthèse des Résultats", styles['title']))
    elements.append(Spacer(1, 0.5*cm))
    
    for domain in complete_scores:
        elements.append(Paragraph(f"Domaine: {domain['name']}", styles['subtitle']))
        
        # Tableau du score de domaine
        if domain['domain_score']:
            create_domain_score_table(elements, domain, styles)
            elements.append(Spacer(1, 0.5*cm))
        
        # Tableau des sous-domaines
        create_subdomain_score_table(elements, domain, styles)
        elements.append(Spacer(1, 1*cm))
    
    elements.append(PageBreak())


def create_domain_score_table(elements, domain, styles):
    """Crée le tableau des scores de domaine."""
    domain_score_data = [
        ["Somme notes-V", "Note standard", "Rang percentile", "Intervalle", "Niveau adaptatif"],
        [
            str(domain['domain_score']['somme_notes_v']),
            str(domain['domain_score']['note_standard'] or "-"),
            str(domain['domain_score']['rang_percentile'] or "-"),
            f"±{domain['domain_score'].get('intervalle', '-')}" if domain['domain_score'].get('intervalle') else "-",
            domain['domain_score'].get('niveau_adaptatif', 'Non disponible')
        ]
    ]
    
    table = Table(domain_score_data, colWidths=[3*cm, 3*cm, 3*cm, 2.5*cm, 3.5*cm])
    table.setStyle(get_score_table_style())
    elements.append(table)


def create_subdomain_score_table(elements, domain, styles):
    """Crée le tableau des scores de sous-domaines."""
    data = [["Sous-domaine", "Note brute", "Note échelle-V", "Intervalle", "Niveau adaptatif", "Âge équivalent"]]
    
    for sous_domain in domain['sous_domaines']:
        data.append([
            sous_domain['name'],
            str(sous_domain['note_brute']),
            str(sous_domain['note_echelle_v']),
            f"±{sous_domain.get('intervalle', '-')}" if sous_domain.get('intervalle') else "-",
            sous_domain.get('niveau_adaptatif', 'Non disponible'),
            sous_domain.get('age_equivalent', '-')
        ])
    
    table = Table(data, colWidths=[4*cm, 2*cm, 2*cm, 2*cm, 3*cm, 2.5*cm])
    table.setStyle(get_score_table_style())
    elements.append(table)


def get_score_table_style():
    """Retourne le style pour les tableaux de scores."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])


def create_comparisons_section(elements, test, scores, age_info, styles, niveau_significativite='.05'):
    """Crée la section des comparaisons par paires."""
    from tests_psy.models import Domain, SousDomain
    
    elements.append(Paragraph("Comparaisons par paires", styles['title']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Ajouter une note sur le niveau de significativité utilisé
    elements.append(Paragraph(f"Niveau de significativité utilisé: {niveau_significativite}", styles['normal']))
    elements.append(Spacer(1, 0.3*cm))
    
    tranche_age, _ = get_age_tranches(age_info['years'])
    tranche_age_simple = get_simple_age_range(age_info['years'])
    
    # Collecter les scores
    domaine_scores = {}
    sous_domaine_scores = {}
    
    for domain_name, domain_data in scores.items():
        if domain_name != "Comportements problématiques":
            domain_note_v_sum = 0
            
            for sous_domain, score in domain_data.items():
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
    
    # Générer et afficher les comparaisons de domaines
    domain_comparisons = generate_domain_comparisons(
        domaine_scores, tranche_age_simple, tranche_age, niveau_significativite
    )
    if domain_comparisons:
        create_domain_comparison_table(elements, domain_comparisons, styles)
        elements.append(Spacer(1, 1*cm))
    
    # Générer et afficher les comparaisons de sous-domaines
    sous_domaine_comparisons = generate_sous_domaine_comparisons(
        sous_domaine_scores, tranche_age, niveau_significativite
    )
    for domaine, comparisons in sous_domaine_comparisons.items():
        if comparisons:
            create_subdomain_comparison_table(elements, domaine, comparisons, styles)
            elements.append(Spacer(1, 1*cm))
    
    # Générer et afficher les comparaisons inter-domaines
    interdomaine_comparisons = generate_interdomaine_comparisons(
        sous_domaine_scores, tranche_age, niveau_significativite
    )
    if interdomaine_comparisons:
        create_interdomain_comparison_table(elements, interdomaine_comparisons, styles)


def get_simple_age_range(age_years):
    """Détermine la tranche d'âge simple pour les comparaisons."""
    if age_years < 3:
        return '1' if age_years < 2 else '2'
    elif age_years < 7:
        return str(age_years)
    elif age_years < 9:
        return '7-8'
    elif age_years < 12:
        return '9-11'
    elif age_years < 15:
        return '12-14'
    elif age_years < 19:
        return '15-18'
    elif age_years < 30:
        return '19-29'
    elif age_years < 50:
        return '30-49'
    else:
        return '50-90'


def create_domain_comparison_table(elements, comparisons, styles):
    """Crée le tableau des comparaisons de domaines."""
    elements.append(Paragraph("Comparaisons des domaines", styles['subtitle']))
    elements.append(Spacer(1, 0.3*cm))
    
    data = [["Domaine 1", "Note", "<,>,=", "Note", "Domaine 2", "Diff.", "Signif.", "Fréq."]]
    
    for comp in comparisons:
        data.append([
            comp['domaine1'],
            str(comp['note1']),
            comp['signe'],
            str(comp['note2']),
            comp['domaine2'],
            str(comp['difference']),
            "✓" if comp['est_significatif'] else "-",
            comp['frequence'] if comp['frequence'] else "-"
        ])
    
    table = Table(data, colWidths=[3*cm, 1.5*cm, 1*cm, 1.5*cm, 3*cm, 1.5*cm, 1.5*cm, 1.5*cm])
    table.setStyle(get_comparison_table_style())
    elements.append(table)


def create_subdomain_comparison_table(elements, domaine, comparisons, styles):
    """Crée le tableau des comparaisons de sous-domaines."""
    elements.append(Paragraph(f"Comparaisons - {domaine}", styles['subtitle']))
    elements.append(Spacer(1, 0.3*cm))
    
    data = [["Sous-domaine 1", "Note", "<,>,=", "Note", "Sous-domaine 2", "Diff.", "Signif.", "Fréq."]]
    
    for comp in comparisons:
        data.append([
            comp['sous_domaine1'],
            str(comp['note1']),
            comp['signe'],
            str(comp['note2']),
            comp['sous_domaine2'],
            str(comp['difference']),
            "✓" if comp['est_significatif'] else "-",
            comp['frequence'] if comp['frequence'] else "-"
        ])
    
    table = Table(data, colWidths=[3*cm, 1.5*cm, 1*cm, 1.5*cm, 3*cm, 1.5*cm, 1.5*cm, 1.5*cm])
    table.setStyle(get_comparison_table_style())
    elements.append(table)


def create_interdomain_comparison_table(elements, comparisons, styles):
    """Crée le tableau des comparaisons inter-domaines."""
    elements.append(Paragraph("Comparaisons inter-domaines", styles['subtitle']))
    elements.append(Spacer(1, 0.3*cm))
    
    data = [[
        Paragraph("<b>SD 1</b>", styles['compact']),
        Paragraph("<b>Dom.</b>", styles['compact']),
        Paragraph("<b>Note</b>", styles['compact']),
        Paragraph("<b><,>,=</b>", styles['compact']),
        Paragraph("<b>Note</b>", styles['compact']),
        Paragraph("<b>SD 2</b>", styles['compact']),
        Paragraph("<b>Dom.</b>", styles['compact']),
        Paragraph("<b>Diff.</b>", styles['compact']),
        Paragraph("<b>Sign.</b>", styles['compact']),
        Paragraph("<b>Fréq.</b>", styles['compact'])
    ]]
    
    for comp in comparisons:
        data.append([
            Paragraph(comp['sous_domaine1'], styles['compact']),
            Paragraph(comp['domaine1'], styles['compact']),
            Paragraph(str(comp['note1']), styles['compact']),
            Paragraph(comp['signe'], styles['compact']),
            Paragraph(str(comp['note2']), styles['compact']),
            Paragraph(comp['sous_domaine2'], styles['compact']),
            Paragraph(comp['domaine2'], styles['compact']),
            Paragraph(str(comp['difference']), styles['compact']),
            Paragraph("✓" if comp['est_significatif'] else "-", styles['compact']),
            Paragraph(comp['frequence'] if comp['frequence'] else "-", styles['compact'])
        ])
    
    table = Table(data, colWidths=[2.2*cm, 2.2*cm, 1*cm, 0.8*cm, 1*cm, 2.2*cm, 2.2*cm, 1.2*cm, 1.2*cm, 1.2*cm])
    table.setStyle(get_comparison_table_style())
    elements.append(table)


def get_comparison_table_style():
    """Retourne le style pour les tableaux de comparaisons."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (3, -1), 'CENTER'),
        ('ALIGN', (5, 1), (7, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (2, 1), (2, -1), colors.lightgrey),
    ])



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
                from tests_psy.models import SousDomain, Domain
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


def generate_domain_comparisons(domaine_scores, tranche_age_simple, tranche_age, niveau_significativite):
    """Génère les comparaisons entre domaines"""
    comparisons = []
    domain_names = list(domaine_scores.keys())
    
    for i in range(len(domain_names)):
        for j in range(i + 1, len(domain_names)):
            domain1 = domain_names[i]
            domain2 = domain_names[j]
            
            note1 = domaine_scores[domain1]['note_standard']
            note2 = domaine_scores[domain2]['note_standard']
            
            difference = abs(note1 - note2)
            
            if note1 > note2:
                signe = '>'
            elif note1 < note2:
                signe = '<'
            else:
                signe = '='
            
            # Chercher la différence requise pour la significativité
            try:
                comparaison_db = ComparaisonDomaineVineland.objects.filter(
                    tranche_age=tranche_age,
                    niveau_significativite=niveau_significativite
                ).first()
                
                if comparaison_db:
                    # Obtenir la différence requise selon les domaines
                    diff_requise = get_domain_difference_requise(
                        comparaison_db, domain1, domain2
                    )
                    est_significatif = difference >= diff_requise if diff_requise else False
                else:
                    est_significatif = False
                    diff_requise = None
            except:
                est_significatif = False
                diff_requise = None
            
            # Chercher la fréquence
            try:
                freq_db = FrequenceDifferenceDomaineVineland.objects.filter(
                    tranche_age=tranche_age_simple
                ).first()
                
                if freq_db:
                    frequence = get_domain_frequence(
                        freq_db, domain1, domain2, difference
                    )
                else:
                    frequence = None
            except:
                frequence = None
            
            comparisons.append({
                'domaine1': domain1,
                'note1': note1,
                'signe': signe,
                'note2': note2,
                'domaine2': domain2,
                'difference': difference,
                'est_significatif': est_significatif,
                'difference_requise': diff_requise,
                'frequence': frequence
            })
    
    return comparisons


def generate_sous_domaine_comparisons(sous_domaine_scores, tranche_age, niveau_significativite):
    """Génère les comparaisons entre sous-domaines d'un même domaine"""
    comparisons_by_domain = {}
    
    # Grouper par domaine
    domaines = {}
    for sous_domain, data in sous_domaine_scores.items():
        domain = data['domaine']
        if domain not in domaines:
            domaines[domain] = []
        domaines[domain].append({
            'name': sous_domain,
            'note': data['note_echelle_v'],
            'obj': data['sous_domaine_obj']
        })
    
    # Comparer les sous-domaines au sein de chaque domaine
    for domain, sous_domains in domaines.items():
        comparisons = []
        
        for i in range(len(sous_domains)):
            for j in range(i + 1, len(sous_domains)):
                sd1 = sous_domains[i]
                sd2 = sous_domains[j]
                
                note1 = sd1['note']
                note2 = sd2['note']
                
                difference = abs(note1 - note2)
                
                if note1 > note2:
                    signe = '>'
                elif note1 < note2:
                    signe = '<'
                else:
                    signe = '='
                
                # Chercher la différence requise pour la significativité
                try:
                    comparaison_db = ComparaisonSousDomaineVineland.objects.filter(
                        sous_domaine_1=sd1['obj'],
                        sous_domaine_2=sd2['obj'],
                        tranche_age=tranche_age,
                        niveau_significativite=niveau_significativite
                    ).first()
                    
                    # Essayer aussi dans l'autre sens
                    if not comparaison_db:
                        comparaison_db = ComparaisonSousDomaineVineland.objects.filter(
                            sous_domaine_1=sd2['obj'],
                            sous_domaine_2=sd1['obj'],
                            tranche_age=tranche_age,
                            niveau_significativite=niveau_significativite
                        ).first()
                    
                    if comparaison_db:
                        diff_requise = comparaison_db.difference_requise
                        est_significatif = difference >= diff_requise
                    else:
                        est_significatif = False
                        diff_requise = None
                except:
                    est_significatif = False
                    diff_requise = None
                
                # Chercher la fréquence
                try:
                    freq_db = FrequenceDifferenceSousDomaineVineland.objects.filter(
                        sous_domaine_1=sd1['obj'],
                        sous_domaine_2=sd2['obj'],
                        tranche_age=tranche_age
                    ).first()
                    
                    if not freq_db:
                        freq_db = FrequenceDifferenceSousDomaineVineland.objects.filter(
                            sous_domaine_1=sd2['obj'],
                            sous_domaine_2=sd1['obj'],
                            tranche_age=tranche_age
                        ).first()
                    
                    if freq_db:
                        frequence = get_sous_domain_frequence(freq_db, difference)
                    else:
                        frequence = None
                except:
                    frequence = None
                
                comparisons.append({
                    'sous_domaine1': sd1['name'],
                    'note1': note1,
                    'signe': signe,
                    'note2': note2,
                    'sous_domaine2': sd2['name'],
                    'difference': difference,
                    'est_significatif': est_significatif,
                    'difference_requise': diff_requise,
                    'frequence': frequence
                })
        
        if comparisons:
            comparisons_by_domain[domain] = comparisons
    
    return comparisons_by_domain


def generate_interdomaine_comparisons(sous_domaine_scores, tranche_age, niveau_significativite):
    """Génère les comparaisons entre sous-domaines de domaines différents"""
    comparisons = []
    sous_domains_list = []
    
    for sous_domain, data in sous_domaine_scores.items():
        sous_domains_list.append({
            'name': sous_domain,
            'note': data['note_echelle_v'],
            'domaine': data['domaine'],
            'obj': data['sous_domaine_obj']
        })
    
    # Comparer tous les sous-domaines entre eux (inter-domaines uniquement)
    for i in range(len(sous_domains_list)):
        for j in range(i + 1, len(sous_domains_list)):
            sd1 = sous_domains_list[i]
            sd2 = sous_domains_list[j]
            
            # Uniquement les comparaisons inter-domaines
            if sd1['domaine'] == sd2['domaine']:
                continue
            
            note1 = sd1['note']
            note2 = sd2['note']
            
            difference = abs(note1 - note2)
            
            if note1 > note2:
                signe = '>'
            elif note1 < note2:
                signe = '<'
            else:
                signe = '='
            
            # Chercher la différence requise pour la significativité
            try:
                comparaison_db = ComparaisonSousDomaineVineland.objects.filter(
                    sous_domaine_1=sd1['obj'],
                    sous_domaine_2=sd2['obj'],
                    tranche_age=tranche_age,
                    niveau_significativite=niveau_significativite
                ).first()
                
                if not comparaison_db:
                    comparaison_db = ComparaisonSousDomaineVineland.objects.filter(
                        sous_domaine_1=sd2['obj'],
                        sous_domaine_2=sd1['obj'],
                        tranche_age=tranche_age,
                        niveau_significativite=niveau_significativite
                    ).first()
                
                if comparaison_db:
                    diff_requise = comparaison_db.difference_requise
                    est_significatif = difference >= diff_requise
                else:
                    est_significatif = False
                    diff_requise = None
            except:
                est_significatif = False
                diff_requise = None
            
            # Chercher la fréquence
            try:
                freq_db = FrequenceDifferenceSousDomaineVineland.objects.filter(
                    sous_domaine_1=sd1['obj'],
                    sous_domaine_2=sd2['obj'],
                    tranche_age=tranche_age
                ).first()
                
                if not freq_db:
                    freq_db = FrequenceDifferenceSousDomaineVineland.objects.filter(
                        sous_domaine_1=sd2['obj'],
                        sous_domaine_2=sd1['obj'],
                        tranche_age=tranche_age
                    ).first()
                
                if freq_db:
                    frequence = get_sous_domain_frequence(freq_db, difference)
                else:
                    frequence = None
            except:
                frequence = None
            
            comparisons.append({
                'sous_domaine1': sd1['name'],
                'domaine1': sd1['domaine'],
                'note1': note1,
                'signe': signe,
                'note2': note2,
                'sous_domaine2': sd2['name'],
                'domaine2': sd2['domaine'],
                'difference': difference,
                'est_significatif': est_significatif,
                'difference_requise': diff_requise,
                'frequence': frequence
            })
    
    return comparisons



# ========== FONCTIONS UTILITAIRES POUR LES COMPARAISONS ==========

def extract_number(value):
    """Extrait la partie numérique d'une valeur de fréquence."""
    if not value:
        return 9999
    if value.endswith('+'):
        return int(value[:-1])
    elif '-' in value:
        return int(value.split('-')[0])
    else:
        try:
            return int(value)
        except ValueError:
            return 9999


def get_frequency_percentage(difference, freq):
    """Détermine le pourcentage de fréquence basé sur la différence."""
    if not freq:
        return None
    
    if freq.frequence_5 and difference >= extract_number(freq.frequence_5):
        return "5%"
    elif freq.frequence_10 and difference >= extract_number(freq.frequence_10):
        return "10%"
    elif freq.frequence_16 and difference >= extract_number(freq.frequence_16):
        return "16%"
    return None


def find_domain_comparison(domain1_obj, domain2_obj, tranche_age, niveau_significativite):
    """Trouve la comparaison entre deux domaines."""
    try:
        return ComparaisonDomaineVineland.objects.get(
            age=tranche_age,
            niveau_significativite=niveau_significativite,
            domaine1=domain1_obj,
            domaine2=domain2_obj
        )
    except ComparaisonDomaineVineland.DoesNotExist:
        try:
            return ComparaisonDomaineVineland.objects.get(
                age=tranche_age,
                niveau_significativite=niveau_significativite,
                domaine1=domain2_obj,
                domaine2=domain1_obj
            )
        except ComparaisonDomaineVineland.DoesNotExist:
            return None


def find_domain_frequency(domain1_obj, domain2_obj, tranche_age):
    """Trouve les fréquences de différence entre deux domaines."""
    try:
        return FrequenceDifferenceDomaineVineland.objects.get(
            age=tranche_age,
            domaine1=domain1_obj,
            domaine2=domain2_obj
        )
    except FrequenceDifferenceDomaineVineland.DoesNotExist:
        try:
            return FrequenceDifferenceDomaineVineland.objects.get(
                age=tranche_age,
                domaine1=domain2_obj,
                domaine2=domain1_obj
            )
        except FrequenceDifferenceDomaineVineland.DoesNotExist:
            return None


def find_sous_domaine_comparison(sous_domaine1_obj, sous_domaine2_obj, tranche_age, niveau_significativite):
    """Trouve la comparaison entre deux sous-domaines."""
    try:
        return ComparaisonSousDomaineVineland.objects.get(
            age=tranche_age,
            niveau_significativite=niveau_significativite,
            sous_domaine1=sous_domaine1_obj,
            sous_domaine2=sous_domaine2_obj
        )
    except ComparaisonSousDomaineVineland.DoesNotExist:
        try:
            return ComparaisonSousDomaineVineland.objects.get(
                age=tranche_age,
                niveau_significativite=niveau_significativite,
                sous_domaine1=sous_domaine2_obj,
                sous_domaine2=sous_domaine1_obj
            )
        except ComparaisonSousDomaineVineland.DoesNotExist:
            return None


def find_sous_domaine_frequency(sous_domaine1_obj, sous_domaine2_obj, tranche_age):
    """Trouve les fréquences de différence entre deux sous-domaines."""
    try:
        return FrequenceDifferenceSousDomaineVineland.objects.get(
            age=tranche_age,
            sous_domaine1=sous_domaine1_obj,
            sous_domaine2=sous_domaine2_obj
        )
    except FrequenceDifferenceSousDomaineVineland.DoesNotExist:
        try:
            return FrequenceDifferenceSousDomaineVineland.objects.get(
                age=tranche_age,
                sous_domaine1=sous_domaine2_obj,
                sous_domaine2=sous_domaine1_obj
            )
        except FrequenceDifferenceSousDomaineVineland.DoesNotExist:
            return None


# ========== FONCTIONS DE GÉNÉRATION DES COMPARAISONS ==========

def generate_domain_comparisons(domaine_scores, tranche_age_simple, tranche_age, niveau_significativite):
    """Génère les comparaisons par paires pour les domaines."""
    comparisons = []
    domaines = list(domaine_scores.keys())
    
    for i in range(len(domaines)):
        for j in range(i+1, len(domaines)):
            domaine1 = domaines[i]
            domaine2 = domaines[j]
            score1 = domaine_scores[domaine1]['note_standard']
            score2 = domaine_scores[domaine2]['note_standard']
            
            domain1_obj = domaine_scores[domaine1]['domaine_obj']
            domain2_obj = domaine_scores[domaine2]['domaine_obj']
            
            difference = abs(score1 - score2)
            signe = '>' if score1 > score2 else '<' if score1 < score2 else '='
            
            # Rechercher la comparaison
            comparison = find_domain_comparison(
                domain1_obj, domain2_obj, tranche_age_simple, niveau_significativite
            )
            
            # Rechercher les fréquences
            freq = find_domain_frequency(domain1_obj, domain2_obj, tranche_age)
            
            est_significatif = comparison and difference >= comparison.difference_requise
            frequence = get_frequency_percentage(difference, freq)
            
            comparisons.append({
                'domaine1': domaine1,
                'domaine2': domaine2,
                'note1': score1,
                'note2': score2,
                'signe': signe,
                'difference': difference,
                'difference_requise': comparison.difference_requise if comparison else None,
                'est_significatif': est_significatif,
                'frequence': frequence
            })
    
    return comparisons


def generate_sous_domaine_comparisons(sous_domaine_scores, tranche_age, niveau_significativite):
    """Génère les comparaisons par paires pour les sous-domaines, groupées par domaine."""
    # Grouper les sous-domaines par domaine
    sous_domaine_grouped = {}
    for sous_domaine, data in sous_domaine_scores.items():
        domaine = data['domaine']
        if domaine not in sous_domaine_grouped:
            sous_domaine_grouped[domaine] = []
        sous_domaine_grouped[domaine].append(sous_domaine)
    
    sous_domaine_comparisons = {}
    
    for domaine, sous_domaines in sous_domaine_grouped.items():
        sous_domaine_comparisons[domaine] = []
        
        for i in range(len(sous_domaines)):
            for j in range(i+1, len(sous_domaines)):
                sous_domaine1 = sous_domaines[i]
                sous_domaine2 = sous_domaines[j]
                note1 = sous_domaine_scores[sous_domaine1]['note_echelle_v']
                note2 = sous_domaine_scores[sous_domaine2]['note_echelle_v']
                
                sous_domaine1_obj = sous_domaine_scores[sous_domaine1]['sous_domaine_obj']
                sous_domaine2_obj = sous_domaine_scores[sous_domaine2]['sous_domaine_obj']
                
                difference = abs(note1 - note2)
                signe = '>' if note1 > note2 else '<' if note1 < note2 else '='
                
                # Rechercher la comparaison
                comparison = find_sous_domaine_comparison(
                    sous_domaine1_obj, sous_domaine2_obj, tranche_age, niveau_significativite
                )
                
                # Rechercher les fréquences
                freq = find_sous_domaine_frequency(
                    sous_domaine1_obj, sous_domaine2_obj, tranche_age
                )
                
                est_significatif = comparison and difference >= comparison.difference_requise
                frequence = get_frequency_percentage(difference, freq)
                
                sous_domaine_comparisons[domaine].append({
                    'sous_domaine1': sous_domaine1,
                    'sous_domaine2': sous_domaine2,
                    'note1': note1,
                    'note2': note2,
                    'signe': signe,
                    'difference': difference,
                    'difference_requise': comparison.difference_requise if comparison else None,
                    'est_significatif': est_significatif,
                    'frequence': frequence
                })
    
    return sous_domaine_comparisons


def generate_interdomaine_comparisons(sous_domaine_scores, tranche_age, niveau_significativite):
    """Génère les comparaisons inter-domaines pour les sous-domaines."""
    interdomaine_comparisons = []
    all_sous_domaines = list(sous_domaine_scores.keys())
    
    for i in range(len(all_sous_domaines)):
        for j in range(i+1, len(all_sous_domaines)):
            sous_domaine1 = all_sous_domaines[i]
            sous_domaine2 = all_sous_domaines[j]
            
            domaine1 = sous_domaine_scores[sous_domaine1]['domaine']
            domaine2 = sous_domaine_scores[sous_domaine2]['domaine']
            
            # Seulement si domaines différents
            if domaine1 != domaine2:
                note1 = sous_domaine_scores[sous_domaine1]['note_echelle_v']
                note2 = sous_domaine_scores[sous_domaine2]['note_echelle_v']
                
                sous_domaine1_obj = sous_domaine_scores[sous_domaine1]['sous_domaine_obj']
                sous_domaine2_obj = sous_domaine_scores[sous_domaine2]['sous_domaine_obj']
                
                difference = abs(note1 - note2)
                signe = '>' if note1 > note2 else '<' if note1 < note2 else '='
                
                # Rechercher la comparaison
                comparison = find_sous_domaine_comparison(
                    sous_domaine1_obj, sous_domaine2_obj, tranche_age, niveau_significativite
                )
                
                # Rechercher les fréquences
                freq = find_sous_domaine_frequency(
                    sous_domaine1_obj, sous_domaine2_obj, tranche_age
                )
                
                est_significatif = comparison and difference >= comparison.difference_requise
                frequence = get_frequency_percentage(difference, freq)
                
                interdomaine_comparisons.append({
                    'sous_domaine1': sous_domaine1,
                    'sous_domaine2': sous_domaine2,
                    'domaine1': domaine1,
                    'domaine2': domaine2,
                    'note1': note1,
                    'note2': note2,
                    'signe': signe,
                    'difference': difference,
                    'difference_requise': comparison.difference_requise if comparison else None,
                    'est_significatif': est_significatif,
                    'frequence': frequence
                })
    
    return interdomaine_comparisons


    """Modifier un test Vineland existant"""
    print("\n" + "="*80)
    print(f"🔍 DEBUG vineland_edit - test_id: {test_id}")
    
    if request.user.is_superadmin():
        test = get_object_or_404(TestVineland.all_objects, id=test_id)
    else:
        test = get_object_or_404(TestVineland, id=test_id, organization=request.user.organization)
    
    print(f"✅ Test récupéré: {test.id}")
    print(f"✅ Patient: {test.patient.nom_complet}")
    print(f"✅ Date passation: {test.date_passation}")
    
    # Récupérer les questions avec leurs relations
    questions = QuestionVineland.objects.select_related(
        'sous_domaine',
        'sous_domaine__domain'
    ).order_by('created_at')

    # Génération d'une clé unique pour chaque question
    for question in questions:
        question.unique_id = f"{question.sous_domaine.id}_{question.numero_item}"

    # Récupérer toutes les plages d'âge
    plages = {
        (plage.sous_domaine_id, plage.item_debut, plage.item_fin): plage 
        for plage in PlageItemVineland.objects.all()
    }

    # Associer les plages d'âge aux questions
    for question in questions:
        for (sous_domaine_id, item_debut, item_fin), plage in plages.items():
            if (question.sous_domaine_id == sous_domaine_id and 
                item_debut <= question.numero_item <= item_fin):
                question.plage_age = plage
                break
        else:
            question.plage_age = None

    paginator = Paginator(questions, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # 🆕 PRÉ-REMPLIR avec les réponses existantes
    initial_data = {}
    existing_responses = ReponseVineland.objects.filter(test_vineland=test)
    
    print(f"\n📊 ANALYSE DES RÉPONSES :")
    print(f"   Nombre total de réponses en BDD : {existing_responses.count()}")
    print(f"   Nombre total de questions : {questions.count()}")
    
    for response in existing_responses:
        key = f'question_{response.question.sous_domaine.id}_{response.question.numero_item}'
        initial_data[key] = response.reponse
        
        # Afficher les 5 premières pour debug
        if len(initial_data) <= 5:
            print(f"   ✓ {key} = '{response.reponse}' (type: {type(response.reponse)})")
    
    print(f"\n📦 initial_data contient {len(initial_data)} entrées")
    
    # Afficher quelques exemples de clés
    if initial_data:
        sample_keys = list(initial_data.keys())[:5]
        print(f"   Exemples de clés : {sample_keys}")
    
    print("="*80 + "\n")

    if request.method == 'POST':
        action = request.POST.get('action')
        
        print(f"📝 POST reçu - action: {action}")
        
        # Sauvegarder les réponses (mise à jour ou création)
        for key, value in request.POST.items():
            if key.startswith('question_'):
                parts = key.split('_')
                if len(parts) >= 3:
                    sous_domaine_id = int(parts[1])
                    numero_item = int(parts[2])
                    
                    question = QuestionVineland.objects.get(
                        sous_domaine_id=sous_domaine_id,
                        numero_item=numero_item
                    )
                    
                    # 🆕 Mettre à jour ou créer la réponse
                    reponse_obj, created = ReponseVineland.objects.update_or_create(
                        question=question,
                        test_vineland=test,
                        defaults={
                            'reponse': value,
                            'organization': test.organization
                        }
                    )
                    
                    if len(initial_data) <= 3:  # Log les 3 premières
                        print(f"   {'Créé' if created else 'Mis à jour'}: {key} = {value}")

        # Vérifier les questions non répondues sur la page courante
        current_page_questions = page_obj.object_list
        unanswered_current = []
        for question in current_page_questions:
            key = f'question_{question.unique_id}'
            if key not in request.POST:
                unanswered_current.append(f"{question.sous_domaine.name}-{question.numero_item}")

        if unanswered_current:
            messages.info(request, f"Questions sans réponse sur cette page : {', '.join(map(str, unanswered_current))}")

        if action == 'previous':
            prev_page = int(page_number) - 1
            return redirect(f'{request.path}?page={prev_page}')
            
        elif action == 'next':
            next_page = int(page_number) + 1
            return redirect(f'{request.path}?page={next_page}')
            
        elif action == 'submit':
            messages.success(request, "Test Vineland modifié avec succès !")
            return redirect('tests_psy:vineland_scores', test_id=test.id)

    return render(request, 'tests_psy/vineland/questionnaire.html', {
        'test': test,
        'patient': test.patient,
        'page_obj': page_obj,
        'initial_data': initial_data,
        'is_edit': True,
    })