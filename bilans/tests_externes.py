"""Tests passés hors de la plateforme (cotation papier ou logiciel de l'éditeur) dont le
psychologue saisit les scores dans le bilan : WISC-V, WAIS-IV, TMT, Stroop, TEA-Ch...

Aucune norme sous droit d'auteur ici : le psychologue saisit les notes déjà étalonnées (notes
composites, notes standard, scores T, percentiles). Le code ne fait que des calculs simples et
documentés : zones qualitatives usuelles, écarts entre indices, forces/faiblesses relatives,
différences TMT, niveaux des inventaires de Beck. Toute valeur qualitative saisie par le
psychologue l'emporte sur la valeur calculée.

Saisie stockée dans Bilan.scores[cle_test] :
  {'grilles': {cle_grille: {cle_ligne: {cle_colonne: 'valeur'}}},      # grilles fixes
   'libres': {cle_grille: [['c1', 'c2', ...], ...]},                     # grilles à lignes libres
   'champs': {cle_champ: 'valeur'}}
"""
import re

# --- valeurs ---------------------------------------------------------------------------------

def nombre(valeur):
    """'12' -> 12, '4,5' -> 4.5, '<0.1' / '' / None -> None."""
    if valeur is None:
        return None
    texte = str(valeur).strip().replace(',', '.').replace(' ', '')
    if not re.fullmatch(r'-?\d+(\.\d+)?', texte):
        return None
    n = float(texte)
    return int(n) if n.is_integer() else n


def fmt(n):
    """Nombre -> texte français (virgule décimale)."""
    if n is None:
        return '-'
    if isinstance(n, float):
        return f'{n:.2f}'.rstrip('0').rstrip('.').replace('.', ',')
    return str(n)


def _v(valeur):
    valeur = (valeur or '').strip() if isinstance(valeur, str) else valeur
    return '-' if valeur in (None, '') else str(valeur)


# --- classifications ---------------------------------------------------------------------------

ZONES_WISC = [(130, 'Très élevée'), (120, 'Élevée'), (110, 'Moyenne forte'), (90, 'Moyenne'),
              (80, 'Moyenne faible'), (70, 'Faible'), (None, 'Très faible')]
ZONES_WAIS = [(130, 'Très supérieur'), (120, 'Supérieur'), (110, 'Moyenne supérieure'), (90, 'Moyenne'),
              (80, 'Moyenne faible'), (70, 'Limite'), (None, 'Très inférieur')]
ZONES_D2R = [(130, 'Très supérieur'), (120, 'Supérieur'), (110, 'Moyenne supérieure'), (90, 'Dans la norme'),
             (80, 'Faible'), (70, 'Très faible'), (None, 'Déficitaire')]
NIVEAUX_BAI = [(26, 'Sévère'), (16, 'Modérée'), (8, 'Légère'), (None, 'Minimale')]
NIVEAUX_BDI = [(28, 'Sévère'), (20, 'Modérée'), (12, 'Légère'), (None, 'Minimale')]  # seuils de l'adaptation française


def zone(valeur, zones):
    n = nombre(valeur)
    if n is None:
        return ''
    for seuil, libelle in zones:
        if seuil is None or n >= seuil:
            return libelle
    return ''


def zone_t_brief(t):
    """Seuils du BRIEF (score T) tels que présentés dans les bilans : 65+ clinique."""
    t = nombre(t)
    if t is None:
        return ''
    if t >= 65:
        return 'Cliniquement significatif'
    if t >= 60:
        return 'Légèrement élevé'
    return 'Dans la norme'


def zone_t_rcads(t):
    t = nombre(t)
    if t is None:
        return ''
    if t >= 70:
        return 'Seuil clinique'
    if t >= 65:
        return 'Zone limite'
    return 'Dans la norme'


# --- catalogue ---------------------------------------------------------------------------------

COLONNES_INDICES = [('note', 'Note composite', 'nombre'), ('percentile', 'Rang percentile', 'texte'),
                    ('ic', 'IC 95 %', 'texte'), ('description', 'Description (si différente)', 'texte')]
COLONNES_SUBTESTS = [('brute', 'Note brute', 'nombre'), ('ns', 'Note standard', 'nombre')]
COLONNES_SCORE_T = [('brute', 'Note brute', 'nombre'), ('t', 'Score T', 'nombre'), ('percentile', 'Percentile', 'texte')]

INDICES_PRINCIPAUX = {'ICV', 'IVS', 'IRF', 'IRP', 'IMT', 'IVT'}

