"""Données d'un patient pour un bilan : tests disponibles, sections remplies automatiquement
(tableaux de résultats calculés par le scoring existant de chaque test) et contexte texte
pour l'IA. Les scores viennent toujours du code, jamais de l'IA."""
import logging
from datetime import date

from django.utils import timezone

from . import html_blocs as hb
from . import tests_externes as te
from .modeles import (MODELES, PLACEHOLDER_IA, PLACEHOLDER_LIBRE, SECTIONS_FINALES, TITRE_INTERPRETATION,
                      section_du_modele)

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
DOMAINES_PLATEFORME = {'vineland': 'adaptatif', 'brief': 'executif', 'd2r': 'attention', 'beck': 'emotionnel',
                       'stai': 'emotionnel'}
PRESENTATIONS_TESTS_PLATEFORME = {
    'vineland': "Entretien semi-structuré avec un proche évaluant le comportement adaptatif dans la vie "
                "quotidienne : communication, autonomie, socialisation et motricité.",
    'brief': "Questionnaire rempli par les parents décrivant les fonctions exécutives dans la vie quotidienne : "
             "régulation comportementale (inhibition, flexibilité, contrôle émotionnel) et métacognition "
             "(initiation, mémoire de travail, planification, organisation, contrôle).",
    'd2r': "Épreuve de barrage explorant l'attention sélective et la concentration : rythme de traitement, "
           "précision et capacité de concentration, dans une tâche visuelle monotone sous contrainte de temps.",
    'beck': "Autoquestionnaire de 21 items mesurant l'intensité des symptômes dépressifs.",
    'stai': "Autoquestionnaire distinguant l'anxiété ressentie au moment présent (anxiété-état) et la tendance "
            "anxieuse habituelle (anxiété-trait).",
}


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


# --- informations du bilan (page de garde) -----------------------------------------------------

CHAMPS_INFOS = [
    ('date_evaluation', "Date d'évaluation", 'date'),
    ('lateralite', "Latéralité", 'texte'),
    ('langues', "Langue(s) maternelle(s)", 'texte'),
    ('etablissement', "Établissement scolaire", 'texte'),
    ('classe', "Classe (ou profession)", 'texte'),
    ('situation_familiale', "Situation familiale", 'texte'),
    ('adresse_par', "Adressé(e) par", 'texte'),
    ('seances', "Déroulement de l'évaluation", 'texte'),
    ('civilite', "Civilité utilisée dans le texte", 'choix'),
    ('bilan_anterieur', "Bilan ou diagnostic antérieur", 'texte_long'),
    ('sous_titre', "Sous-titre du bilan", 'texte'),
]
CIVILITES = ['', 'Mme', 'M.']
LIBELLES_INFOS = {cle: libelle for cle, libelle, _ in CHAMPS_INFOS}
# Noms propres de l'entourage : masqués avant tout envoi à l'IA (voir Pseudonymiseur.pour_bilan)
INFOS_A_MASQUER = ('etablissement', 'adresse_par')


def lire_infos(post, modele):
    infos = {}
    for cle, _, type_champ in CHAMPS_INFOS:
        valeur = (post.get(f'info_{cle}') or '').strip()
        if type_champ == 'choix' and valeur not in CIVILITES:
            valeur = ''
        if type_champ == 'date':
            valeur = valeur if _parse_date(valeur) else ''
        valeur = valeur[:1500 if type_champ == 'texte_long' else 200]
        if valeur or (cle == 'sous_titre' and post.get('info_sous_titre') is not None):
            infos[cle] = valeur  # sous-titre vidé volontairement : on garde la chaîne vide
    if 'sous_titre' not in infos and post.get('info_sous_titre') is None and modele.get('sous_titre'):
        infos['sous_titre'] = modele['sous_titre']
    return infos


def _parse_date(texte):
    try:
        return date.fromisoformat(texte)
    except (TypeError, ValueError):
        return None


def date_evaluation(bilan):
    return _parse_date((bilan.infos or {}).get('date_evaluation')) or timezone.localdate()


