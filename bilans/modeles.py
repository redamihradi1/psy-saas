"""Modèles de bilan, construits sur la structure de vrais bilans neuropsychologiques (page de
garde, anamnèse, observation, tests utilisés, un chapitre par test, conclusion par plans,
recommandations par catégorie, tableau de synthèse, signature).

Chaque section a un type :
- 'auto'  : remplie par le code à partir des données (jamais par l'IA - aucun score inventé) ;
- 'ia'    : rédigée par l'IA (première version), selon sa `consigne` ;
- 'libre' : écrite par le psychologue lui-même ;
- 'tests' : emplacement des chapitres de résultats, un par test inclus (sections de type
            'test' : tableaux et graphiques calculés, puis « Interprétation » rédigée par l'IA).
`page` : l'export commence cette section sur une nouvelle page.
`besoin: 'clinique'` : section rédigée par l'IA seulement si l'anamnèse ou des notes de séance sont
fournies (sinon elle inventerait des faits plausibles) ; elle reste alors à compléter par le psy.
Le psychologue peut ensuite tout modifier, quelle que soit la section.
"""

PLACEHOLDER_IA = "[Section à rédiger : cliquez sur « Rédiger avec l'IA » ou écrivez directement ici.]"
# Textes d'attente des versions précédentes, encore présents dans des bilans existants
ANCIENS_PLACEHOLDERS_IA = ("[Section à rédiger : cliquez sur « Première version IA » ou écrivez directement ici.]",)
PLACEHOLDER_LIBRE = "[À compléter par le psychologue.]"
TITRE_INTERPRETATION = "Interprétation"

SOUS_TITRE_ATTENTION = "Évaluation des capacités attentionnelles et exécutives"

_IDENTITE = {'cle': 'identite', 'titre': "Identité", 'type': 'auto', 'generateur': 'identite'}
_TESTS_UTILISES = {'cle': 'tests_utilises', 'titre': "Tests utilisés", 'type': 'auto', 'generateur': 'tests_utilises',
                   'page': True}
_TESTS = {'cle': 'resultats', 'type': 'tests'}
_SYNTHESE = {'cle': 'synthese_resultats', 'titre': "Synthèse des résultats aux tests", 'type': 'auto',
             'generateur': 'synthese_resultats', 'page': True}
_SIGNATURE = {'cle': 'signature', 'titre': "Signature", 'type': 'auto', 'generateur': 'signature'}

_CONCLUSION = {
    'cle': 'conclusion', 'titre': "Conclusion", 'type': 'ia', 'page': True,
    'consigne': "Synthèse intégrative en plusieurs paragraphes, un par plan, chacun commençant par « Sur le "
                "plan intellectuel, », « Sur le plan attentionnel, », « Sur le plan exécutif, », puis selon les "
                "données « Sur le plan graphomoteur, » et « Sur le plan émotionnel, ». Rappelle dans chaque "
                "paragraphe les scores clés entre parenthèses. Ajoute un paragraphe « L'analyse croisée des "
                "résultats... » qui relie les épreuves entre elles, les observations de passation et l'anamnèse "
                "(convergences, dissociations, facteurs qui majorent les difficultés comme l'anxiété ou la fatigue). "
                "N'écris un paragraphe que pour les plans documentés par au moins un test ou une observation : "
                "aucun paragraphe pour un plan sans données. Reprends le niveau de chaque score tel qu'il figure dans "
                "la colonne de lecture du tableau (un score « dans la norme » n'est jamais « modéré » ni « élevé »). "
                "Termine par une hypothèse diagnostique prudente (« le fonctionnement apparaît compatible avec... ») "
                "uniquement si les données la soutiennent, éventuellement suivie d'une liste « - » des éléments "
                "associés ; sinon, conclus sur les points d'appui et les fragilités. Si un bilan ou un diagnostic "
                "antérieur est mentionné, situe l'évaluation dans sa continuité (évolution, persistance).",
}
_RECOMMANDATIONS_ENFANT = {
    'cle': 'recommandations', 'titre': "Recommandations", 'type': 'ia', 'page': True,
    'consigne': "Recommandations organisées en catégories numérotées, chacune introduite par une ligne "
                "« ## 1. Titre de la catégorie », suivie d'une liste « - » d'actions concrètes. Choisis les "
                "catégories utiles parmi : suivi médical et psychothérapeutique (pédopsychiatre, psychothérapie "
                "axée sur l'anxiété...) ; remédiation cognitive (objectifs précis) ; prises en charge "
                "complémentaires (orthophonie, psychomotricité, ergothérapie) uniquement si un résultat du "
                "bilan les justifie explicitement (sinon n'en parle pas) ; "
                "aménagements scolaires, avec des sous-groupes en gras (**Attention**, **Production écrite**, "
                "**Raisonnement**, **Organisation**) ; aménagements pour les examens (temps majoré, salle calme, "
                "vérification des consignes, ordinateur...) ; guidance parentale. Chaque recommandation doit "
                "répondre à une difficulté objectivée dans le bilan. Termine par une phrase sur la concertation "
                "avec l'équipe pédagogique.",
}
_RECOMMANDATIONS_ADULTE = {
    'cle': 'recommandations', 'titre': "Recommandations et orientation", 'type': 'ia', 'page': True,
    'consigne': "Recommandations organisées en catégories numérotées (ligne « ## 1. Titre » puis liste « - ») : "
                "orientation médicale (psychiatre pour avis diagnostique et thérapeutique si un TDAH est évoqué), "
                "accompagnement psychothérapeutique (anxiété, humeur, épuisement...), stratégies de compensation au "
                "quotidien et au travail (organisation, gestion du temps, réduction des distracteurs), "
                "aménagements professionnels ou d'études si pertinents, hygiène de vie et consommations si "
                "mentionnées. Chaque recommandation répond à une difficulté objectivée dans le bilan.",
}