TESTS = {
    'wisc5': {
        'nom': 'WISC-V',
        'nom_long': "WISC-V - Échelle d'intelligence de Wechsler pour enfants et adolescents (5e édition)",
        'domaine': 'intellectuel',
        'description': "Évaluation du fonctionnement intellectuel : compréhension verbale, aptitudes "
                       "visuospatiales, raisonnement fluide, mémoire de travail et vitesse de traitement. "
                       "L'analyse du profil permet de repérer les ressources et les fragilités cognitives.",
        'type': 'wechsler',
        'zones': ZONES_WISC,
        'grilles': [
            {'cle': 'indices', 'titre': "Indices", 'colonnes': COLONNES_INDICES, 'lignes': [
                ('ICV', "Compréhension verbale (ICV)"), ('IVS', "Visuospatial (IVS)"),
                ('IRF', "Raisonnement fluide (IRF)"), ('IMT', "Mémoire de travail (IMT)"),
                ('IVT', "Vitesse de traitement (IVT)"), ('QIT', "QI total (QIT)"),
                ('IAG', "Aptitude générale (IAG)"), ('ICC', "Compétence cognitive (ICC)"),
            ]},
            {'cle': 'subtests', 'titre': "Subtests", 'colonnes': COLONNES_SUBTESTS, 'lignes': [
                ('SIM', "Similitudes"), ('VOC', "Vocabulaire"), ('INF', "Information"), ('COM', "Compréhension"),
                ('CUB', "Cubes"), ('PUZ', "Puzzles visuels"), ('MAT', "Matrices"), ('BAL', "Balances"),
                ('ARI', "Arithmétique"), ('MCH', "Mémoire des chiffres"), ('MIM', "Mémoire des images"),
                ('SLC', "Séquence lettres-chiffres"), ('COD', "Code"), ('SYM', "Symboles"), ('BAR', "Barrage"),
            ]},
        ],
        'indice_des_subtests': {'SIM': 'ICV', 'VOC': 'ICV', 'INF': 'ICV', 'COM': 'ICV', 'CUB': 'IVS', 'PUZ': 'IVS',
                                'MAT': 'IRF', 'BAL': 'IRF', 'ARI': 'IRF', 'MCH': 'IMT', 'MIM': 'IMT', 'SLC': 'IMT',
                                'COD': 'IVT', 'SYM': 'IVT', 'BAR': 'IVT'},
    },
    'wais4': {
        'nom': 'WAIS-IV',
        'nom_long': "WAIS-IV - Échelle d'intelligence de Wechsler pour adultes (4e édition)",
        'domaine': 'intellectuel',
        'description': "Évaluation du fonctionnement intellectuel de l'adulte : compréhension verbale, "
                       "raisonnement perceptif, mémoire de travail et vitesse de traitement. L'analyse des "
                       "écarts entre indices est particulièrement informative dans le cadre d'un bilan attentionnel.",
        'type': 'wechsler',
        'zones': ZONES_WAIS,
        'grilles': [
            {'cle': 'indices', 'titre': "Indices", 'colonnes': COLONNES_INDICES, 'lignes': [
                ('ICV', "Compréhension verbale (ICV)"), ('IRP', "Raisonnement perceptif (IRP)"),
                ('IMT', "Mémoire de travail (IMT)"), ('IVT', "Vitesse de traitement (IVT)"),
                ('QIT', "QI total (QIT)"), ('IAG', "Aptitude générale (IAG)"), ('ICC', "Compétence cognitive (ICC)"),
            ]},
            {'cle': 'subtests', 'titre': "Subtests", 'colonnes': COLONNES_SUBTESTS, 'lignes': [
                ('SIM', "Similitudes"), ('VOC', "Vocabulaire"), ('INF', "Information"), ('COM', "Compréhension"),
                ('CUB', "Cubes"), ('MAT', "Matrices"), ('PUZ', "Puzzles visuels"), ('BAL', "Balances"),
                ('IMC', "Complètement d'images"), ('MCH', "Mémoire des chiffres"), ('ARI', "Arithmétique"),
                ('SLC', "Séquence lettres-chiffres"), ('SYM', "Symboles"), ('COD', "Code"), ('BAR', "Barrage"),
            ]},
        ],
        'indice_des_subtests': {'SIM': 'ICV', 'VOC': 'ICV', 'INF': 'ICV', 'COM': 'ICV', 'CUB': 'IRP', 'MAT': 'IRP',
                                'PUZ': 'IRP', 'BAL': 'IRP', 'IMC': 'IRP', 'MCH': 'IMT', 'ARI': 'IMT', 'SLC': 'IMT',
                                'SYM': 'IVT', 'COD': 'IVT', 'BAR': 'IVT'},
    },
    'd2r_papier': {
        'nom': 'd2-R',
        'nom_long': "d2-R - Test d'attention concentrée (version révisée)",
        'domaine': 'attention',
        'description': "Épreuve de barrage explorant l'attention sélective et la concentration : rythme de "
                       "traitement, précision et capacité de concentration, dans une tâche visuelle monotone "
                       "sous contrainte de temps.",
        'grilles': [
            {'cle': 'scores', 'titre': "Scores", 'colonnes': [('ns', 'Note standard', 'nombre'),
                                                              ('percentile', 'Percentile', 'texte')], 'lignes': [
                ('CCT', "Caractères cibles traités (CCT) - rythme"), ('E', "Taux d'erreurs (E %) - exactitude"),
                ('CC', "Capacité de concentration (CC)"),
            ]},
        ],
        'champs': [('profil', "Profil (laisser vide pour le calcul automatique)", 'choix',
                    ['', 'Attentif et concentré', 'Réfléchi', 'Impulsif', 'Ni attentif ni concentré'])],
    },
    'tmt': {
        'nom': 'TMT',
        'nom_long': "Trail Making Test (TMT) - parties A et B",
        'domaine': 'executif',
        'description': "La partie A mesure la vitesse de traitement et l'exploration visuelle ; la partie B "
                       "ajoute une alternance entre deux séquences et sollicite la flexibilité cognitive. "
                       "Les indices B - A et B/A isolent le coût de l'alternance.",
        'grilles': [
            {'cle': 'parties', 'titre': "Parties", 'colonnes': [
                ('temps', 'Temps (s)', 'nombre'), ('erreurs', 'Erreurs', 'nombre'),
                ('interpretation', 'Interprétation (normes utilisées)', 'texte')], 'lignes': [
                ('A', "TMT-A"), ('B', "TMT-B"),
            ]},
        ],
        'champs': [('interpretation_ba', "Interprétation de B - A", 'texte'),
                   ('interpretation_ratio', "Interprétation de B/A", 'texte'),
                   ('normes', "Normes utilisées (ex. GREFEX)", 'texte')],
    },
    'stroop': {
        'nom': 'Stroop',
        'nom_long': "Test de Stroop",
        'domaine': 'executif',
        'description': "Épreuve d'inhibition : la condition d'interférence demande de dénommer la couleur "
                       "de l'encre en inhibant la lecture automatique du mot. Elle renseigne sur le contrôle "
                       "inhibiteur et la sensibilité à l'interférence.",
        'grilles': [
            {'cle': 'conditions', 'titre': "Conditions", 'colonnes': [
                ('score', 'Temps ou score', 'texte'), ('erreurs', 'Erreurs', 'nombre'),
                ('classe', 'Classe / norme', 'texte'), ('interpretation', 'Interprétation', 'texte')], 'lignes': [
                ('lecture', "Lecture"), ('denomination', "Dénomination des couleurs"),
                ('interference', "Interférence"), ('score_interference', "Score d'interférence"),
            ]},
        ],
        'champs': [('normes', "Normes utilisées (ex. GREFEX 2008)", 'texte')],
    },
    'teach': {
        'nom': 'TEA-Ch',
        'nom_long': "TEA-Ch - Test d'évaluation de l'attention chez l'enfant",
        'domaine': 'attention',
        'description': "Batterie évaluant les composantes de l'attention : attention sélective, attention "
                       "soutenue, attention divisée et contrôle attentionnel (flexibilité, inhibition). Les "
                       "épreuves limitent le poids du langage et de la mémoire.",
        'grilles': [
            {'cle': 'subtests', 'titre': "Subtests", 'colonnes': [
                ('brute', 'Note brute', 'texte'), ('pc', 'Pourcentage cumulé / percentile', 'texte')], 'lignes': [
                ('ciel_cibles', "Recherche dans le ciel - cibles correctement encerclées"),
                ('ciel_temps', "Recherche dans le ciel - temps par cible"),
                ('ciel_attention', "Recherche dans le ciel - note d'attention"),
                ('fusils', "Coups de fusil"),
                ('hommes_verts_precision', "Les petits hommes verts - bonnes réponses"),
                ('hommes_verts_temps', "Les petits hommes verts - note de temps"),
                ('deux_choses', "Faire deux choses à la fois"),
                ('carte', "Carte géographique"),
                ('ecouter', "Écouter deux choses à la fois"),
                ('marche_arrete', "Marche-Arrête"),
                ('mondes_endroit', "Mondes contraires - à l'endroit"),
                ('mondes_envers', "Mondes contraires - à l'envers"),
                ('codes', "Transmission de codes"),
            ]},
        ],
        'domaines_attention': [
            ("Attention sélective", ['ciel_cibles', 'ciel_temps', 'ciel_attention', 'carte']),
            ("Attention soutenue", ['fusils', 'codes']),
            ("Attention divisée", ['deux_choses', 'ecouter']),
            ("Contrôle attentionnel et flexibilité", ['marche_arrete', 'mondes_endroit', 'mondes_envers',
                                                      'hommes_verts_precision', 'hommes_verts_temps']),
        ],
    },
    'brief_papier': {
        'nom': 'BRIEF',
        'nom_long': "BRIEF - Inventaire d'évaluation comportementale des fonctions exécutives",
        'domaine': 'executif',
        'description': "Questionnaire rempli par l'entourage (ou par le patient) décrivant les fonctions "
                       "exécutives dans la vie quotidienne : régulation comportementale (inhibition, "
                       "flexibilité, contrôle émotionnel) et métacognition (initiation, mémoire de travail, "
                       "planification, organisation, contrôle). Un score T de 65 ou plus est cliniquement significatif.",
        'grilles': [
            {'cle': 'echelles', 'titre': "Échelles et indices", 'colonnes': COLONNES_SCORE_T, 'lignes': [
                ('inhibition', "Inhibition"), ('flexibilite', "Flexibilité"),
                ('controle_emotionnel', "Contrôle émotionnel"), ('IRC', "Indice de régulation comportementale (IRC)"),
                ('initiation', "Initiation"), ('memoire_travail', "Mémoire de travail"),
                ('planification', "Planification / organisation"), ('organisation_materiel', "Organisation du matériel"),
                ('controle', "Contrôle"), ('IM', "Indice de métacognition (IM)"),
                ('CEG', "Composite exécutif global (CEG)"),
            ]},
        ],
        'champs': [('version', "Version", 'choix', ['Parent', 'Enseignant', 'Auto-questionnaire (adolescent)',
                                                    'Adulte (BRIEF-A)'])],
    },
    'rcads': {
        'nom': 'RCADS',
        'nom_long': "RCADS - Échelle révisée d'anxiété et de dépression de l'enfant",
        'domaine': 'emotionnel',
        'description': "Questionnaire explorant les symptômes anxieux (séparation, anxiété généralisée, "
                       "panique, anxiété sociale, obsessions-compulsions) et dépressifs. Un score T de 65 "
                       "situe en zone limite, de 70 ou plus au seuil clinique.",
        'grilles': [
            {'cle': 'echelles', 'titre': "Échelles", 'colonnes': [('brute', 'Score brut', 'nombre'),
                                                                 ('t', 'Score T', 'nombre')], 'lignes': [
                ('separation', "Anxiété de séparation"), ('generalisee', "Anxiété généralisée"),
                ('panique', "Trouble panique"), ('sociale', "Anxiété sociale"),
                ('toc', "Obsessions-compulsions"), ('depression', "Dépression"),
                ('total_anxiete', "Total anxiété"), ('total', "Total anxiété et dépression"),
            ]},
        ],
        'champs': [('version', "Version", 'choix', ['Parents', 'Enfant'])],
    },
    'bhk': {
        'nom': 'BHK',
        'nom_long': "BHK - Échelle d'évaluation rapide de l'écriture",
        'domaine': 'graphomoteur',
        'description': "Évaluation de la qualité et de la vitesse de l'écriture à partir d'une copie de "
                       "texte : la note de dégradation résume les critères de qualité graphique "
                       "(régularité, formes des lettres, organisation spatiale).",
        'grilles': [],
        'libres': [{'cle': 'criteres', 'titre': "Critères", 'colonnes': ["Critère", "Score"]}],
        'champs': [('degradation', "Note totale de dégradation", 'nombre'),
                   ('degradation_zone', "Lecture de la note de dégradation (écart à la norme)", 'texte'),
                   ('vitesse', "Vitesse (caractères en 5 min)", 'nombre'),
                   ('vitesse_zone', "Lecture de la vitesse", 'texte')],
    },
    'asrs': {
        'nom': 'ASRS',
        'nom_long': "ASRS - Échelle d'autoévaluation du TDAH chez l'adulte",
        'domaine': 'questionnaire',
        'description': "Questionnaire d'autoévaluation des symptômes de TDAH à l'âge adulte. La partie A "
                       "(6 questions) sert au repérage : 4 réponses positives ou plus sont évocatrices.",
        'grilles': [],
        'champs': [('partie_a', "Partie A (sur 6)", 'nombre'), ('partie_b', "Partie B (sur 12)", 'nombre')],
    },
    'diva5': {
        'nom': 'DIVA-5',
        'nom_long': "DIVA-5 - Entretien diagnostique du TDAH chez l'adulte",
        'domaine': 'questionnaire',
        'description': "Entretien semi-structuré reprenant les critères du DSM-5, avec exploration "
                       "rétrospective de l'enfance et du retentissement fonctionnel actuel.",
        'grilles': [],
        'champs': [('inattention_adulte', "Symptômes d'inattention à l'âge adulte (sur 9)", 'nombre'),
                   ('hyperactivite_adulte', "Symptômes d'hyperactivité/impulsivité à l'âge adulte (sur 9)", 'nombre'),
                   ('inattention_enfance', "Symptômes d'inattention dans l'enfance (sur 9)", 'nombre'),
                   ('hyperactivite_enfance', "Symptômes d'hyperactivité/impulsivité dans l'enfance (sur 9)", 'nombre'),
                   ('enfance', "Présence des symptômes dans l'enfance", 'choix', ['', 'Oui', 'Non', 'Incertain']),
                   ('retentissement', "Retentissement dans plusieurs domaines", 'choix', ['', 'Oui', 'Non', 'Incertain'])],
    },
    'bai': {
        'nom': 'BAI',
        'nom_long': "Inventaire d'anxiété de Beck (BAI)",
        'domaine': 'emotionnel',
        'description': "Autoquestionnaire de 21 items mesurant l'intensité des symptômes anxieux "
                       "(score sur 63).",
        'grilles': [],
        'champs': [('score', "Score total (sur 63)", 'nombre')],
    },
    'bdi': {
        'nom': 'BDI-II',
        'nom_long': "Inventaire de dépression de Beck (BDI-II)",
        'domaine': 'emotionnel',
        'description': "Autoquestionnaire de 21 items mesurant l'intensité des symptômes dépressifs "
                       "(score sur 63).",
        'grilles': [],
        'champs': [('score', "Score total (sur 63)", 'nombre')],
    },
    'conners': {
        'nom': 'Conners',
        'nom_long': "Échelle de Conners",
        'domaine': 'questionnaire',
        'description': "Questionnaire rempli par les parents ou les enseignants, explorant les difficultés "
                       "de comportement, d'attention, d'hyperactivité et d'impulsivité.",
        'grilles': [],
        'libres': [{'cle': 'echelles', 'titre': "Échelles", 'colonnes': ["Échelle", "Résultat", "Lecture"]}],
        'champs': [('version', "Version", 'choix', ['Parents', 'Enseignants', 'Adolescent'])],
    },
    'nepsy2': {
        'nom': 'NEPSY-II',
        'nom_long': "NEPSY-II - Bilan neuropsychologique de l'enfant",
        'domaine': 'neuropsy',
        'description': "Batterie neuropsychologique de l'enfant (attention et fonctions exécutives, langage, "
                       "mémoire, traitements visuospatiaux, cognition sociale) dont seuls les subtests utiles "
                       "à la question posée sont administrés.",
        'grilles': [],
        'libres': [{'cle': 'subtests', 'titre': "Subtests", 'colonnes': [
            "Domaine / subtest", "Note brute", "Note étalonnée", "Rang percentile"]}],
    },
    'autre_1': {
        'nom': 'Autre épreuve',
        'nom_long': "Autre épreuve",
        'domaine': 'autre',
        'description': "",
        'grilles': [],
        'libres': [{'cle': 'mesures', 'titre': "Mesures", 'colonnes': ["Mesure", "Résultat", "Interprétation"]}],
        'champs': [('nom', "Nom de l'épreuve", 'texte'), ('presentation', "Présentation (ce qu'elle évalue)", 'texte')],
    },
    'autre_2': {
        'nom': 'Autre épreuve (2)',
        'nom_long': "Autre épreuve",
        'domaine': 'autre',
        'description': "",
        'grilles': [],
        'libres': [{'cle': 'mesures', 'titre': "Mesures", 'colonnes': ["Mesure", "Résultat", "Interprétation"]}],
        'champs': [('nom', "Nom de l'épreuve", 'texte'), ('presentation', "Présentation (ce qu'elle évalue)", 'texte')],
    },
}
ORDRE_DOMAINES = ['intellectuel', 'attention', 'executif', 'neuropsy', 'graphomoteur', 'questionnaire',
                  'emotionnel', 'autre']
