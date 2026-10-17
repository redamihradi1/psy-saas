"""Données d'un patient pour un bilan : tests disponibles, sections remplies automatiquement
(tableaux de résultats calculés par le scoring existant de chaque test) et contexte texte
pour l'IA. Les scores viennent toujours du code, jamais de l'IA."""
import logging
from datetime import date

from django.utils import timezone

from . import html_blocs as hb
from .modeles import MODELES, PLACEHOLDER_IA, PLACEHOLDER_LIBRE

logger = logging.getLogger(__name__)

TYPES_TESTS = [
    ('vineland', 'Vineland-II', "Vineland-II (comportement adaptatif)"),
    ('brief', 'BRIEF', "BRIEF - Forme Parent (fonctions exécutives)"),
    ('d2r', 'D2R', "d2-R (attention et concentration)"),
    ('beck', 'Beck', "Inventaire de dépression de Beck (BDI)"),
    ('stai', 'STAI', "STAI - Inventaire d'anxiété état-trait"),
]
NOMS_TESTS = {cle: nom for cle, nom, _ in TYPES_TESTS}
NOMS_LONGS_TESTS = {cle: nom_long for cle, _, nom_long in TYPES_TESTS}


def _modeles_tests():
    from tests_psy.models import TestVineland, TestBeck, TestSTAI, TestD2R, TestBRIEF
    return {'vineland': TestVineland, 'brief': TestBRIEF, 'd2r': TestD2R, 'beck': TestBeck, 'stai': TestSTAI}


def tests_autorises(user, organization):
    """Types de tests que cet utilisateur peut citer dans un bilan (licence du cabinet ET
    permission utilisateur, comme l'onglet Tests de la fiche patient)."""
    license = getattr(organization, 'license', None)
    return [
        cle for cle, _, _ in TYPES_TESTS
        if license and getattr(license, f'has_{cle}', False) and user.has_test_permission(cle)
    ]


def tests_disponibles(user, patient):
    """Tests passés par le patient, exploitables dans un bilan : [{'ref', 'type', 'nom', 'date'}]."""
    modeles = _modeles_tests()
    disponibles = []
    for cle in tests_autorises(user, patient.organization):
        queryset = modeles[cle].all_objects.filter(organization=patient.organization, patient=patient)
        for test in queryset.order_by('-date_passation'):
            if getattr(test, 'mode', '') == 'lien_public' and not test.lien_soumis_le:
                continue  # parent pas encore répondu : rien à exploiter
            disponibles.append({
                'ref': f'{cle}:{test.id}',
                'type': cle,
                'nom': NOMS_TESTS[cle],
                'date': test.date_passation,
            })
    return disponibles


def charger_tests(bilan, user=None):
    """Tests sélectionnés dans bilan.sources, encore existants et autorisés : [(type, test)]."""
    modeles = _modeles_tests()
    autorises = set(tests_autorises(user, bilan.organization)) if user else set(modeles)
    tests = []
    for ref in bilan.sources.get('tests', []):
        cle, _, test_id = ref.partition(':')
        if cle not in modeles or cle not in autorises or not test_id.isdigit():
            continue
        test = modeles[cle].all_objects.filter(
            id=int(test_id), organization=bilan.organization, patient=bilan.patient,
        ).first()
        if test:
            tests.append((cle, test))
    return tests


# --- âge ------------------------------------------------------------------------------------

def age_detaille(date_naissance, reference=None):
    reference = reference or timezone.localdate()
    mois = (reference.year - date_naissance.year) * 12 + reference.month - date_naissance.month
    if reference.day < date_naissance.day:
        mois -= 1
    return mois // 12, mois % 12


def texte_age(date_naissance, reference=None):
    ans, mois = age_detaille(date_naissance, reference)
    texte = f"{ans} an{'s' if ans > 1 else ''}"
    if mois:
        texte += f" et {mois} mois"
    return texte


def _date(d):
    if d is None:
        return '-'
    if hasattr(d, 'date') and not isinstance(d, date):
        d = timezone.localtime(d).date() if timezone.is_aware(d) else d.date()
    return d.strftime('%d/%m/%Y')


def _val(v, suffixe=''):
    return '-' if v is None or v == '' else f'{v}{suffixe}'


# --- résultats par test (structurés : tableaux + remarques) --------------------------------

