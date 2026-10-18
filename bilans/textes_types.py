"""Bibliothèque de textes réutilisables fournis par défaut (insérables en un clic dans l'éditeur).
Chaque cabinet peut les personnaliser, les masquer ou ajouter les siens (modèle TexteType).
Une ligne commençant par « - » devient une puce à l'insertion."""
from . import tests_externes as te

_DEFINITIONS = [
    ('def_attention_selective', "Attention sélective",
     "L'attention sélective correspond à la capacité à orienter son attention vers les informations pertinentes "
     "tout en filtrant les éléments distracteurs."),
    ('def_attention_soutenue', "Attention soutenue",
     "L'attention soutenue correspond à la capacité à maintenir un niveau d'attention stable sur une période "
     "prolongée, notamment lors de tâches monotones ou répétitives."),
    ('def_attention_divisee', "Attention divisée",
     "L'attention divisée correspond à la capacité à partager ses ressources attentionnelles entre plusieurs "
     "sources d'information ou plusieurs tâches menées simultanément."),
    ('def_flexibilite', "Flexibilité cognitive",
     "La flexibilité cognitive correspond à la capacité à modifier une stratégie mentale ou à passer d'une règle "
     "à une autre selon les exigences de la situation."),
    ('def_inhibition', "Contrôle inhibiteur",
     "Le contrôle inhibiteur désigne la capacité à freiner une réponse automatique ou impulsive au profit d'une "
     "réponse plus adaptée à la consigne."),
    ('def_memoire_travail', "Mémoire de travail",
     "La mémoire de travail permet de maintenir temporairement des informations à l'esprit et de les manipuler "
     "pendant la réalisation d'une tâche (suivre une consigne en plusieurs étapes, calculer mentalement...)."),
    ('def_vitesse_traitement', "Vitesse de traitement",
     "La vitesse de traitement reflète la rapidité avec laquelle des informations simples sont perçues, traitées "
     "et transformées en réponse, sous contrainte de temps."),
    ('def_brief_inhibition', "BRIEF - Inhibition",
     "L'échelle d'inhibition explore la capacité à freiner une réponse impulsive, à attendre son tour et à "
     "interrompre un comportement au moment approprié."),
    ('def_brief_flexibilite', "BRIEF - Flexibilité",
     "L'échelle de flexibilité évalue la capacité à passer d'une activité ou d'une idée à une autre, à tolérer "
     "les changements et les imprévus, et à ajuster sa stratégie."),
    ('def_brief_controle_emotionnel', "BRIEF - Contrôle émotionnel",
     "L'échelle de contrôle émotionnel apprécie la capacité à moduler ses réactions émotionnelles : gérer la "
     "frustration, contenir la colère, retrouver son calme après une contrariété."),
    ('def_brief_initiation', "BRIEF - Initiation",
     "L'échelle d'initiation renvoie à la capacité à se mettre en action de façon autonome, à commencer une tâche "
     "sans rappel extérieur et à générer des idées."),
    ('def_brief_memoire_travail', "BRIEF - Mémoire de travail",
     "L'échelle de mémoire de travail décrit la capacité à garder une information en tête pour mener une "
     "activité à son terme, suivre une consigne en plusieurs étapes et ne pas perdre le fil."),
    ('def_brief_planification', "BRIEF - Planification / organisation",
     "L'échelle de planification et d'organisation mesure la capacité à anticiper, à se fixer un but et à "
     "organiser les étapes nécessaires pour l'atteindre."),
    ('def_brief_organisation_materiel', "BRIEF - Organisation du matériel",
     "L'échelle d'organisation du matériel apprécie la façon de ranger, retrouver et gérer ses affaires et son "
     "espace de travail."),
    ('def_brief_controle', "BRIEF - Contrôle",
     "L'échelle de contrôle renvoie à l'autosurveillance : vérifier son travail, repérer ses erreurs et mesurer "
     "l'effet de son comportement sur les autres."),
    ('def_brief_irc', "BRIEF - Indice de régulation comportementale",
     "L'indice de régulation comportementale regroupe l'inhibition, la flexibilité et le contrôle émotionnel : "
     "il renseigne sur la capacité globale à moduler son comportement et ses émotions."),
    ('def_brief_im', "BRIEF - Indice de métacognition",
     "L'indice de métacognition regroupe l'initiation, la mémoire de travail, la planification, l'organisation "
     "du matériel et le contrôle : il reflète la gestion active des tâches au quotidien."),
]