TESTS_CHOICES = [(cle, t['nom_long'] if not cle.startswith('autre') else t['nom']) for cle, t in TESTS.items()]


# --- saisie ----------------------------------------------------------------------------------

def saisie_vide():
    return {'grilles': {}, 'libres': {}, 'champs': {}}


def lire_formulaire(cle, post):
    """POST du formulaire de saisie -> dict de saisie (valeurs texte nettoyées, vides retirés)."""
    test = TESTS[cle]
    saisie = saisie_vide()
    for grille in test.get('grilles', []):
        valeurs = {}
        for cle_ligne, _ in grille['lignes']:
            ligne = {}
            for cle_col, _, _ in grille['colonnes']:
                v = post.get(f'{cle}__g__{grille["cle"]}__{cle_ligne}__{cle_col}', '').strip()[:60]
                if v:
                    ligne[cle_col] = v
            if ligne:
                valeurs[cle_ligne] = ligne
        if valeurs:
            saisie['grilles'][grille['cle']] = valeurs
    for grille in test.get('libres', []):
        lignes = []
        for n in range(40):
            cellules = [post.get(f'{cle}__l__{grille["cle"]}__{n}__{c}', '').strip()[:120]
                        for c in range(len(grille['colonnes']))]
            if any(cellules):
                lignes.append(cellules)
        if lignes:
            saisie['libres'][grille['cle']] = lignes
    for champ in test.get('champs', []):
        v = post.get(f'{cle}__c__{champ[0]}', '').strip()[:300]
        if champ[2] == 'choix' and v not in champ[3]:
            v = ''
        if v:
            saisie['champs'][champ[0]] = v
    return saisie