# --- tests inclus (plateforme + saisis) ----------------------------------------------------------

ORDRE_DOMAINES = ['intellectuel', 'attention', 'executif', 'neuropsy', 'adaptatif', 'graphomoteur',
                  'questionnaire', 'emotionnel', 'autre']


def tests_inclus(bilan, user=None):
    """Tests du bilan, dans l'ordre de présentation (domaine puis ordre du catalogue) :
    [{'section', 'origine', 'cle', 'test'|'saisie', 'titre', 'nom', 'domaine'}]."""
    items = []
    for cle, test in charger_tests(bilan, user):
        items.append({'section': f'test_{cle}_{test.id}', 'origine': 'plateforme', 'cle': cle, 'test': test,
                      'titre': NOMS_LONGS_TESTS[cle], 'nom': NOMS_TESTS[cle],
                      'domaine': DOMAINES_PLATEFORME.get(cle, 'autre')})
    for cle, saisie in (bilan.scores or {}).items():
        if cle in te.TESTS:
            items.append({'section': f'ext_{cle}', 'origine': 'externe', 'cle': cle, 'saisie': saisie or {},
                          'titre': te.nom_affiche(cle, saisie), 'nom': te.nom_court(cle, saisie),
                          'domaine': te.TESTS[cle]['domaine']})
    ordre_catalogue = list(te.TESTS) + [c for c, _, _ in TYPES_TESTS]
    items.sort(key=lambda i: (ORDRE_DOMAINES.index(i['domaine']) if i['domaine'] in ORDRE_DOMAINES else 99,
                              ordre_catalogue.index(i['cle'])))
    return items


def resultats_item(item):
    """Résultats normalisés d'un test inclus : tableaux, remarques, figures, synthèse, valeurs."""
    if item['origine'] == 'externe':
        return te.resultats(item['cle'], item['saisie'])
    res = resultats_test(item['cle'], item['test'])
    res['remarques'] = [f"Passation du {_date(item['test'].date_passation)}."] + res['remarques']
    res.update(figures=[], synthese=_synthese_plateforme(item['cle'], res), valeurs=_valeurs_plateforme(item['cle'], res),
               niveaux=[])
    if item['cle'] == 'beck':
        res['niveaux'] = [{'noms': ['BDI', 'Beck'], 'niveau': item['test'].get_niveau_depression_display()}]
    return res


def _synthese_plateforme(cle, res):
    if not res['tableaux']:
        return []
    lignes = res['tableaux'][0][2]
    nom = NOMS_TESTS[cle]
    synthese = []
    for ligne in lignes:
        if cle == 'brief':
            libelle, _, t, pct, _, zone_txt = ligne
            if zone_txt.startswith('Significatif') or 'Indice' in libelle or 'Composite' in libelle:
                synthese.append([f"BRIEF - {libelle}", f"T{t}" + (f" - P{pct}" if pct != '-' else ''), zone_txt])
        elif cle == 'd2r':
            libelle, _, ns, pct = ligne
            synthese.append([f"d2-R - {libelle}", f"{ns} - P{pct}" if pct != '-' else str(ns), te.zone(ns, te.ZONES_D2R) or '-'])
        elif cle == 'vineland':
            libelle, ns, pct, _, niveau = ligne
            synthese.append([f"Vineland - {libelle}", f"{ns} - P{pct}" if pct != '-' else str(ns), niveau])
        else:
            synthese.append([f"{nom} - {ligne[0]}", ligne[1], ligne[2]])
    return synthese


def _valeurs_plateforme(cle, res):
    if not res['tableaux']:
        return []
    valeurs = []
    for ligne in res['tableaux'][0][2]:
        if cle == 'brief' and te.nombre(ligne[2]) is not None:
            valeurs.append({'noms': [ligne[0].split(' (')[0]], 'valeur': te.nombre(ligne[2]),
                            'percentile': te.nombre(ligne[3]), 'type': 'T'})
        elif cle == 'd2r' and ligne[0].startswith(('Rythme', 'Capacité')) and te.nombre(ligne[2]) is not None:
            valeurs.append({'noms': ['CCT' if ligne[0].startswith('Rythme') else 'CC'], 'valeur': te.nombre(ligne[2]),
                            'percentile': te.nombre(ligne[3])})
    return valeurs


