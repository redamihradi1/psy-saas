"""Cotation BRIEF (Forme Parent), selon le chapitre 2 du manuel.

Fonctions pures (données en entrée, dict en sortie) pour être testables sans base, puis
`calculer_resultats(test)` qui assemble tout à partir d'un TestBRIEF. Rien n'est stocké :
les scores sont recalculés à chaque affichage, comme pour Vineland - modifier une réponse
et revenir sur les résultats suffit à recalculer.
"""
from tests_psy.models.brief import (
    ECHELLE_CHOICES, INDICE_CHOICES, ItemBRIEF, NormeBRIEF, PaireIncoherenceBRIEF,
)

ECHELLES = [code for code, _ in ECHELLE_CHOICES]
LIBELLES = dict(ECHELLE_CHOICES + INDICE_CHOICES)
LIBELLES_COURTS = {**dict(ECHELLE_CHOICES), 'irc': 'IRC', 'im': 'IM', 'ceg': 'CEG'}

COMPOSITION_INDICES = {
    'irc': ['inhibition', 'flexibilite', 'controle_emotionnel'],
    'im': ['initiation', 'memoire_travail', 'planification', 'organisation_materiel', 'controle'],
    'ceg': ECHELLES,  # CEG = IRC + IM
}

# Réponses manquantes (manuel, "Réponses manquantes") : au-delà de 14 items manquants parmi
# ceux qui comptent dans les échelles, le protocole n'est pas cotable ; dans une échelle,
# 1 ou 2 manquants valent 1 point chacun, au-delà le score brut de l'échelle n'est pas calculé.
MAX_MANQUANTS_PROTOCOLE = 14
MAX_MANQUANTS_ECHELLE = 2
VALEUR_ITEM_MANQUANT = 1

# Scores T >= 65 : signification clinique potentielle (manuel, 3.1).
SEUIL_T_CLINIQUE = 65

# Écart de scores T entre IRC et IM au-delà duquel le CEG peut masquer des différences
# importantes et ne doit pas être utilisé comme mesure résumée (manuel, 3.3, Forme Parent).
SEUIL_ECART_IRC_IM = 13

# Négativité (manuel, Figure 3) : nombre d'items de Négativité cotés 3.
def classer_negativite(score):
    if score is None:
        return None
    if score <= 4:
        return 'Acceptable'
    if score <= 6:
        return 'Élevé'
    return 'Très élevé'


# Incohérence : les seuils de l'adaptation française (Acceptable / Limite / Incohérent)
# figurent dans la section "Adaptation française" du manuel, pas encore fournie. Tant
# qu'ils sont à None, le score est affiché sans classification.
SEUILS_INCOHERENCE = None  # ex. {'acceptable_max': 6, 'limite_max': 8}


def classer_incoherence(score):
    if score is None or SEUILS_INCOHERENCE is None:
        return None
    if score <= SEUILS_INCOHERENCE['acceptable_max']:
        return 'Acceptable'
    if score <= SEUILS_INCOHERENCE['limite_max']:
        return 'Limite'
    return 'Incohérent'


def age_en_annees(date_naissance, date_reference):
    age = date_reference.year - date_naissance.year
    if (date_reference.month, date_reference.day) < (date_naissance.month, date_naissance.day):
        age -= 1
    return age


def scores_bruts_echelles(items_par_echelle, reponses):
    """items_par_echelle : {echelle: [numéros d'items]} ; reponses : {numéro: valeur 1/2/3}.

    Retourne ({echelle: {'note_brute', 'manquants', 'nb_items'}}, total des manquants)."""
    resultats = {}
    manquants_total = 0
    for echelle in ECHELLES:
        numeros = items_par_echelle.get(echelle, [])
        valeurs = [reponses[n] for n in numeros if n in reponses]
        manquants = len(numeros) - len(valeurs)
        manquants_total += manquants
        if manquants > MAX_MANQUANTS_ECHELLE:
            note = None
        else:
            note = sum(valeurs) + manquants * VALEUR_ITEM_MANQUANT
        resultats[echelle] = {'note_brute': note, 'manquants': manquants, 'nb_items': len(numeros)}
    return resultats, manquants_total


def scores_bruts_indices(notes_echelles):
    """notes_echelles : {echelle: note brute ou None} -> {indice: note brute ou None}."""
    indices = {}
    for indice, composantes in COMPOSITION_INDICES.items():
        notes = [notes_echelles.get(echelle) for echelle in composantes]
        indices[indice] = None if any(note is None for note in notes) else sum(notes)
    return indices


def score_negativite(numeros_negativite, reponses):
    score = sum(1 for n in numeros_negativite if reponses.get(n) == 3)
    manquants = sum(1 for n in numeros_negativite if n not in reponses)
    return {'score': score, 'classification': classer_negativite(score), 'manquants': manquants}


def score_incoherence(paires, reponses):
    """paires : [(item_a, item_b)] -> somme des différences absolues. Une paire dont un des
    deux items est sans réponse est ignorée et signalée (score alors sous-estimé)."""
    score = 0
    details = []
    incompletes = 0
    for item_a, item_b in paires:
        a, b = reponses.get(item_a), reponses.get(item_b)
        if a is None or b is None:
            incompletes += 1
            details.append({'item_a': item_a, 'item_b': item_b, 'a': a, 'b': b, 'difference': None})
            continue
        difference = abs(a - b)
        score += difference
        details.append({'item_a': item_a, 'item_b': item_b, 'a': a, 'b': b, 'difference': difference})
    return {
        'score': score,
        'classification': classer_incoherence(score) if not incompletes else None,
        'paires_incompletes': incompletes,
        'details': details,
    }