def a_des_valeurs(saisie):
    return bool(saisie and (saisie.get('grilles') or saisie.get('libres') or saisie.get('champs')))


def nom_affiche(cle, saisie=None):
    """Nom long du test (le nom saisi pour une « autre épreuve »)."""
    if cle.startswith('autre'):
        nom = ((saisie or {}).get('champs') or {}).get('nom')
        return nom or "Autre épreuve"
    return TESTS[cle]['nom_long']


def nom_court(cle, saisie=None):
    if cle.startswith('autre'):
        return ((saisie or {}).get('champs') or {}).get('nom') or "Autre épreuve"
    return TESTS[cle]['nom']


def presentation(cle, saisie=None):
    if cle.startswith('autre'):
        return ((saisie or {}).get('champs') or {}).get('presentation', '')
    return TESTS[cle]['description']


def _grille(saisie, cle_grille):
    return ((saisie or {}).get('grilles') or {}).get(cle_grille) or {}


def _champ(saisie, cle_champ):
    return ((saisie or {}).get('champs') or {}).get(cle_champ, '')


# --- résultats : tableaux, remarques, graphiques, synthèse, valeurs pour la cohérence -------

def resultats(cle, saisie):
    """-> {'tableaux': [(titre|None, entetes, lignes)], 'remarques': [str], 'figures': [ref],
           'synthese': [[épreuve, résultat, lecture]], 'valeurs': [{'noms', 'valeur', 'percentile'}],
           'niveaux': [{'noms', 'niveau'}]}"""
    test = TESTS[cle]
    vide = {'tableaux': [], 'remarques': [], 'figures': [], 'synthese': [], 'valeurs': [], 'niveaux': []}
    if not a_des_valeurs(saisie):
        return dict(vide, remarques=["Scores non encore saisis : ouvrez « Scores et informations » pour les renseigner."])
    if test.get('type') == 'wechsler':
        res = _wechsler(cle, test, saisie)
    else:
        res = CALCULS.get(cle, _generique)(cle, test, saisie)
    for k, v in vide.items():
        res.setdefault(k, v)
    # Grilles libres communes (BHK, Conners, NEPSY-II, autres épreuves)
    for grille in test.get('libres', []):
        lignes = ((saisie.get('libres') or {}).get(grille['cle'])) or []
        if lignes:
            res['tableaux'].append((grille['titre'] if len(test.get('libres')) > 1 or test.get('grilles') else None,
                                    grille['colonnes'], [[_v(c) for c in l] for l in lignes]))
            if cle.startswith('autre') or cle in ('conners', 'nepsy2'):
                nom = nom_court(cle, saisie)
                res['synthese'].extend([f"{nom} - {l[0]}", _v(l[1]) if len(l) > 1 else '-',
                                        _v(l[-1]) if len(l) > 2 else '-'] for l in lignes if l and l[0])
    return res