def resultats_test(cle, test):
    """-> {'titre', 'tableaux': [(titre|None, entetes, lignes)], 'remarques': [str]}.
    Ne lève jamais : un test incomplet donne une remarque plutôt qu'un plantage du bilan."""
    titre = f"{NOMS_LONGS_TESTS[cle]} - passé le {_date(test.date_passation)}"
    try:
        contenu = RESULTATS[cle](test)
    except Exception:  # données incomplètes, normes absentes...
        logger.exception("Résultats indisponibles pour %s %s", cle, test.pk)
        contenu = {'tableaux': [], 'remarques': ["Résultats indisponibles (test incomplet ou normes manquantes)."]}
    return {'titre': titre, **contenu}


def _resultats_vineland(test):
    from tests_psy.views.vineland.scoring import (
        calculate_all_scores, calculate_domain_scores, get_age_tranches, get_patient_age,
    )
    age_info = get_patient_age(test)
    tranche_age, tranche_intervalle = get_age_tranches(age_info['years'])
    domaines = calculate_domain_scores(
        calculate_all_scores(test), age_info, tranche_age, tranche_intervalle, test, niveau_confiance=90,
    )
    lignes_domaines, lignes_sous = [], []
    for domaine in domaines:
        score = domaine['domain_score'] or {}
        lignes_domaines.append([
            domaine['name'], _val(score.get('note_standard')), _val(score.get('rang_percentile')),
            f"±{score['intervalle']}" if score.get('intervalle') else '-', _val(score.get('niveau_adaptatif')),
        ])
        for sd in domaine['sous_domaines']:
            lignes_sous.append([
                sd['name'], _val(sd['note_brute']), _val(sd['note_echelle_v']),
                _val(sd.get('niveau_adaptatif')), _val(sd.get('age_equivalent')),
            ])
    tableaux = [
        ("Domaines", ["Domaine", "Note standard", "Rang percentile", "IC 90 %", "Niveau adaptatif"], lignes_domaines),
        ("Sous-domaines", ["Sous-domaine", "Note brute", "Note échelle-V", "Niveau adaptatif", "Âge équivalent"],
         lignes_sous),
    ]
    remarques = []
    if test.mode == 'importe':
        remarques.append("Notes brutes saisies à partir d'une cotation papier.")
    return {'tableaux': tableaux, 'remarques': remarques}


def _resultats_brief(test):
    from tests_psy.views.brief.scoring import calculer_resultats
    r = calculer_resultats(test)
    lignes = []
    for ligne in r['lignes']:
        ic = f"{ligne['ic_bas']}-{ligne['ic_haut']}" if ligne['ic_bas'] is not None else '-'
        zone = 'Significatif (T de 65 ou plus)' if ligne['significatif'] else ('Dans la norme' if ligne['score_t'] is not None else '-')
        lignes.append([ligne['libelle'], _val(ligne['note_brute']), _val(ligne['score_t']),
                       _val(ligne['percentile']), ic, zone])
    repondant = f"répondant : {test.repondant} ; " if test.repondant else ''
    remarques = [f"Questionnaire parent ({repondant}enfant : {test.get_sexe_display().lower()}, {r['age']} ans)."]
    if not r['protocole_cotable']:
        remarques.append("Protocole non cotable : trop de réponses manquantes.")
    elif r['hors_etalonnage']:
        remarques.append("Âge hors étalonnage (5-18 ans) : scores T non disponibles.")
    elif not r['normes_disponibles']:
        remarques.append("Normes non chargées : scores T en attente.")
    neg = r['negativite']
    if neg['score'] is not None:
        remarques.append(f"Échelle de validité Négativité : {neg['score']} ({neg['classification']}).")
    inc = r['incoherence']
    if inc['score'] is not None:
        classement = f" ({inc['classification']})" if inc['classification'] else " (seuils de l'adaptation française non disponibles)"
        remarques.append(f"Échelle de validité Incohérence : {inc['score']}{classement}.")
    if r['alerte_ecart_irc_im']:
        remarques.append(f"Écart IRC-IM de {r['ecart_irc_im']} points T (seuil : {r['seuil_ecart_irc_im']}) : "
                         "le CEG doit être interprété avec prudence.")
    entetes = ["Échelle / indice", "Note brute", "Score T", "Percentile", "IC 90 %", "Interprétation"]
    return {'tableaux': [(None, entetes, lignes)], 'remarques': remarques}


def _resultats_d2r(test):
    from tests_psy.views.d2r import calculer_scores_d2r
    s = calculer_scores_d2r(test)
    lignes = [
        ["Rythme de traitement (CCT)", s['cct'], _val(s['note_standard_cct']), _val(s['percentile_cct'])],
        ["Exactitude (E %)", f"{s['e_percentage']} %", _val(s['note_standard_e']), _val(s['percentile_e'])],
        ["Capacité de concentration (CC)", s['cc'], _val(s['note_standard_cc']), _val(s['percentile_cc'])],
    ]
    remarques = [f"Erreurs d'omission : {s['eo']} ; erreurs de commission : {s['ec']} ; "
                 f"âge à la passation : {test.age} ans."]
    return {'tableaux': [(None, ["Indicateur", "Valeur", "Note standard", "Percentile"], lignes)],
            'remarques': remarques}