def blocs_resultats(item):
    """Partie calculée d'un chapitre de test : tableaux, graphiques, remarques."""
    res = resultats_item(item)
    blocs = []
    plusieurs = len(res['tableaux']) > 1
    figures = list(res['figures'])
    for titre_tableau, entetes, lignes in res['tableaux']:
        if titre_tableau and plusieurs:
            blocs.append(hb.paragraphe(titre_tableau, b=True))
        blocs.append(hb.tableau(entetes, lignes))
        # Graphique de profil juste après le tableau qu'il illustre
        if titre_tableau in ('Comparaisons entre les indices', 'Indices') and f"{item['cle']}.indices" in figures:
            if titre_tableau == 'Comparaisons entre les indices' or not any(t[0] == 'Comparaisons entre les indices'
                                                                            for t in res['tableaux']):
                blocs.append(hb.figure(f"{item['cle']}.indices"))
                figures.remove(f"{item['cle']}.indices")
        if titre_tableau == 'Subtests' and f"{item['cle']}.subtests" in figures:
            blocs.append(hb.figure(f"{item['cle']}.subtests"))
            figures.remove(f"{item['cle']}.subtests")
    blocs.extend(hb.figure(ref) for ref in figures)
    blocs.extend(hb.paragraphe(r, i=True) for r in res['remarques'])
    return blocs


def blocs_section_test(item):
    return [hb.titre(2, item['titre'], section=item['section'], section_type='test')] + blocs_resultats(item) + [
        hb.titre(3, TITRE_INTERPRETATION), hb.paragraphe(PLACEHOLDER_IA, i=True)]


def _est_titre_interpretation(bloc):
    return bloc['type'] == 'h3' and hb.texte_runs(bloc['runs']).strip().rstrip(' :').lower() == TITRE_INTERPRETATION.lower()


def decouper_interpretation(corps):
    """Corps d'un chapitre de test -> (partie calculée, [titre Interprétation + texte]) ."""
    for n, bloc in enumerate(corps):
        if _est_titre_interpretation(bloc):
            return corps[:n], corps[n:]
    return corps, []


# --- sections automatiques ---------------------------------------------------------------------

def _psychologue(bilan):
    return bilan.psychologue if bilan.psychologue and not bilan.psychologue.is_superadmin() else \
        bilan.organization.users.filter(role='psychologist').order_by('id').first()


def en_tete_de(bilan):
    from .models import EnTeteBilan
    psy = _psychologue(bilan)
    return EnTeteBilan.objects.filter(utilisateur=psy).first() if psy else None


def _ligne_identite(libelle, valeur, gras=False):
    return {'header': False, 'cells': [[hb.run(libelle, i=True)], [hb.run(valeur, b=gras)]]}