def _percentile_txt(p):
    p = (p or '').strip()
    return f"P{p}" if p and p[0].isdigit() else p


def _wechsler(cle, test, saisie):
    nom = test['nom']
    zones = test['zones']
    indices = _grille(saisie, 'indices')
    libelles = dict(test['grilles'][0]['lignes'])
    lignes, synthese, valeurs, points = [], [], [], []
    for sigle, libelle in test['grilles'][0]['lignes']:
        ligne = indices.get(sigle)
        if not ligne:
            continue
        note = nombre(ligne.get('note'))
        description = ligne.get('description') or zone(note, zones)
        lignes.append([libelle, _v(ligne.get('note')), _v(ligne.get('percentile')), _v(ligne.get('ic')), description or '-'])
        if note is not None:
            synthese.append([f"{nom} - {sigle}", f"{fmt(note)} - {_percentile_txt(ligne.get('percentile'))}".rstrip(' -'),
                             description or '-'])
            valeurs.append({'noms': [sigle], 'valeur': note, 'percentile': nombre(ligne.get('percentile'))})
            if sigle not in ('IAG', 'ICC'):
                points.append(sigle)
    tableaux, remarques, figures = [], [], []
    if lignes:
        tableaux.append(("Indices", ["Indice", "Note composite", "Rang percentile", "IC 95 %", "Description qualitative"],
                         lignes))
        if len(points) >= 2:
            figures.append(f'{cle}.indices')

    # Homogénéité du profil : écart entre l'indice principal le plus haut et le plus bas
    principaux = [(s, nombre(indices[s].get('note'))) for s in libelles if s in INDICES_PRINCIPAUX
                  and s in indices and nombre(indices[s].get('note')) is not None]
    if len(principaux) >= 2:
        haut = max(principaux, key=lambda p: p[1])
        bas = min(principaux, key=lambda p: p[1])
        ecart = haut[1] - bas[1]
        if ecart >= 23:
            remarques.append(f"Écart de {fmt(ecart)} points entre l'indice le plus élevé ({haut[0]} = {fmt(haut[1])}) "
                             f"et le plus faible ({bas[0]} = {fmt(bas[1])}), supérieur à 1,5 écart-type : "
                             "le QIT est à interpréter avec prudence, au profit d'une lecture par indices.")
        comparaisons = []
        for n, (s1, v1) in enumerate(principaux):
            for s2, v2 in principaux[n + 1:]:
                diff = v1 - v2
                lecture = (f"{s1} > {s2}" if diff > 0 else f"{s2} > {s1}") if abs(diff) >= 15 else "Écart inférieur à 15 points"
                comparaisons.append([f"{s1} - {s2}", f"{'+' if diff > 0 else ''}{fmt(diff)}", lecture])
        tableaux.append(("Comparaisons entre les indices", ["Comparaison", "Différence", "Lecture (seuil indicatif : 15 points)"],
                         comparaisons))
        remarques.append("Les écarts entre indices sont indiqués à titre de repère (15 points = 1 écart-type) : "
                         "leur significativité statistique se vérifie dans les tables de l'édition utilisée.")

    # Subtests : forces et faiblesses relatives (écart de 3 points ou plus à la moyenne des notes standard)
    subtests = _grille(saisie, 'subtests')
    notes = [nombre(l.get('ns')) for l in subtests.values() if nombre(l.get('ns')) is not None]
    moyenne = sum(notes) / len(notes) if notes else None
    lignes_sub = []
    for code, libelle in test['grilles'][1]['lignes']:
        ligne = subtests.get(code)
        if not ligne:
            continue
        ns = nombre(ligne.get('ns'))
        lecture = ''
        if ns is not None and moyenne is not None and len(notes) >= 4:
            if ns - moyenne >= 3:
                lecture = 'Point fort relatif'
            elif moyenne - ns >= 3:
                lecture = 'Point faible relatif'
        lignes_sub.append([test['indice_des_subtests'].get(code, ''), libelle, _v(ligne.get('brute')),
                           _v(ligne.get('ns')), lecture or '-'])
        if ns is not None:
            valeurs.append({'noms': [libelle], 'valeur': ns, 'percentile': None})
    if lignes_sub:
        tableaux.append(("Subtests", ["Indice", "Subtest", "Note brute", "Note standard", "Lecture"], lignes_sub))
        if moyenne is not None and len(notes) >= 4:
            remarques.append(f"Moyenne des notes standard : {fmt(round(moyenne, 1))} ; un écart de 3 points ou plus "
                             "à cette moyenne signale un point fort ou faible relatif.")
        if len(notes) >= 3:
            figures.append(f'{cle}.subtests')
    return {'tableaux': tableaux, 'remarques': remarques, 'figures': figures, 'synthese': synthese, 'valeurs': valeurs}


