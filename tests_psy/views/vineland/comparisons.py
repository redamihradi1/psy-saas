"""
Comparaisons par paires Vineland : domaines, sous-domaines (intra-domaine)
et inter-domaines, avec recherche de significativité et de fréquence dans
les tables de normes.
"""
from tests_psy.models import (
    ComparaisonDomaineVineland, ComparaisonSousDomaineVineland,
    FrequenceDifferenceDomaineVineland, FrequenceDifferenceSousDomaineVineland,
)


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