def generer_section_auto(generateur, bilan, items):
    patient = bilan.patient
    infos = bilan.infos or {}
    modele = MODELES.get(bilan.modele, {})
    if generateur == 'identite':
        quand = date_evaluation(bilan)
        lignes = [_ligne_identite("Nom et prénom", f"{patient.nom.upper()} {patient.prenom}", gras=True),
                  _ligne_identite("Date de naissance", _date(patient.date_naissance)),
                  _ligne_identite("Âge", texte_age(patient.date_naissance, quand)),
                  _ligne_identite("Date d'évaluation", _date(quand))]
        for cle in ('lateralite', 'langues', 'etablissement', 'classe', 'situation_familiale', 'adresse_par', 'seances'):
            if infos.get(cle):
                libelle = LIBELLES_INFOS[cle]
                if cle == 'classe':
                    libelle = "Profession" if modele.get('public') == 'adulte' else "Classe"
                lignes.append(_ligne_identite(libelle, infos[cle]))
        psy = _psychologue(bilan)
        en_tete = en_tete_de(bilan)
        if psy:
            lignes.append(_ligne_identite("Psychologue", (en_tete.nom_affiche if en_tete and en_tete.nom_affiche
                                                          else psy.get_full_name() or psy.username)))
        blocs = [{'type': 'table', 'rows': lignes}]
        if modele.get('public') == 'enfant':
            from .textes_types import _MENTIONS
            blocs.append(hb.paragraphe(dict((c, t) for c, _, t in _MENTIONS)['men_non_figes'], i=True))
        return blocs

    if generateur == 'tests_utilises':
        if not items:
            return [hb.paragraphe("Aucun test inclus pour le moment : ajoutez-les dans « Scores et informations ».", i=True)]
        entrees = []
        for item in items:
            description = (PRESENTATIONS_TESTS_PLATEFORME.get(item['cle'], '') if item['origine'] == 'plateforme'
                           else te.presentation(item['cle'], item['saisie']))
            runs = [hb.run(item['nom'], b=True)]
            if description:
                runs.append(hb.run(f" : {description}"))
            entrees.append(runs)
        return [hb.liste(entrees)]

    if generateur == 'etapes':
        domaines = {}
        for item in items:
            domaines.setdefault(item['domaine'], []).append(item['nom'])
        etapes = ["Entretien clinique initial, visant à préciser la demande et le contexte de consultation.",
                  "Recueil de l'anamnèse : histoire développementale, scolaire et professionnelle, difficultés "
                  "actuellement rapportées."]
        if domaines.get('intellectuel'):
            etapes.append(f"Évaluation du fonctionnement intellectuel ({', '.join(domaines['intellectuel'])}).")
        attention = domaines.get('attention', []) + domaines.get('executif', [])
        if attention:
            etapes.append(f"Évaluation de l'attention et des fonctions exécutives ({', '.join(attention)}).")
        questionnaires = domaines.get('questionnaire', []) + domaines.get('emotionnel', [])
        if questionnaires:
            etapes.append(f"Questionnaires et entretiens standardisés ({', '.join(questionnaires)}).")
        etapes.append("Entretien de restitution des résultats.")
        return [hb.liste(etapes)]

    if generateur == 'synthese_resultats':
        lignes = []
        for item in items:
            lignes.extend(resultats_item(item)['synthese'])
        if not lignes:
            return [hb.paragraphe("Le tableau de synthèse se remplit à partir des scores des tests.", i=True)]
        return [hb.tableau(["Domaine / épreuve", "Résultat principal", "Lecture clinique"], lignes)]

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
        en_tete = en_tete_de(bilan)
        ville = bilan.organization.city or '...'
        blocs = [hb.paragraphe(f"Fait à {ville}, le {_date(timezone.localdate())}.")]
        formule = en_tete.formule_signature if en_tete else "Pour faire valoir ce que de droit."
        if formule:
            blocs.append(hb.paragraphe(formule))
        if psy:
            nom = (en_tete.nom_affiche if en_tete and en_tete.nom_affiche else psy.get_full_name() or psy.username)
            titre = en_tete.titre_pro if en_tete and en_tete.titre_pro else "Psychologue"
            blocs.append(hb.paragraphe(nom, b=True))
            blocs.append(hb.paragraphe(titre + (f" - N° {psy.license_number}" if psy.license_number else "")))
        if en_tete and en_tete.signature:
            blocs.append(hb.figure('signature'))
        return blocs

    return []


def _blocs_section(section, bilan, items):
    if section['type'] == 'tests':
        blocs = []
        for item in items:
            blocs.extend(blocs_section_test(item))
        return blocs
    blocs = [hb.titre(2, section['titre'], section=section['cle'], section_type=section['type'])]
    if section['type'] == 'auto':
        blocs.extend(generer_section_auto(section['generateur'], bilan, items))
    elif section['type'] == 'ia':
        blocs.append(hb.paragraphe(PLACEHOLDER_IA, i=True))
    else:
        aide = f" ({section['aide']})" if section.get('aide') else ''
        blocs.append(hb.paragraphe(PLACEHOLDER_LIBRE + aide, i=True))
    return blocs