MODELES = {
    'neuropsy_enfant': {
        'titre': "Bilan neuropsychologique",
        'nom': "Bilan neuropsychologique - enfant / adolescent",
        'sous_titre': SOUS_TITRE_ATTENTION,
        'public': 'enfant',
        'description': "Attention et fonctions exécutives : WISC-V, d2-R, TEA-Ch, Stroop, BRIEF, RCADS, BHK...",
        'icone': 'fa-child',
        'tests_suggeres': ['brief', 'd2r', 'vineland'],
        'externes_suggeres': ['wisc5', 'teach', 'stroop', 'rcads'],
        'sections': [
            _IDENTITE,
            {'cle': 'motif_reference', 'titre': "Motif de référence", 'type': 'ia', 'page': True,
             'consigne': "Un paragraphe : qui adresse l'enfant (médecin, pédopsychiatre, école, parents) et dans "
                         "quel cadre (suivi déjà en place, diagnostic déjà posé, suspicion), puis l'objectif de "
                         "l'évaluation (préciser les forces et fragilités, actualiser le fonctionnement, étayer une "
                         "demande d'aménagements...)."},
            {'cle': 'motif_consultation', 'titre': "Motif de consultation", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Liste « - » de 3 à 7 difficultés rapportées (attention, comportement, apprentissages, "
                         "émotions, autonomie), formulées brièvement, sans phrase d'introduction."},
            {'cle': 'scolarite', 'titre': "Scolarité", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Scolarité de l'enfant : établissement et classe, parcours (redoublement, changements), "
                         "puis sur le plan scolaire, comportemental et social, activités et loisirs si connus. "
                         "Un court paragraphe ou une liste « - » commençant par « Sur le plan scolaire : », etc."},
            {'cle': 'anamnese', 'titre': "Anamnèse", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Histoire des difficultés (depuis quand, comment elles se manifestent), éléments de "
                         "développement, de santé, de contexte familial et émotionnel utiles à la compréhension, "
                         "en 1 à 3 paragraphes, uniquement à partir des données."},
            {'cle': 'observation', 'titre': "Observation clinique et déroulement de la passation", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "À partir des observations et notes fournies uniquement : nombre et durée des séances si "
                         "connus, puis une liste « - » d'observations (contact, coopération, compréhension des "
                         "consignes, attention, impulsivité, agitation, anxiété, verbalisations, stratégie : "
                         "rapidité ou précision). Si aucune observation n'est fournie, écris seulement "
                         "« [à compléter : observations de la passation] »."},
            _TESTS_UTILISES,
            _TESTS,
            _CONCLUSION,
            _RECOMMANDATIONS_ENFANT,
            _SYNTHESE,
            _SIGNATURE,
        ],
    },
    'neuropsy_adulte': {
        'titre': "Bilan neuropsychologique",
        'nom': "Bilan neuropsychologique - adulte",
        'sous_titre': SOUS_TITRE_ATTENTION,
        'public': 'adulte',
        'description': "Bilan attentionnel de l'adulte (hypothèse de TDAH) : WAIS-IV, d2-R, TMT, Stroop, ASRS, "
                       "DIVA-5, BAI, BDI...",
        'icone': 'fa-user',
        'tests_suggeres': ['d2r', 'beck'],
        'externes_suggeres': ['wais4', 'tmt', 'stroop', 'asrs', 'diva5', 'bai'],
        'sections': [
            _IDENTITE,
            {'cle': 'etapes', 'titre': "Étapes du bilan", 'type': 'auto', 'generateur': 'etapes', 'page': True},
            {'cle': 'motif_demande', 'titre': "Motif de la demande", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "1 à 3 courts paragraphes : la demande (bilan attentionnel...), le contexte qui l'amène, "
                         "qui l'a suggérée, et l'objectif du bilan."},
            {'cle': 'plainte', 'titre': "Plainte actuelle", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Les difficultés décrites aujourd'hui (organisation, gestion du temps, oublis, "
                         "attention soutenue, impulsivité, fatigue...), les stratégies déjà essayées, et le "
                         "contexte récent qui les majore, en 2 à 4 paragraphes."},
            {'cle': 'retentissement', 'titre': "Retentissement fonctionnel", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Retentissement professionnel, quotidien et personnel des difficultés, en 1 à 3 paragraphes."},
            {'cle': 'histoire', 'titre': "Histoire développementale et scolaire", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Présence des difficultés dès l'enfance, remarques des enseignants, scolarité, "
                         "orientations, parcours d'études et professionnel (liste « - » des étapes si utile)."},
            {'cle': 'antecedents', 'titre': "Antécédents personnels et contexte de vie", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Antécédents personnels et familiaux, contexte de vie actuel, consommations, en "
                         "paragraphes sobres et factuels. Termine par un paragraphe qui justifie la réalisation du "
                         "bilan et les hypothèses à explorer (dont les diagnostics différentiels)."},
            _TESTS_UTILISES,
            _TESTS,
            _CONCLUSION,
            _RECOMMANDATIONS_ADULTE,
            _SYNTHESE,
            _SIGNATURE,
        ],
    },
    'reevaluation': {
        'titre': "Bilan neuropsychologique",
        'nom': "Réévaluation neuropsychologique",
        'sous_titre': "Actualisation du bilan",
        'public': 'enfant',
        'description': "Actualisation d'un bilan antérieur : évolution du profil, aménagements à maintenir ou ajuster.",
        'icone': 'fa-redo-alt',
        'tests_suggeres': ['brief', 'd2r'],
        'externes_suggeres': ['wisc5', 'tmt'],
        'sections': [
            _IDENTITE,
            {'cle': 'motif_reference', 'titre': "Motif de référence", 'type': 'ia', 'page': True,
             'consigne': "Un paragraphe : le patient est reçu dans le cadre de l'actualisation de son bilan "
                         "(rappelle la date ou la période du bilan antérieur s'il est mentionné), objectif : "
                         "apprécier l'évolution, préciser les besoins actuels et réexaminer les aménagements."},
            {'cle': 'motif_consultation', 'titre': "Motif de consultation", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Liste « - » de 3 à 6 difficultés actuellement rapportées, formulées brièvement."},
            {'cle': 'scolarite', 'titre': "Scolarité", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Un paragraphe : établissement, classe, comment l'entourage décrit le patient et dans "
                         "quelles conditions son efficience diminue."},
            {'cle': 'entretien', 'titre': "Compte rendu de l'entretien", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Un paragraphe sur le contact, la qualité des échanges, le discours, l'investissement et "
                         "les éléments émotionnels observés (anxiété de performance, perfectionnisme...), à partir "
                         "des observations fournies uniquement ; sinon « [à compléter] »."},
            {'cle': 'passation', 'titre': "Passation", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Liste « - » des observations pendant les épreuves (coopération, compréhension des "
                         "consignes, fluctuations attentionnelles, vagabondage mental, lenteur, verbalisations...), "
                         "à partir des observations fournies uniquement ; sinon « [à compléter] »."},
            _TESTS_UTILISES,
            _TESTS,
            _CONCLUSION,
            {'cle': 'recommandations', 'titre': "Recommandations et adaptations pour la scolarité", 'type': 'ia',
             'page': True,
             'consigne': "Un premier paragraphe sur les aménagements déjà mis en place et leur effet (s'ils sont "
                         "mentionnés), un second qui justifie leur maintien ou ajustement au regard du profil "
                         "actuel, sans abaisser les exigences cognitives. Puis une liste numérotée « 1. **Titre** : "
                         "explication » (maintien du tiers-temps, adaptation des consignes, réduction des "
                         "distracteurs, allègement de la charge exécutive, fractionnement des tâches, soutien à "
                         "l'organisation, modalités d'évaluation, prise en compte de l'anxiété...), en ne gardant "
                         "que ce qui répond au profil. Termine par une phrase sur la concertation avec l'équipe "
                         "pédagogique."},
            _SYNTHESE,
            _SIGNATURE,
        ],
    },
    'psy_adulte': {
        'titre': "Bilan psychologique",
        'nom': "Bilan psychologique - adulte",
        'sous_titre': "",
        'public': 'adulte',
        'description': "Symptomatologie anxieuse et dépressive (Beck, STAI, BAI).",
        'icone': 'fa-user-friends',
        'tests_suggeres': ['beck', 'stai'],
        'externes_suggeres': [],
        'sections': [
            _IDENTITE,
            {'cle': 'motif', 'titre': "Motif de consultation", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Reformule le motif de consultation et les attentes du patient, en 1 paragraphe."},
            {'cle': 'contexte', 'titre': "Histoire et contexte de vie", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Contexte de vie (situation familiale, professionnelle, antécédents, hygiène de vie : "
                         "sommeil, alimentation, substances), en 1 à 2 paragraphes."},
            {'cle': 'observations', 'titre': "Observations cliniques", 'type': 'libre',
             'aide': "Présentation, discours, affect, alliance thérapeutique..."},
            _TESTS_UTILISES,
            _TESTS,
            {'cle': 'synthese', 'titre': "Synthèse", 'type': 'ia', 'page': True,
             'consigne': "Synthèse clinique en 1 à 3 paragraphes reliant motif, contexte et résultats. Si une "
                         "alerte (idées suicidaires) est signalée, mentionne-la comme point à évaluer en priorité. "
                         "Hypothèses prudentes, sans diagnostic définitif."},
            {'cle': 'recommandations', 'titre': "Orientation et recommandations", 'type': 'ia',
             'consigne': "Liste « - » de 3 à 5 recommandations (type et rythme de suivi, orientation éventuelle "
                         "vers un médecin ou un psychiatre, pistes de travail)."},
            _SIGNATURE,
        ],
    },
    'compte_rendu_suivi': {
        'titre': "Compte rendu de suivi",
        'nom': "Compte rendu de suivi",
        'sous_titre': "",
        'public': '',
        'description': "Point d'étape d'une prise en charge, à partir des notes de séance.",
        'icone': 'fa-notes-medical',
        'tests_suggeres': [],
        'externes_suggeres': [],
        'sections': [
            _IDENTITE,
            {'cle': 'periode', 'titre': "Période de suivi", 'type': 'auto', 'generateur': 'periode_suivi'},
            {'cle': 'evolution', 'titre': "Évolution", 'type': 'ia', 'besoin': 'clinique',
             'consigne': "Décris l'évolution du patient au fil des séances (thèmes travaillés, progrès, "
                         "difficultés persistantes) à partir des notes de séance, en 2 à 3 paragraphes."},
            {'cle': 'perspectives', 'titre': "Perspectives", 'type': 'libre',
             'aide': "Suite envisagée, objectifs des prochaines séances..."},
            _SIGNATURE,
        ],
    },
}

MODELE_CHOICES = [(cle, modele['nom']) for cle, modele in MODELES.items()]

# Sections rédigées en dernier par l'IA : elles s'appuient sur les interprétations déjà écrites.
SECTIONS_FINALES = {'conclusion', 'synthese', 'recommandations'}


def sections_ia(cle_modele):
    return [s for s in MODELES[cle_modele]['sections'] if s['type'] == 'ia']


def section_du_modele(cle_modele, cle_section):
    for section in MODELES.get(cle_modele, {}).get('sections', []):
        if section.get('cle') == cle_section:
            return section
    return None