_RECOMMANDATIONS = [
    ('rec_tiers_temps', "Temps majoré",
     "Accorder un temps majoré (tiers-temps) lors des évaluations et des travaux chronométrés, compte tenu de la "
     "lenteur de traitement objectivée."),
    ('rec_consignes', "Consignes courtes et explicites",
     "Privilégier des consignes courtes, explicites et fractionnées, et vérifier leur compréhension avant "
     "l'engagement dans la tâche."),
    ('rec_distracteurs', "Réduction des distracteurs",
     "Installer l'élève dans un environnement limitant les distractions (premier rang, loin des fenêtres et des "
     "passages), avec uniquement le matériel nécessaire sur la table."),
    ('rec_double_tache', "Éviter la double tâche",
     "Limiter les situations de double tâche (écouter et écrire en même temps) et décomposer les activités "
     "complexes en étapes successives."),
    ('rec_fractionnement', "Fractionnement des tâches",
     "Organiser les activités longues en séquences plus courtes, avec des objectifs intermédiaires clairement "
     "définis et des pauses."),
    ('rec_organisation', "Soutien à l'organisation",
     "Encourager l'usage d'outils de planification (agenda, planning, listes de vérification) pour anticiper les "
     "échéances et organiser le travail."),
    ('rec_evaluation', "Modalités d'évaluation",
     "Lorsque la rapidité n'est pas la compétence évaluée, privilégier l'appréciation des connaissances, du "
     "raisonnement et de la qualité des réponses."),
    ('rec_anxiete', "Anxiété de performance",
     "Valoriser les efforts, les stratégies mises en œuvre et les progrès, afin de limiter l'impact de la "
     "pression évaluative sur les performances."),
    ('rec_ecrit', "Production écrite",
     "- Limiter la copie et fournir des supports de cours écrits.\n"
     "- Autoriser l'ordinateur pour les productions longues.\n"
     "- Ne pas pénaliser la présentation ni la qualité graphique : évaluer le fond plutôt que la forme."),
    ('rec_examens', "Aménagements d'examens",
     "- Temps majoré (tiers-temps).\n"
     "- Salle calme à effectif réduit.\n"
     "- Vérification de la compréhension des consignes en début d'épreuve.\n"
     "- Utilisation de l'ordinateur pour les productions écrites longues."),
    ('rec_remediation', "Remédiation cognitive",
     "Une prise en charge en remédiation cognitive est recommandée afin de renforcer l'attention soutenue et "
     "sélective, d'améliorer le contrôle inhibiteur et de soutenir la mise en place de stratégies."),
    ('rec_psychomotricite', "Psychomotricité / ergothérapie",
     "Au regard des difficultés graphomotrices objectivées, une prise en charge en psychomotricité et/ou en "
     "ergothérapie est recommandée afin d'améliorer la qualité du geste graphique et d'en réduire le coût cognitif."),
    ('rec_orthophonie', "Bilan orthophonique",
     "Un bilan orthophonique du langage oral et écrit est recommandé afin de préciser les difficultés observées."),
    ('rec_suivi', "Suivi médical et psychothérapeutique",
     "La poursuite du suivi pédopsychiatrique est recommandée, ainsi que la mise en place d'un accompagnement "
     "psychothérapeutique axé sur l'anxiété de performance."),
    ('rec_guidance', "Guidance parentale",
     "Une guidance parentale est proposée afin d'accompagner la mise en place de routines structurantes à la "
     "maison, notamment au moment des devoirs."),
    ('rec_concertation', "Concertation avec l'équipe pédagogique",
     "La mise en œuvre de ces aménagements nécessite une concertation avec l'équipe pédagogique, afin d'en "
     "assurer une application régulière et cohérente."),
]

_MENTIONS = [
    ('men_non_figes', "Résultats non figés (enfant)",
     "Les résultats obtenus ne sont pas figés : les compétences d'un enfant évoluent avec son développement, ses "
     "apprentissages et son environnement. Ce bilan reflète une photographie actuelle de son fonctionnement et "
     "doit être lu dans une perspective dynamique."),
    ('men_qit', "QIT peu interprétable",
     "Le QI total n'est pas interprétable en raison de l'hétérogénéité marquée entre les indices : une lecture "
     "par domaines est privilégiée."),
    ('men_significativite', "Significativité des écarts entre indices",
     "La significativité statistique des écarts entre indices doit être confirmée à l'aide des tables de "
     "comparaison de l'édition utilisée."),
    ('men_brief_lecture', "Lecture des scores T (BRIEF)",
     "Lecture des scores T : 65 et plus, cliniquement significatif ; de 60 à 64, légèrement élevé ; en dessous "
     "de 60, dans la norme."),
    ('men_source_tierce', "Critère développemental (adulte)",
     "L'absence de confirmation par une source tierce (parent, bulletins scolaires) limite la validité du "
     "critère développemental."),
]


def textes_par_defaut():
    """[{'cle', 'categorie', 'titre', 'contenu'}] - présentations des tests incluses."""
    textes = []
    for cle, test in te.TESTS.items():
        if test.get('description'):
            textes.append({'cle': f'pres_{cle}', 'categorie': 'presentation', 'titre': test['nom_long'],
                           'contenu': test['description']})
    from .donnees import NOMS_LONGS_TESTS, PRESENTATIONS_TESTS_PLATEFORME
    for cle, contenu in PRESENTATIONS_TESTS_PLATEFORME.items():
        textes.append({'cle': f'pres_plateforme_{cle}', 'categorie': 'presentation', 'titre': NOMS_LONGS_TESTS[cle],
                       'contenu': contenu})
    for categorie, liste in (('definition', _DEFINITIONS), ('recommandation', _RECOMMANDATIONS),
                             ('mention', _MENTIONS)):
        textes.extend({'cle': cle, 'categorie': categorie, 'titre': titre, 'contenu': contenu}
                      for cle, titre, contenu in liste)
    return textes


def bibliotheque(organization):
    """Textes par défaut, remplacés par la version personnalisée du cabinet s'il y en a une,
    sans les textes masqués, plus les textes ajoutés par le cabinet."""
    from .models import TexteType
    personnalises = {t.cle: t for t in TexteType.all_objects.filter(organization=organization).exclude(cle='')}
    textes = []
    for texte in textes_par_defaut():
        perso = personnalises.get(texte['cle'])
        if perso and perso.masque:
            continue
        if perso:
            texte = dict(texte, titre=perso.titre, contenu=perso.contenu, id=perso.id, personnalise=True)
        textes.append(texte)
    for perso in TexteType.all_objects.filter(organization=organization, cle='', masque=False):
        textes.append({'cle': '', 'id': perso.id, 'categorie': perso.categorie, 'titre': perso.titre,
                       'contenu': perso.contenu, 'personnalise': True})
    return textes