def profil_d2r(ns_cct, ns_e):
    """Quadrant du profil d2-R : rythme (CCT) en abscisse, exactitude (E %) en ordonnée."""
    if ns_cct is None or ns_e is None:
        return ''
    if ns_cct >= 100:
        return 'Attentif et concentré' if ns_e >= 100 else 'Impulsif'
    return 'Réfléchi' if ns_e >= 100 else 'Ni attentif ni concentré'


def _d2r_papier(cle, test, saisie):
    scores = _grille(saisie, 'scores')
    lignes, synthese, valeurs = [], [], []
    noms_courts = {'CCT': "CCT", 'E': "Erreurs", 'CC': "Concentration"}
    for code, libelle in test['grilles'][0]['lignes']:
        ligne = scores.get(code)
        if not ligne:
            continue
        lecture = zone(ligne.get('ns'), ZONES_D2R)
        lignes.append([libelle, _v(ligne.get('ns')), _v(ligne.get('percentile')), lecture or '-'])
        if nombre(ligne.get('ns')) is not None:
            synthese.append([f"d2-R - {noms_courts[code]}", f"{_v(ligne.get('ns'))} - {_percentile_txt(ligne.get('percentile'))}".rstrip(' -'),
                             lecture or '-'])
            valeurs.append({'noms': [code] if code != 'E' else [], 'valeur': nombre(ligne.get('ns')),
                            'percentile': nombre(ligne.get('percentile'))})
    profil = _champ(saisie, 'profil') or profil_d2r(nombre((scores.get('CCT') or {}).get('ns')),
                                                     nombre((scores.get('E') or {}).get('ns')))
    tableaux = []
    if lignes:
        if profil:
            lignes.append(["Profil", profil, '', ''])
        tableaux.append((None, ["Indicateur", "Note standard", "Percentile", "Interprétation"], lignes))
    return {'tableaux': tableaux, 'synthese': synthese,
            'valeurs': [v for v in valeurs if v['noms']]}


def _tmt(cle, test, saisie):
    parties = _grille(saisie, 'parties')
    lignes, synthese = [], []
    temps = {}
    for code, libelle in test['grilles'][0]['lignes']:
        ligne = parties.get(code)
        if not ligne:
            continue
        t, e = nombre(ligne.get('temps')), nombre(ligne.get('erreurs'))
        temps[code] = t
        resultat = ' - '.join(x for x in [f"{fmt(t)} s" if t is not None else '',
                                          f"{fmt(e)} erreur{'s' if (e or 0) > 1 else ''}" if e is not None else ''] if x)
        lignes.append([libelle, resultat or '-', ligne.get('interpretation') or '-'])
        synthese.append([libelle, resultat or '-', ligne.get('interpretation') or '-'])
    if temps.get('A') and temps.get('B') is not None:
        lignes.append(["Indice B - A", f"{fmt(temps['B'] - temps['A'])} s", _champ(saisie, 'interpretation_ba') or '-'])
        lignes.append(["Indice B/A", fmt(round(temps['B'] / temps['A'], 2)), _champ(saisie, 'interpretation_ratio') or '-'])
    tableaux = [(None, ["Mesure", "Résultat", "Interprétation"], lignes)] if lignes else []
    remarques = [f"Normes : {_champ(saisie, 'normes')}."] if _champ(saisie, 'normes') else []
    valeurs = [{'noms': [f'TMT-{c}'], 'valeur': t, 'percentile': None} for c, t in temps.items() if t is not None]
    return {'tableaux': tableaux, 'remarques': remarques, 'synthese': synthese, 'valeurs': valeurs}


def _stroop(cle, test, saisie):
    conditions = _grille(saisie, 'conditions')
    lignes, synthese = [], []
    for code, libelle in test['grilles'][0]['lignes']:
        ligne = conditions.get(code)
        if not ligne:
            continue
        lignes.append([libelle, _v(ligne.get('score')), _v(ligne.get('erreurs')), _v(ligne.get('classe')),
                       _v(ligne.get('interpretation'))])
        synthese.append([f"Stroop - {libelle}", _v(ligne.get('score')), _v(ligne.get('interpretation') or ligne.get('classe'))])
    tableaux = [(None, ["Condition", "Temps / score", "Erreurs", "Classe / norme", "Interprétation"], lignes)] if lignes else []
    remarques = [f"Normes : {_champ(saisie, 'normes')}."] if _champ(saisie, 'normes') else []
    return {'tableaux': tableaux, 'remarques': remarques, 'synthese': synthese}