def _resultats_beck(test):
    lignes = [["Score total", f"{test.score_total} / 63", test.get_niveau_depression_display()]]
    remarques = []
    if test.alerte_suicide:
        remarques.append("ALERTE : item 9 (idées suicidaires) coté 2 ou plus - à évaluer en priorité.")
    return {'tableaux': [(None, ["Mesure", "Score", "Niveau"], lignes)], 'remarques': remarques}


def _resultats_stai(test):
    lignes = [
        ["Anxiété-état (items 1-20)", f"{test.score_etat} / 80", test.niveau_etat_display],
        ["Anxiété-trait (items 21-40)", f"{test.score_trait} / 80", test.niveau_trait_display],
    ]
    return {'tableaux': [(None, ["Échelle", "Score", "Niveau"], lignes)], 'remarques': []}


RESULTATS = {
    'vineland': _resultats_vineland,
    'brief': _resultats_brief,
    'd2r': _resultats_d2r,
    'beck': _resultats_beck,
    'stai': _resultats_stai,
}


# --- sections automatiques -------------------------------------------------------------------

def _psychologue(bilan):
    return bilan.psychologue if bilan.psychologue and not bilan.psychologue.is_superadmin() else \
        bilan.organization.users.filter(role='psychologist').order_by('id').first()


def generer_section_auto(generateur, bilan, tests):
    patient = bilan.patient
    if generateur == 'identite':
        lignes = [
            ["Nom et prénom", patient.nom_complet],
            ["Date de naissance", _date(patient.date_naissance)],
            ["Âge à la date du bilan", texte_age(patient.date_naissance)],
            ["Date du bilan", _date(timezone.localdate())],
        ]
        psy = _psychologue(bilan)
        if psy:
            lignes.append(["Psychologue", psy.get_full_name() or psy.username])
        rows = [{'header': False, 'cells': [[hb.run(a, b=True)], [hb.run(b)]]} for a, b in lignes]
        return [{'type': 'table', 'rows': rows}]

    if generateur == 'tests_administres':
        if not tests:
            return [hb.paragraphe("Aucun test psychométrique inclus dans ce bilan.", i=True)]
        return [hb.liste([f"{NOMS_LONGS_TESTS[cle]}, le {_date(test.date_passation)}" for cle, test in tests])]

    if generateur == 'resultats':
        if not tests:
            return [hb.paragraphe("Aucun résultat de test à présenter.", i=True)]
        blocs = []
        for cle, test in tests:
            res = resultats_test(cle, test)
            blocs.append(hb.titre(3, res['titre']))
            for titre_tableau, entetes, lignes in res['tableaux']:
                if titre_tableau:
                    blocs.append(hb.paragraphe(titre_tableau, b=True))
                blocs.append(hb.tableau(entetes, lignes))
            for remarque in res['remarques']:
                blocs.append(hb.paragraphe(remarque, i=True))
        return blocs

    if generateur == 'periode_suivi':
        seances = patient.consultation_set.filter(statut_consultation='termine').order_by('date_seance')
        if not seances.exists():
            return [hb.paragraphe("Aucune séance terminée enregistrée pour ce patient.", i=True)]
        premiere, derniere = seances.first(), seances.last()
        return [hb.paragraphe(
            f"Suivi du {_date(premiere.date_seance)} au {_date(derniere.date_seance)} : "
            f"{seances.count()} séance(s) réalisée(s)."
        )]

    if generateur == 'signature':
        psy = _psychologue(bilan)
        ville = bilan.organization.city or '...'
        blocs = [hb.paragraphe(f"Fait à {ville}, le {_date(timezone.localdate())}.")]
        if psy:
            blocs.append(hb.paragraphe(psy.get_full_name() or psy.username, b=True))
            blocs.append(hb.paragraphe("Psychologue" + (f" - N° {psy.license_number}" if psy.license_number else "")))
        return blocs

    return []


def construire_contenu(bilan, user=None):
    """Document initial d'un bilan (HTML nettoyé) à partir de son modèle et de ses sources."""
    modele = MODELES[bilan.modele]
    tests = charger_tests(bilan, user)
    blocs = [hb.titre(1, bilan.titre)]
    for section in modele['sections']:
        blocs.append(hb.titre(2, section['titre'], section=section['cle'], section_type=section['type']))
        if section['type'] == 'auto':
            blocs.extend(generer_section_auto(section['generateur'], bilan, tests))
        elif section['type'] == 'ia':
            blocs.append(hb.paragraphe(PLACEHOLDER_IA, i=True))
        else:
            aide = f" ({section['aide']})" if section.get('aide') else ''
            blocs.append(hb.paragraphe(PLACEHOLDER_LIBRE + aide, i=True))
    return hb.ecrire(blocs)


