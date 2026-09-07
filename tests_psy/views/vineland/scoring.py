"""
Calcul des scores Vineland : note brute par sous-domaine (item plancher),
mapping échelle-V par âge, et scores de domaine complets (norme, intervalle
de confiance, niveau adaptatif, âge équivalent).
"""
from dateutil.relativedelta import relativedelta

from django.db.models import Q

from tests_psy.models import (
    Domain, SousDomain, ReponseVineland, EchelleVMapping, NoteDomaineVMapping,
    IntervaleConfianceSousDomaine, IntervaleConfianceDomaine, NiveauAdaptatif,
    AgeEquivalentSousDomaine,
)


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

def _age_apres_ou_egal_au_debut(mapping, age_years, age_months, age_days):
    """
    True si (age_years, age_months, age_days) est >= à la borne de début du mapping.
    Le jour n'est comparé que quand année ET mois coïncident exactement, et
    seulement si age_debut_jour est renseigné.
    """
    if mapping.age_debut_annee != age_years:
        return mapping.age_debut_annee < age_years
    if mapping.age_debut_mois != age_months:
        return mapping.age_debut_mois < age_months
    if mapping.age_debut_jour is None:
        return True
    return mapping.age_debut_jour <= age_days


def _age_avant_ou_egal_a_la_fin(mapping, age_years, age_months, age_days):
    """Symétrique de _age_apres_ou_egal_au_debut pour la borne de fin."""
    if mapping.age_fin_annee != age_years:
        return mapping.age_fin_annee > age_years
    if mapping.age_fin_mois != age_months:
        return mapping.age_fin_mois > age_months
    if mapping.age_fin_jour is None:
        return True
    return mapping.age_fin_jour >= age_days


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
        if (_age_apres_ou_egal_au_debut(mapping, age_years, age_months, age_days)
                and _age_avant_ou_egal_a_la_fin(mapping, age_years, age_months, age_days)):
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