def chercher_norme(forme, sexe, age, echelle, score_brut):
    """Ligne de la table d'étalonnage correspondante, ou None si absente (normes non
    chargées, âge hors étalonnage, score brut absent de la table)."""
    if score_brut is None or age is None:
        return None
    return NormeBRIEF.objects.filter(
        forme=forme, sexe=sexe, age_min__lte=age, age_max__gte=age,
        echelle=echelle, score_brut=score_brut,
    ).first()


def normes_disponibles(forme, sexe, age):
    return NormeBRIEF.objects.filter(forme=forme, sexe=sexe, age_min__lte=age, age_max__gte=age).exists()


def _ligne(code, note_brute, norme, manquants=None, nb_items=None):
    score_t = norme.score_t if norme else None
    ic = norme.ic90 if norme else None
    return {
        'code': code,
        'libelle': LIBELLES[code],
        'libelle_court': LIBELLES_COURTS[code],
        'est_indice': code not in ECHELLES,
        'note_brute': note_brute,
        'manquants': manquants,
        'nb_items': nb_items,
        'score_t': score_t,
        'percentile': norme.percentile if norme else None,
        'ic_bas': score_t - ic if score_t is not None and ic is not None else None,
        'ic_haut': score_t + ic if score_t is not None and ic is not None else None,
        'significatif': score_t is not None and score_t >= SEUIL_T_CLINIQUE,
    }


def calculer_resultats(test):
    """Assemble tous les résultats d'un TestBRIEF (scores bruts, T, percentiles, IC,
    indices, validité, alertes) pour l'affichage et le PDF."""
    forme = test.forme
    age = age_en_annees(test.patient.date_naissance, test.date_passation.date())
    reponses = {}
    details_echelles = {}
    manquants_total = None

    if test.mode == 'importe':
        notes = {n.echelle: n.note_brute for n in test.notes_brutes_importees.all()}
        notes_echelles = {echelle: notes.get(echelle) for echelle in ECHELLES}
        negativite = {
            'score': test.negativite_importee,
            'classification': classer_negativite(test.negativite_importee),
            'manquants': None,
        }
        incoherence = {
            'score': test.incoherence_importee,
            'classification': classer_incoherence(test.incoherence_importee),
            'paires_incompletes': 0,
            'details': [],
        }
    else:
        reponses = {r.item.numero: r.valeur for r in test.reponses.select_related('item')}
        items = list(ItemBRIEF.objects.filter(forme=forme))
        items_par_echelle = {}
        for item in items:
            if item.echelle:
                items_par_echelle.setdefault(item.echelle, []).append(item.numero)
        details_echelles, manquants_total = scores_bruts_echelles(items_par_echelle, reponses)
        notes_echelles = {echelle: details_echelles[echelle]['note_brute'] for echelle in ECHELLES}
        negativite = score_negativite([i.numero for i in items if i.est_negativite], reponses)
        paires = PaireIncoherenceBRIEF.objects.filter(forme=forme).values_list('item_a', 'item_b')
        incoherence = score_incoherence(list(paires), reponses)

    protocole_cotable = manquants_total is None or manquants_total <= MAX_MANQUANTS_PROTOCOLE
    hors_etalonnage = age < 5 or age > 18
    avec_normes = protocole_cotable and not hors_etalonnage and normes_disponibles(forme, test.sexe, age)

    notes_indices = scores_bruts_indices(notes_echelles)
    lignes = []
    for code in ECHELLES:
        note = notes_echelles[code]
        detail = details_echelles.get(code, {})
        norme = chercher_norme(forme, test.sexe, age, code, note) if avec_normes else None
        lignes.append(_ligne(code, note, norme, detail.get('manquants'), detail.get('nb_items')))
    for code, _ in INDICE_CHOICES:
        note = notes_indices[code]
        norme = chercher_norme(forme, test.sexe, age, code, note) if avec_normes else None
        lignes.append(_ligne(code, note, norme))

    par_code = {ligne['code']: ligne for ligne in lignes}
    t_irc, t_im = par_code['irc']['score_t'], par_code['im']['score_t']
    ecart_irc_im = abs(t_irc - t_im) if t_irc is not None and t_im is not None else None

    return {
        'age': age,
        'forme': forme,
        'sexe': test.sexe,
        'lignes': lignes,
        'echelles': [l for l in lignes if not l['est_indice']],
        'indices': [l for l in lignes if l['est_indice']],
        'par_code': par_code,
        'reponses': reponses,
        'nb_reponses': len(reponses),
        'manquants_total': manquants_total,
        'protocole_cotable': protocole_cotable,
        'hors_etalonnage': hors_etalonnage,
        'normes_disponibles': avec_normes,
        'negativite': negativite,
        'incoherence': incoherence,
        'seuils_incoherence_connus': SEUILS_INCOHERENCE is not None,
        'ecart_irc_im': ecart_irc_im,
        'alerte_ecart_irc_im': ecart_irc_im is not None and ecart_irc_im >= SEUIL_ECART_IRC_IM,
        'seuil_ecart_irc_im': SEUIL_ECART_IRC_IM,
        'seuil_t_clinique': SEUIL_T_CLINIQUE,
    }