def _teach(cle, test, saisie):
    subtests = _grille(saisie, 'subtests')
    libelles = dict(test['grilles'][0]['lignes'])
    lignes, synthese = [], []
    for domaine, codes in test['domaines_attention']:
        presents = [c for c in codes if c in subtests]
        if not presents:
            continue
        lignes.append([domaine, '', ''])
        for code in presents:
            ligne = subtests[code]
            lignes.append([libelles[code], _v(ligne.get('brute')), _v(ligne.get('pc'))])
            synthese.append([f"TEA-Ch - {libelles[code]}", f"{_v(ligne.get('brute'))} ({_v(ligne.get('pc'))})", domaine])
    tableaux = [(None, ["Subtest", "Note brute", "Pourcentage cumulé / percentile"], lignes)] if lignes else []
    return {'tableaux': tableaux, 'synthese': synthese}


def _score_t(cle, test, saisie, fonction_zone, prefixe):
    echelles = _grille(saisie, 'echelles')
    lignes, synthese, valeurs = [], [], []
    for code, libelle in test['grilles'][0]['lignes']:
        ligne = echelles.get(code)
        if not ligne:
            continue
        lecture = fonction_zone(ligne.get('t'))
        cellules = [libelle, _v(ligne.get('brute')), _v(ligne.get('t'))]
        if 'percentile' in dict((c[0], c) for c in test['grilles'][0]['colonnes']):
            cellules.append(_v(ligne.get('percentile')))
        lignes.append(cellules + [lecture or '-'])
        t = nombre(ligne.get('t'))
        if t is not None:
            valeurs.append({'noms': [libelle.split(' (')[0]] + ([code] if code.isupper() else []), 'valeur': t,
                            'percentile': nombre(ligne.get('percentile')), 'type': 'T'})
            if lecture != 'Dans la norme' or code.isupper() or code.startswith('total'):
                resultat = f"T{fmt(t)}" + (f" - {_percentile_txt(ligne.get('percentile'))}" if ligne.get('percentile') else '')
                synthese.append([f"{prefixe} - {libelle}", resultat, lecture])
    return lignes, synthese, valeurs


def _brief_papier(cle, test, saisie):
    lignes, synthese, valeurs = _score_t(cle, test, saisie, zone_t_brief, 'BRIEF')
    tableaux = [(None, ["Échelle / indice", "Note brute", "Score T", "Percentile", "Interprétation"], lignes)] if lignes else []
    remarques = []
    if _champ(saisie, 'version'):
        remarques.append(f"Version : {_champ(saisie, 'version')}.")
    remarques.append("Lecture des scores T : 65 et plus = cliniquement significatif ; 60 à 64 = légèrement élevé ; "
                     "en dessous de 60 = dans la norme.")
    return {'tableaux': tableaux, 'remarques': remarques, 'synthese': synthese, 'valeurs': valeurs}


def _rcads(cle, test, saisie):
    lignes, synthese, valeurs = _score_t(cle, test, saisie, zone_t_rcads, 'RCADS')
    tableaux = [(None, ["Échelle", "Score brut", "Score T", "Lecture"], lignes)] if lignes else []
    remarques = [f"Version : {_champ(saisie, 'version')}."] if _champ(saisie, 'version') else []
    remarques.append("Lecture des scores T : 65 à 69 = zone limite ; 70 et plus = seuil clinique.")
    niveaux = [{'noms': ['RCADS'], 'niveau': zone_t_rcads((v.get('valeur'))), 'echelle': v['noms'][0]} for v in valeurs]
    return {'tableaux': tableaux, 'remarques': remarques, 'synthese': synthese, 'valeurs': valeurs, 'niveaux': niveaux}


def _bhk(cle, test, saisie):
    lignes, synthese = [], []
    for code, libelle, zone_cle in [('degradation', "Note totale de dégradation", 'degradation_zone'),
                                    ('vitesse', "Vitesse (caractères en 5 min)", 'vitesse_zone')]:
        if _champ(saisie, code):
            lignes.append([libelle, _champ(saisie, code), _champ(saisie, zone_cle) or '-'])
            synthese.append([f"BHK - {libelle.split(' (')[0]}", _champ(saisie, code), _champ(saisie, zone_cle) or '-'])
    tableaux = [(None, ["Mesure", "Résultat", "Lecture"], lignes)] if lignes else []
    valeurs = []
    if nombre(_champ(saisie, 'degradation')) is not None:
        valeurs.append({'noms': ['note totale de dégradation', 'dégradation'], 'valeur': nombre(_champ(saisie, 'degradation')),
                        'percentile': None})
    return {'tableaux': tableaux, 'synthese': synthese, 'valeurs': valeurs}


def _asrs(cle, test, saisie):
    a, b = nombre(_champ(saisie, 'partie_a')), nombre(_champ(saisie, 'partie_b'))
    lignes = []
    if a is not None:
        lignes.append(["Partie A", f"{fmt(a)} / 6", "Évocateur d'un TDAH (4 ou plus)" if a >= 4 else "Inférieur au seuil de repérage (4)"])
    if b is not None:
        lignes.append(["Partie B", f"{fmt(b)} / 12", "-"])
    return {'tableaux': [(None, ["Partie", "Score", "Lecture"], lignes)] if lignes else [],
            'synthese': [[f"ASRS - {l[0]}", l[1], l[2]] for l in lignes]}


def _diva5(cle, test, saisie):
    lignes = []
    ia_, ha = nombre(_champ(saisie, 'inattention_adulte')), nombre(_champ(saisie, 'hyperactivite_adulte'))
    ie, he = nombre(_champ(saisie, 'inattention_enfance')), nombre(_champ(saisie, 'hyperactivite_enfance'))
    if ia_ is not None:
        lignes.append(["6 symptômes d'inattention ou plus (âge adulte)", f"{'Oui' if ia_ >= 6 else 'Non'} ({fmt(ia_)}/9)"])
    if ha is not None:
        lignes.append(["6 symptômes d'hyperactivité/impulsivité ou plus (âge adulte)", f"{'Oui' if ha >= 6 else 'Non'} ({fmt(ha)}/9)"])
    if ie is not None:
        lignes.append(["Symptômes d'inattention dans l'enfance", f"{fmt(ie)}/9"])
    if he is not None:
        lignes.append(["Symptômes d'hyperactivité/impulsivité dans l'enfance", f"{fmt(he)}/9"])
    if _champ(saisie, 'enfance'):
        lignes.append(["Présence des symptômes dans l'enfance", _champ(saisie, 'enfance')])
    if _champ(saisie, 'retentissement'):
        lignes.append(["Retentissement fonctionnel dans plusieurs domaines", _champ(saisie, 'retentissement')])
    synthese = [["DIVA-5 - " + l[0], l[1], '-'] for l in lignes[:2]]
    return {'tableaux': [(None, ["Critère diagnostique", "Résultat"], lignes)] if lignes else [], 'synthese': synthese}