def construire_contenu(bilan, user=None):
    """Document initial d'un bilan (HTML nettoyé) à partir de son modèle et de ses sources."""
    modele = MODELES[bilan.modele]
    items = tests_inclus(bilan, user)
    blocs = [hb.titre(1, bilan.titre)]
    sous_titre = (bilan.infos or {}).get('sous_titre', modele.get('sous_titre', ''))
    if sous_titre:
        blocs.append(hb.paragraphe(sous_titre))
    for section in modele['sections']:
        blocs.extend(_blocs_section(section, bilan, items))
    return hb.ecrire(blocs)


def rafraichir_contenu(bilan, user=None):
    """Après une modification des scores ou des informations : régénère les sections « Données »
    et la partie calculée de chaque chapitre de test (tableaux, graphiques), ajoute les chapitres
    des tests ajoutés et retire ceux des tests retirés. Les textes rédigés (interprétations,
    sections IA ou libres) sont conservés."""
    items = tests_inclus(bilan, user)
    par_section = {item['section']: item for item in items}
    preambule, sections = hb.decouper_sections(hb.lire(bilan.contenu))

    autres, chapitres, position = [], {}, None
    for titre_bloc, corps in sections:
        cle, type_section = titre_bloc['section'], titre_bloc.get('section_type')
        if type_section == 'test':
            if position is None:
                position = len(autres)
            if cle in par_section:
                calcule, interpretation = decouper_interpretation(corps)
                if not interpretation:  # titre « Interprétation » supprimé : on garde le texte rédigé
                    interpretation = [hb.titre(3, TITRE_INTERPRETATION)] + [
                        b for b in calcule if b['type'] not in ('table', 'figure')]
                titre_bloc = dict(titre_bloc, runs=[hb.run(par_section[cle]['titre'])])
                chapitres[cle] = (titre_bloc, blocs_resultats(par_section[cle]) + interpretation)
            continue
        if type_section == 'auto':
            section = section_du_modele(bilan.modele, cle)
            if section and section.get('generateur'):
                corps = generer_section_auto(section['generateur'], bilan, items)
        autres.append((titre_bloc, corps))

    if position is None:  # aucun chapitre de test jusque-là : après « Tests utilisés », sinon avant la fin
        cles = [t['section'] for t, _ in autres]
        if 'tests_utilises' in cles:
            position = cles.index('tests_utilises') + 1
        else:
            finales = [n for n, c in enumerate(cles) if c in SECTIONS_FINALES | {'synthese_resultats', 'signature'}]
            position = finales[0] if finales else len(autres)
    ordonnes = []
    for item in items:
        if item['section'] in chapitres:
            ordonnes.append(chapitres[item['section']])
        else:
            nouveaux = blocs_section_test(item)
            ordonnes.append((nouveaux[0], nouveaux[1:]))
    return hb.ecrire(hb.assembler_sections(preambule, autres[:position] + ordonnes + autres[position:]))


# --- contexte pour l'IA (texte NON anonymisé : passer ensuite par Pseudonymiseur) -----------

LIMITE_CHAMP = 1500
LIMITE_NOTE = 600
NB_SEANCES_MAX = 12
LIMITE_BILAN_PRECEDENT = 3000

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