# --- contexte pour l'IA (texte NON anonymisé : passer ensuite par Pseudonymiseur) -----------

LIMITE_CHAMP = 1500
LIMITE_NOTE = 600
NB_SEANCES_MAX = 12

CHAMPS_ANAMNESE = [
    ('motif_consultation', "Motif de consultation"),
    ('antecedents_medicaux', "Antécédents médicaux"),
    ('antecedents_familiaux', "Antécédents familiaux"),
    ('medicaments_actuels', "Médicaments actuels"),
    ('situation_familiale', "Situation familiale"),
    ('situation_professionnelle', "Situation professionnelle / scolaire"),
    ('troubles_sommeil', "Sommeil"),
    ('troubles_alimentaires', "Alimentation"),
    ('activite_physique', "Activité physique"),
    ('hobbies_bien_etre', "Loisirs"),
    ('consommation_substances', "Consommation de substances"),
    ('objectifs_therapie', "Objectifs de la thérapie"),
    ('attentes_patient', "Attentes du patient"),
    ('changements_souhaites', "Changements souhaités"),
]
CHAMPS_SEANCE = [
    ('note_subjectif', "Subjectif"), ('note_objectif', "Objectif"), ('note_evaluation', "Évaluation"),
    ('note_plan', "Plan"), ('objectifs_seance', "Objectifs"), ('suivi_progression', "Progression"),
    ('notes_cliniques', "Notes"),
]


def _tronquer(texte, limite):
    texte = (texte or '').strip()
    return texte if len(texte) <= limite else texte[:limite].rstrip() + ' [...]'


def contexte_patient(bilan, user=None):
    """Texte des données du patient (identité, âge, anamnèse, séances, résultats) - jamais
    le téléphone ni l'email."""
    from cabinet.models import Anamnese
    patient = bilan.patient
    sources = bilan.sources or {}
    parties = [
        f"Patient : {patient.prenom} {patient.nom}, né(e) le {_date(patient.date_naissance)}, "
        f"{texte_age(patient.date_naissance)} ({patient.get_categorie_age_display().lower()})."
    ]

    if sources.get('anamnese'):
        anamnese = Anamnese.all_objects.filter(patient=patient).first()
        if anamnese:
            lignes = [f"- {libelle} : {_tronquer(getattr(anamnese, champ), LIMITE_CHAMP)}"
                      for champ, libelle in CHAMPS_ANAMNESE if (getattr(anamnese, champ) or '').strip()]
            lignes.append(f"- Niveau de stress déclaré : {anamnese.niveau_stress}/10")
            lignes.append(f"- A déjà consulté un psychologue : {'oui' if anamnese.deja_consulte_psy else 'non'}")
            parties.append("ANAMNÈSE\n" + '\n'.join(lignes))

    if sources.get('consultations'):
        seances = list(patient.consultation_set.filter(statut_consultation='termine')
                       .order_by('-date_seance')[:NB_SEANCES_MAX])
        blocs_seances = []
        for seance in reversed(seances):
            notes = [f"  {libelle} : {_tronquer(getattr(seance, champ), LIMITE_NOTE)}"
                     for champ, libelle in CHAMPS_SEANCE if (getattr(seance, champ) or '').strip()]
            if notes:
                blocs_seances.append(f"- Séance du {_date(seance.date_seance)} :\n" + '\n'.join(notes))
        if blocs_seances:
            parties.append(f"NOTES DE SÉANCE ({len(blocs_seances)} dernières séances terminées)\n"
                           + '\n'.join(blocs_seances))

    tests = charger_tests(bilan, user)
    if tests:
        blocs_tests = []
        for cle, test in tests:
            res = resultats_test(cle, test)
            lignes = [res['titre']]
            for titre_tableau, entetes, rows in res['tableaux']:
                if titre_tableau:
                    lignes.append(titre_tableau)
                lignes.append('| ' + ' | '.join(entetes) + ' |')
                lignes.extend('| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows)
            lignes.extend(f"Remarque : {r}" for r in res['remarques'])
            blocs_tests.append('\n'.join(lignes))
        parties.append("RÉSULTATS DES TESTS (calculés par la plateforme, à ne pas modifier)\n"
                       + '\n\n'.join(blocs_tests))

    return '\n\n'.join(parties)