def _beck(niveaux_seuils, sigle):
    def calcul(cle, test, saisie):
        score = nombre(_champ(saisie, 'score'))
        if score is None:
            return {}
        niveau = zone(score, niveaux_seuils)
        noms = [sigle, test['nom_long'].split(' (')[0]]
        return {
            'tableaux': [(None, ["Mesure", "Score", "Niveau"], [["Score total", f"{fmt(score)} / 63", niveau]])],
            'synthese': [[sigle, f"{fmt(score)} / 63", niveau]],
            'valeurs': [{'noms': [sigle], 'valeur': score, 'percentile': None}],
            'niveaux': [{'noms': noms, 'niveau': niveau}],
        }
    return calcul


def _generique(cle, test, saisie):
    return {}


CALCULS = {
    'd2r_papier': _d2r_papier,
    'tmt': _tmt,
    'stroop': _stroop,
    'teach': _teach,
    'brief_papier': _brief_papier,
    'rcads': _rcads,
    'bhk': _bhk,
    'asrs': _asrs,
    'diva5': _diva5,
    'bai': _beck(NIVEAUX_BAI, 'BAI'),
    'bdi': _beck(NIVEAUX_BDI, 'BDI'),
}


# --- graphiques ------------------------------------------------------------------------------

def donnees_figure(cle, saisie, partie):
    """Points d'un graphique de profil : {'titre', 'points': [(libellé, valeur, ic_bas, ic_haut)],
    'min', 'max', 'bande': (bas, haut), 'pas'} ou None."""
    test = TESTS.get(cle)
    if not test or test.get('type') != 'wechsler':
        return None
    if partie == 'indices':
        indices = _grille(saisie, 'indices')
        points = []
        for sigle, _ in test['grilles'][0]['lignes']:
            if sigle in ('IAG', 'ICC') or sigle not in indices:
                continue
            note = nombre(indices[sigle].get('note'))
            if note is None:
                continue
            ic = re.findall(r'\d+', indices[sigle].get('ic') or '')
            bas, haut = (int(ic[0]), int(ic[1])) if len(ic) == 2 else (None, None)
            points.append((sigle, note, bas, haut))
        return {'titre': f"Profil des notes composites - {test['nom']}", 'points': points,
                'min': 40, 'max': 160, 'bande': (90, 110), 'pas': 10} if len(points) >= 2 else None
    if partie == 'subtests':
        subtests = _grille(saisie, 'subtests')
        points = [(libelle, nombre(subtests[code].get('ns')), None, None)
                  for code, libelle in test['grilles'][1]['lignes']
                  if code in subtests and nombre(subtests[code].get('ns')) is not None]
        return {'titre': f"Profil des notes standard aux subtests - {test['nom']}", 'points': points,
                'min': 1, 'max': 19, 'bande': (8, 12), 'pas': 1} if len(points) >= 3 else None
    return None


# --- formulaire de saisie (structure prête pour le gabarit) -------------------------------------

LIBELLES_DOMAINES = {
    'intellectuel': "Efficience intellectuelle", 'attention': "Attention", 'executif': "Fonctions exécutives",
    'neuropsy': "Batteries neuropsychologiques", 'graphomoteur': "Graphisme", 'questionnaire': "Questionnaires TDAH",
    'emotionnel': "Anxiété et humeur", 'autre': "Autres épreuves",
}
LIGNES_LIBRES_VIDES = 3


def groupes_catalogue():
    """[(libellé du domaine, [(cle, test)])] dans l'ordre des domaines."""
    groupes = []
    for domaine in ORDRE_DOMAINES:
        tests = [(cle, t) for cle, t in TESTS.items() if t['domaine'] == domaine]
        if tests:
            groupes.append((LIBELLES_DOMAINES[domaine], tests))
    return groupes


def formulaire(cle, saisie):
    test = TESTS[cle]
    saisie = saisie or saisie_vide()
    grilles = []
    for grille in test.get('grilles', []):
        valeurs = _grille(saisie, grille['cle'])
        lignes = []
        for cle_ligne, libelle in grille['lignes']:
            lignes.append({'libelle': libelle, 'cellules': [
                {'name': f'{cle}__g__{grille["cle"]}__{cle_ligne}__{cle_col}', 'type': type_col,
                 'value': (valeurs.get(cle_ligne) or {}).get(cle_col, '')}
                for cle_col, _, type_col in grille['colonnes']]})
        grilles.append({'titre': grille['titre'], 'colonnes': [c[1] for c in grille['colonnes']], 'lignes': lignes})
    libres = []
    for grille in test.get('libres', []):
        existantes = ((saisie.get('libres') or {}).get(grille['cle'])) or []
        lignes = []
        for n in range(min(40, len(existantes) + LIGNES_LIBRES_VIDES)):
            valeurs = existantes[n] if n < len(existantes) else []
            lignes.append([{'name': f'{cle}__l__{grille["cle"]}__{n}__{c}',
                            'value': valeurs[c] if c < len(valeurs) else ''} for c in range(len(grille['colonnes']))])
        libres.append({'titre': grille['titre'], 'colonnes': grille['colonnes'], 'lignes': lignes,
                       'prefixe': f'{cle}__l__{grille["cle"]}'})
    champs = [{'name': f'{cle}__c__{c[0]}', 'cle': c[0], 'libelle': c[1], 'type': c[2], 'choix': c[3] if len(c) > 3 else [],
               'value': _champ(saisie, c[0])} for c in test.get('champs', [])]
    return {'grilles': grilles, 'libres': libres, 'champs': champs}