def _texte_resultats(item):
    res = resultats_item(item)
    lignes = [item['titre']]
    if item['origine'] == 'externe' and item['cle'].startswith('autre') and te.presentation(item['cle'], item['saisie']):
        lignes.append(f"Présentation : {te.presentation(item['cle'], item['saisie'])}")
    for titre_tableau, entetes, rows in res['tableaux']:
        if titre_tableau:
            lignes.append(titre_tableau)
        lignes.append('| ' + ' | '.join(entetes) + ' |')
        lignes.extend('| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows)
    lignes.extend(f"Remarque : {r}" for r in res['remarques'])
    return '\n'.join(lignes)


def contexte_patient(bilan, user=None, nb_seances_max=NB_SEANCES_MAX):
    """Texte des données du patient (identité, âge, informations du bilan, anamnèse, séances,
    résultats) - jamais le téléphone ni l'email."""
    from cabinet.models import Anamnese
    from .models import Bilan
    patient = bilan.patient
    sources = bilan.sources or {}
    infos = bilan.infos or {}
    modele = MODELES.get(bilan.modele, {})
    quand = date_evaluation(bilan)
    parties = [
        f"Patient : {patient.prenom} {patient.nom}, né(e) le {_date(patient.date_naissance)}, "
        f"{texte_age(patient.date_naissance, quand)} à la date d'évaluation ({_date(quand)})."
    ]
    public = {'enfant': "enfant ou adolescent", 'adulte': "adulte"}.get(modele.get('public'))
    lignes_infos = [f"- Type de bilan : {modele.get('nom', bilan.titre)}" + (f" ({public})" if public else '')]
    for cle, libelle, _ in CHAMPS_INFOS:
        if cle in ('date_evaluation', 'sous_titre', 'civilite') or not infos.get(cle):
            continue
        lignes_infos.append(f"- {libelle} : {_tronquer(infos[cle], LIMITE_CHAMP)}")
    if infos.get('civilite'):
        lignes_infos.append(f"- Désigner le patient par : {infos['civilite']} [NOM]")
    parties.append("INFORMATIONS DU BILAN\n" + '\n'.join(lignes_infos))

    if sources.get('bilan_precedent'):
        precedent = Bilan.all_objects.filter(id=sources['bilan_precedent'], organization=bilan.organization,
                                             patient=patient).first()
        if precedent:
            _, sections_prec = hb.decouper_sections(hb.lire(precedent.contenu))
            conclusion = [corps for titre_bloc, corps in sections_prec
                          if titre_bloc['section'] in ('conclusion', 'synthese')]
            texte = hb.en_texte(conclusion[0]) if conclusion else hb.en_texte(hb.lire(precedent.contenu))
            parties.append(f"BILAN PRÉCÉDENT ({precedent.titre}, {_date(precedent.date_creation)}) - conclusion\n"
                           + _tronquer(texte, LIMITE_BILAN_PRECEDENT))

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
                       .order_by('-date_seance')[:nb_seances_max])
        blocs_seances = []
        for seance in reversed(seances):
            notes = [f"  {libelle} : {_tronquer(getattr(seance, champ), LIMITE_NOTE)}"
                     for champ, libelle in CHAMPS_SEANCE if (getattr(seance, champ) or '').strip()]
            if notes:
                blocs_seances.append(f"- Séance du {_date(seance.date_seance)} :\n" + '\n'.join(notes))
        if blocs_seances:
            parties.append(f"NOTES DE SÉANCE ET OBSERVATIONS ({len(blocs_seances)} dernières séances terminées)\n"
                           + '\n'.join(blocs_seances))

    items = tests_inclus(bilan, user)
    if items:
        parties.append("RÉSULTATS DES TESTS (saisis ou calculés par la plateforme, à ne pas modifier)\n"
                       + '\n\n'.join(_texte_resultats(item) for item in items))

    return '\n\n'.join(parties)


def valeurs_de_reference(bilan, user=None):
    """Scores connus du bilan, pour la vérification de cohérence du texte."""
    valeurs, niveaux, noms_tests = [], [], []
    for item in tests_inclus(bilan, user):
        res = resultats_item(item)
        valeurs.extend(dict(v, test=item['nom']) for v in res['valeurs'])
        niveaux.extend(dict(n, test=item['nom']) for n in res['niveaux'])
        noms_tests.append(item['cle'])
    return {'valeurs': valeurs, 'niveaux': niveaux, 'tests': noms_tests}
