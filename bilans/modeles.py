"""Modèles de bilan (fictifs pour l'instant, à ajuster sur de vrais exemples anonymisés).

Chaque section a un type :
- 'auto'  : remplie par le code à partir des données (jamais par l'IA - aucun score inventé) ;
- 'ia'    : rédigée par l'IA (première version), selon sa `consigne` ;
- 'libre' : écrite par le psychologue lui-même (observations, ressenti clinique...).
Le psychologue peut ensuite tout modifier, quelle que soit la section.
"""

PLACEHOLDER_IA = "[Section à rédiger : cliquez sur « Première version IA » ou écrivez directement ici.]"
PLACEHOLDER_LIBRE = "[À compléter par le psychologue.]"

MODELES = {
    'neuropsy_enfant': {
        'titre': "Bilan neuropsychologique",
        'description': "Enfant ou adolescent : comportement adaptatif, fonctions exécutives, attention "
                       "(Vineland, BRIEF, D2R).",
        'icone': 'fa-child',
        'tests_suggeres': ['vineland', 'brief', 'd2r'],
        'sections': [
            {'cle': 'identite', 'titre': "Identité", 'type': 'auto', 'generateur': 'identite'},
            {'cle': 'motif', 'titre': "Motif de la demande", 'type': 'ia',
             'consigne': "Reformule le motif de consultation et qui est à l'origine de la demande (parents, "
                         "école, médecin), en 1 paragraphe."},
            {'cle': 'anamnese', 'titre': "Éléments d'anamnèse", 'type': 'ia',
             'consigne': "Résume les éléments d'anamnèse utiles (développement, scolarité, santé, contexte "
                         "familial), en 1 à 2 paragraphes, sans rien ajouter qui ne soit pas dans les données."},
            {'cle': 'tests_administres', 'titre': "Outils d'évaluation", 'type': 'auto',
             'generateur': 'tests_administres'},
            {'cle': 'resultats', 'titre': "Résultats", 'type': 'auto', 'generateur': 'resultats'},
            {'cle': 'analyse', 'titre': "Analyse des résultats", 'type': 'ia',
             'consigne': "Commente les résultats test par test, en t'appuyant uniquement sur les scores fournis "
                         "et leurs seuils (zones normale / limite / significative). Signale les points forts et "
                         "les points de vigilance. Mentionne les limites de validité indiquées."},
            {'cle': 'observations', 'titre': "Observations cliniques pendant la passation", 'type': 'libre',
             'aide': "Comportement, coopération, attention, fatigabilité..."},
            {'cle': 'synthese', 'titre': "Synthèse", 'type': 'ia',
             'consigne': "Synthèse clinique en 1 à 2 paragraphes reliant le motif, l'anamnèse et les résultats. "
                         "Formule des hypothèses prudentes, jamais un diagnostic définitif."},
            {'cle': 'recommandations', 'titre': "Recommandations", 'type': 'ia',
             'consigne': "Liste de 3 à 6 recommandations concrètes (suivi, aménagements scolaires, "
                         "orientations éventuelles, conseils aux parents), sous forme de liste « - »."},
            {'cle': 'signature', 'titre': "Signature", 'type': 'auto', 'generateur': 'signature'},
        ],
    },
    'psy_adulte': {
        'titre': "Bilan psychologique",
        'description': "Adulte : symptomatologie anxieuse et dépressive (Beck, STAI).",
        'icone': 'fa-user',
        'tests_suggeres': ['beck', 'stai'],
        'sections': [
            {'cle': 'identite', 'titre': "Identité", 'type': 'auto', 'generateur': 'identite'},
            {'cle': 'motif', 'titre': "Motif de consultation", 'type': 'ia',
             'consigne': "Reformule le motif de consultation et les attentes du patient, en 1 paragraphe."},
            {'cle': 'contexte', 'titre': "Histoire et contexte de vie", 'type': 'ia',
             'consigne': "Résume le contexte de vie (situation familiale, professionnelle, antécédents, "
                         "hygiène de vie : sommeil, alimentation, substances), en 1 à 2 paragraphes."},
            {'cle': 'tests_administres', 'titre': "Outils d'évaluation", 'type': 'auto',
             'generateur': 'tests_administres'},
            {'cle': 'resultats', 'titre': "Résultats", 'type': 'auto', 'generateur': 'resultats'},
            {'cle': 'analyse', 'titre': "Analyse des résultats", 'type': 'ia',
             'consigne': "Commente les scores Beck et STAI (niveau, signification clinique) en t'appuyant "
                         "uniquement sur les données. Si une alerte (idées suicidaires) est signalée, "
                         "mentionne-la explicitement comme point à évaluer en priorité."},
            {'cle': 'observations', 'titre': "Observations cliniques", 'type': 'libre',
             'aide': "Présentation, discours, affect, alliance thérapeutique..."},
            {'cle': 'synthese', 'titre': "Synthèse", 'type': 'ia',
             'consigne': "Synthèse clinique en 1 à 2 paragraphes, hypothèses prudentes, sans diagnostic définitif."},
            {'cle': 'recommandations', 'titre': "Orientation et recommandations", 'type': 'ia',
             'consigne': "Liste de 3 à 5 recommandations (type et rythme de suivi, orientations éventuelles "
                         "vers un médecin/psychiatre, pistes de travail), sous forme de liste « - »."},
            {'cle': 'signature', 'titre': "Signature", 'type': 'auto', 'generateur': 'signature'},
        ],
    },
    'compte_rendu_suivi': {
        'titre': "Compte rendu de suivi",
        'description': "Point d'étape d'une prise en charge, à partir des notes de séance.",
        'icone': 'fa-notes-medical',
        'tests_suggeres': [],
        'sections': [
            {'cle': 'identite', 'titre': "Identité", 'type': 'auto', 'generateur': 'identite'},
            {'cle': 'periode', 'titre': "Période de suivi", 'type': 'auto', 'generateur': 'periode_suivi'},
            {'cle': 'evolution', 'titre': "Évolution", 'type': 'ia',
             'consigne': "Décris l'évolution du patient au fil des séances (thèmes travaillés, progrès, "
                         "difficultés persistantes) à partir des notes de séance, en 2 à 3 paragraphes."},
            {'cle': 'perspectives', 'titre': "Perspectives", 'type': 'libre',
             'aide': "Suite envisagée, objectifs des prochaines séances..."},
            {'cle': 'signature', 'titre': "Signature", 'type': 'auto', 'generateur': 'signature'},
        ],
    },
}

MODELE_CHOICES = [(cle, modele['titre']) for cle, modele in MODELES.items()]


def sections_ia(cle_modele):
    return [s for s in MODELES[cle_modele]['sections'] if s['type'] == 'ia']
