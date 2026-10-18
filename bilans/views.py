import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import require_test_access
from cabinet.models import Patient

from . import coherence, donnees, exports, graphiques, ia
from . import html_blocs as hb
from . import tests_externes as te
from .anonymisation import Pseudonymiseur
from .modeles import ANCIENS_PLACEHOLDERS_IA, MODELES, PLACEHOLDER_IA, SECTIONS_FINALES, section_du_modele
from .models import Bilan, EnTeteBilan, MessageBilan, TexteType, VersionBilan
from .textes_types import bibliotheque

INTERVALLE_VERSION_AUTO = timedelta(minutes=10)
LIMITE_MESSAGE = 2000
LIMITE_SELECTION = 6000
TAILLE_MAX_IMAGE = 2 * 1024 * 1024
# Poids d'une section dans un lot de rédaction IA (un lot = un appel, budget POIDS_LOT)
POIDS_LOT = 4
POIDS_LOURDS = {'wisc5', 'wais4', 'brief', 'brief_papier', 'teach', 'conclusion', 'recommandations'}


def _bilans(request):
    if request.user.is_superadmin():
        return Bilan.all_objects.all()
    return Bilan.objects.filter(organization=request.user.organization)


def _get_bilan(request, bilan_id):
    return get_object_or_404(_bilans(request).select_related('patient', 'organization', 'psychologue'), id=bilan_id)


def _get_patient(request, patient_id):
    if request.user.is_superadmin():
        return get_object_or_404(Patient.all_objects, id=patient_id)
    return get_object_or_404(Patient, id=patient_id, organization=request.user.organization)


def _peut_voir_clinique(user):
    """Anamnèse et notes de séance relèvent du module Consultations (comme sur la fiche
    patient) : sans cet accès, elles ne sont ni proposées ni envoyées à l'IA."""
    return user.has_module_access('consultations')


def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _erreur(message, status=400, **extra):
    return JsonResponse({'ok': False, 'erreur': message, **extra}, status=status)


def _bilans_precedents(patient, exclure=None):
    bilans = Bilan.all_objects.filter(organization=patient.organization, patient=patient).order_by('-date_creation')
    return bilans.exclude(id=exclure) if exclure else bilans


# --- liste / création ------------------------------------------------------------------------

@login_required
@require_test_access('bilans')
def bilans_liste(request):
    bilans = _bilans(request).select_related('patient', 'psychologue')
    patient = None
    if request.GET.get('patient', '').isdigit():
        patient = _get_patient(request, int(request.GET['patient']))
        bilans = bilans.filter(patient=patient)
    return render(request, 'bilans/liste.html', {'bilans': bilans, 'patient': patient, 'modeles': MODELES})


def _contexte_choix_tests(user, patient):
    peut_clinique = _peut_voir_clinique(user)
    return {
        'tests': donnees.tests_disponibles(user, patient),
        'peut_clinique': peut_clinique,
        'a_anamnese': peut_clinique and hasattr(patient, 'anamnese'),
        'nb_seances': patient.consultation_set.filter(statut_consultation='termine').count() if peut_clinique else 0,
        'groupes_externes': te.groupes_catalogue(),
    }


def _champs_infos(infos, modele):
    """Champs du formulaire des informations du bilan, avec leur valeur actuelle."""
    champs = []
    for cle, libelle, type_champ in donnees.CHAMPS_INFOS:
        valeur = infos.get(cle, '')
        if cle == 'sous_titre' and cle not in infos:
            valeur = modele.get('sous_titre', '')
        if cle == 'date_evaluation' and not valeur:
            valeur = timezone.localdate().isoformat()
        champs.append({'name': f'info_{cle}', 'cle': cle, 'libelle': libelle, 'type': type_champ, 'value': valeur,
                       'choix': donnees.CIVILITES if type_champ == 'choix' else []})
    return champs


@login_required
@require_test_access('bilans')
def bilan_nouveau(request):
    patient_id = request.POST.get('patient') or request.GET.get('patient')
    if not (patient_id and str(patient_id).isdigit()):
        patients = Patient.all_objects.all() if request.user.is_superadmin() else Patient.objects.all()
        return render(request, 'bilans/choisir_patient.html', {
            'patients': patients.order_by('nom', 'prenom'),
            'derniers_patients': patients.order_by('-date_creation')[:5],
        })

    patient = _get_patient(request, int(patient_id))
    contexte = _contexte_choix_tests(request.user, patient)
    precedents = list(_bilans_precedents(patient))

    if request.method == 'POST':
        cle_modele = request.POST.get('modele')
        if cle_modele not in MODELES:
            messages.error(request, "Choisissez un modèle de bilan.")
        else:
            modele = MODELES[cle_modele]
            refs_valides = {t['ref'] for t in contexte['tests']}
            externes = [cle for cle in request.POST.getlist('externes') if cle in te.TESTS]
            precedent = request.POST.get('bilan_precedent', '')
            bilan = Bilan.objects.create(
                organization=patient.organization,
                patient=patient,
                psychologue=request.user,
                modele=cle_modele,
                titre=(request.POST.get('titre') or '').strip()[:200] or modele['titre'],
                sources={
                    'anamnese': contexte['a_anamnese'] and request.POST.get('anamnese') == '1',
                    'consultations': (contexte['peut_clinique'] and contexte['nb_seances'] > 0
                                      and request.POST.get('consultations') == '1'),
                    'tests': [ref for ref in request.POST.getlist('tests') if ref in refs_valides],
                    'bilan_precedent': int(precedent) if precedent.isdigit() and any(
                        b.id == int(precedent) for b in precedents) else None,
                },
                infos=donnees.lire_infos(request.POST, modele),
                scores={cle: te.saisie_vide() for cle in externes},
            )
            bilan.contenu = donnees.construire_contenu(bilan, request.user)
            bilan.save(update_fields=['contenu'])
            VersionBilan.objects.create(bilan=bilan, contenu=bilan.contenu, motif="Création", auteur=request.user)
            if externes:
                messages.info(request, "Bilan créé. Saisissez maintenant les scores des tests passés hors plateforme.")
                return redirect('bilans:donnees', bilan_id=bilan.id)
            return redirect('bilans:editeur', bilan_id=bilan.id)

    return render(request, 'bilans/nouveau.html', {
        'patient': patient,
        'modeles': MODELES,
        'precedents': precedents,
        'champs_infos': _champs_infos({}, {}),
        **contexte,
    })


# --- scores et informations -----------------------------------------------------------------

@login_required
@require_test_access('bilans')
def bilan_donnees(request, bilan_id):
    """Informations de la page de garde, tests inclus et saisie des scores des tests externes.
    À l'enregistrement, les tableaux et sections « Données » du document sont régénérés."""
    bilan = _get_bilan(request, bilan_id)
    contexte = _contexte_choix_tests(request.user, bilan.patient)
    modele = MODELES.get(bilan.modele, {})

    if request.method == 'POST':
        if bilan.est_finalise:
            messages.error(request, "Ce bilan est finalisé : rouvrez-le pour modifier ses données.")
            return redirect('bilans:editeur', bilan_id=bilan.id)
        refs_valides = {t['ref'] for t in contexte['tests']}
        externes = [cle for cle in request.POST.getlist('externes') if cle in te.TESTS]
        bilan.infos = donnees.lire_infos(request.POST, modele)
        bilan.sources = dict(bilan.sources or {}, tests=[ref for ref in request.POST.getlist('tests') if ref in refs_valides])
        if contexte['peut_clinique']:
            bilan.sources['anamnese'] = contexte['a_anamnese'] and request.POST.get('anamnese') == '1'
            bilan.sources['consultations'] = contexte['nb_seances'] > 0 and request.POST.get('consultations') == '1'
        precedent = request.POST.get('bilan_precedent', '')
        bilan.sources['bilan_precedent'] = int(precedent) if precedent.isdigit() and _bilans_precedents(
            bilan.patient, exclure=bilan.id).filter(id=int(precedent)).exists() else None
        bilan.scores = {cle: te.lire_formulaire(cle, request.POST) for cle in externes}
        _enregistrer(bilan, donnees.rafraichir_contenu(bilan, request.user), request.user,
                     motif_version="Avant mise à jour des données")
        bilan.save()
        messages.success(request, "Données enregistrées : tableaux et graphiques mis à jour dans le bilan.")
        if request.POST.get('suite') == 'rester':
            return redirect('bilans:donnees', bilan_id=bilan.id)
        return redirect('bilans:editeur', bilan_id=bilan.id)

    refs_coches = set((bilan.sources or {}).get('tests', []))
    formulaires = []
    for cle, test in te.TESTS.items():
        saisie = (bilan.scores or {}).get(cle)
        formulaires.append({'cle': cle, 'test': test, 'inclus': saisie is not None, 'nom': te.nom_court(cle, saisie),
                            'domaine': te.LIBELLES_DOMAINES[test['domaine']], 'form': te.formulaire(cle, saisie)})
    return render(request, 'bilans/donnees.html', {
        'bilan': bilan,
        'modele': modele,
        'formulaires': formulaires,
        'refs_coches': refs_coches,
        'precedents': _bilans_precedents(bilan.patient, exclure=bilan.id),
        'champs_infos': _champs_infos(bilan.infos or {}, modele),
        **contexte,
    })


@login_required
@require_test_access('bilans')
@require_GET
def bilan_figure(request, bilan_id, ref):
    """Graphique d'un bilan (PNG) : profil d'un test (« wisc5.indices ») ou signature."""
    bilan = _get_bilan(request, bilan_id)
    png = exports.png_figure(bilan, ref)
    if png is None:
        raise Http404
    reponse = HttpResponse(png, content_type='image/png')
    reponse['Cache-Control'] = 'private, no-cache'
    return reponse


# --- éditeur ---------------------------------------------------------------------------------

@login_required
@require_test_access('bilans')
def bilan_editeur(request, bilan_id):
    bilan = _get_bilan(request, bilan_id)
    historique = [
        {'role': m.role, 'contenu': m.contenu, 'proposition': m.proposition, 'selection': m.selection,
         'proposition_html': _proposition_html(m.proposition)}
        for m in bilan.messages.all()
    ]
    return render(request, 'bilans/editeur.html', {
        'bilan': bilan,
        'modele': MODELES.get(bilan.modele, {}),
        'items': donnees.tests_inclus(bilan, request.user),
        'ia_configuree': ia.ia_configuree(),
        'appels_restants': ia.appels_restants(bilan.organization),
        'historique': historique,
        'placeholders_ia': [PLACEHOLDER_IA, *ANCIENS_PLACEHOLDERS_IA],
        'a_en_tete': EnTeteBilan.objects.filter(utilisateur=request.user).exists(),
        'sections_sans_source': sections_sans_source(bilan, request.user),
    })


def _enregistrer(bilan, contenu, user, motif_version=None):
    """Nettoie et enregistre le contenu. Versionne l'ancien contenu si demandé, ou
    automatiquement s'il n'y a pas eu de version depuis INTERVALLE_VERSION_AUTO."""
    contenu = hb.nettoyer(contenu)
    if contenu != bilan.contenu:
        derniere = bilan.versions.first()
        if motif_version or not derniere or derniere.date < timezone.now() - INTERVALLE_VERSION_AUTO:
            VersionBilan.objects.create(bilan=bilan, contenu=bilan.contenu,
                                        motif=motif_version or "Sauvegarde automatique", auteur=user)
        bilan.contenu = contenu
    return contenu


@login_required
@require_test_access('bilans')
@require_POST
def bilan_sauvegarder(request, bilan_id):
    bilan = _get_bilan(request, bilan_id)
    if bilan.est_finalise:
        return _erreur("Ce bilan est finalisé : rouvrez-le pour le modifier.", status=409)
    data = _json_body(request)
    if 'contenu' in data:
        motif = "Avant modification IA" if data.get('version_avant') else None
        _enregistrer(bilan, str(data['contenu']), request.user, motif)
    titre = str(data.get('titre') or '').strip()[:200]
    if titre:
        bilan.titre = titre
    bilan.save()
    return JsonResponse({'ok': True, 'date_modification': timezone.localtime(bilan.date_modification).strftime('%H:%M')})


@login_required
@require_test_access('bilans')
@require_POST
def bilan_statut(request, bilan_id):
    bilan = _get_bilan(request, bilan_id)
    if request.POST.get('action') == 'finaliser':
        VersionBilan.objects.create(bilan=bilan, contenu=bilan.contenu, motif="Finalisation", auteur=request.user)
        bilan.statut = 'finalise'
        messages.success(request, "Bilan finalisé. Il n'est plus modifiable tant qu'il n'est pas rouvert.")
    elif request.POST.get('action') == 'rouvrir':
        bilan.statut = 'brouillon'
        messages.success(request, "Bilan rouvert en brouillon.")
    bilan.save()
    return redirect('bilans:editeur', bilan_id=bilan.id)


@login_required
@require_test_access('bilans')
@require_GET
def bilan_versions(request, bilan_id):
    bilan = _get_bilan(request, bilan_id)
    versions = [{
        'id': v.id,
        'motif': v.motif,
        'date': timezone.localtime(v.date).strftime('%d/%m/%Y %H:%M'),
        'auteur': (v.auteur.get_full_name() or v.auteur.username) if v.auteur else '',
    } for v in bilan.versions.select_related('auteur')[:50]]
    return JsonResponse({'ok': True, 'versions': versions})


@login_required
@require_test_access('bilans')
@require_POST
def bilan_restaurer_version(request, bilan_id, version_id):
    bilan = _get_bilan(request, bilan_id)
    if bilan.est_finalise:
        return _erreur("Ce bilan est finalisé : rouvrez-le pour le modifier.", status=409)
    version = get_object_or_404(bilan.versions, id=version_id)
    _enregistrer(bilan, version.contenu, request.user, motif_version="Avant restauration d'une version")
    bilan.save()
    return JsonResponse({'ok': True, 'contenu': bilan.contenu})


@login_required
@require_test_access('bilans')
def bilan_supprimer(request, bilan_id):
    bilan = _get_bilan(request, bilan_id)
    if request.method == 'POST':
        patient_id = bilan.patient_id
        bilan.delete()
        messages.success(request, "Bilan supprimé.")
        return redirect(f"{reverse('bilans:liste')}?patient={patient_id}")
    return render(request, 'bilans/supprimer.html', {'bilan': bilan})


@login_required
@require_test_access('bilans')
def bilan_export(request, bilan_id, format_export):
    if format_export not in ('docx', 'pdf'):
        raise Http404
    bilan = _get_bilan(request, bilan_id)
    if format_export == 'docx':
        contenu = exports.exporter_docx(bilan)
        type_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        contenu = exports.exporter_pdf(bilan)
        type_mime = 'application/pdf'
    reponse = HttpResponse(contenu, content_type=type_mime)
    # ?apercu=1 : le PDF s'ouvre dans un onglet du navigateur au lieu d'être téléchargé
    mode = 'inline' if format_export == 'pdf' and request.GET.get('apercu') == '1' else 'attachment'
    reponse['Content-Disposition'] = f'{mode}; filename="{exports.nom_fichier(bilan, format_export)}"'
    return reponse


# --- cohérence ---------------------------------------------------------------------------------

@login_required
@require_test_access('bilans')
def bilan_coherence(request, bilan_id):
    """GET : relecture automatique (sans IA). POST : relecture par l'IA (un appel)."""
    bilan = _get_bilan(request, bilan_id)
    if request.method == 'GET':
        alertes = coherence.verifier(bilan.contenu, donnees.valeurs_de_reference(bilan, request.user))
        return JsonResponse({'ok': True, 'alertes': alertes})

    if bilan.est_finalise:
        return _erreur("Ce bilan est finalisé : rouvrez-le pour le relire avec l'IA.", status=409)
    data = _json_body(request)
    if 'contenu' in data:
        _enregistrer(bilan, str(data['contenu']), request.user)
        bilan.save()
    pseudo = Pseudonymiseur.pour_bilan(bilan)
    messages_ia = ia.messages_relecture(pseudo.masquer(hb.en_texte(hb.lire(bilan.contenu))),
                                        _contexte_masque(bilan, request.user, pseudo, place_pour_bilan=True))
    try:
        reponse = ia.appeler_journalise('relecture', bilan, request.user, messages_ia,
                                        max_tokens=ia.max_tokens_pour(messages_ia, 3500))
    except ia.IAErreur as e:
        return _erreur(str(e), status=502, attendre=e.attendre)
    problemes = []
    for p in reponse.get('problemes') or []:
        if isinstance(p, dict) and p.get('probleme'):
            problemes.append({k: pseudo.restaurer(str(p.get(k) or '')).strip() for k in ('passage', 'probleme', 'suggestion')})
    return JsonResponse({'ok': True, 'problemes': problemes[:15], 'restants': ia.appels_restants(bilan.organization)})


# --- IA --------------------------------------------------------------------------------------

def _est_vide_ou_placeholder(corps):
    texte = ' '.join(hb.en_texte([b]) for b in corps).strip()
    return not texte or texte == PLACEHOLDER_IA or texte in ANCIENS_PLACEHOLDERS_IA


def _a_source_clinique(bilan, user):
    sources = bilan.sources or {}
    return _peut_voir_clinique(user) and bool(sources.get('anamnese') or sources.get('consultations'))


def sections_sans_source(bilan, user):
    """Sections IA qui exigent l'anamnèse ou les notes de séance, quand le bilan n'en a pas."""
    if _a_source_clinique(bilan, user):
        return []
    return [s['cle'] for s in MODELES.get(bilan.modele, {}).get('sections', []) if s.get('besoin') == 'clinique']


def _sections_a_rediger(bilan, user, cles_forcees=None):
    """Sections à rédiger, dans l'ordre du document : sections IA du modèle et interprétations
    des chapitres de test, encore vides (ou avec le texte d'attente) - ou, si `cles_forcees` est
    fourni (réécriture demandée par le psy), ces sections-là même remplies.
    -> [{'cle', 'titre', 'consigne', 'poids'}]"""
    _, sections_doc = hb.decouper_sections(hb.lire(bilan.contenu))
    items = {item['section']: item for item in donnees.tests_inclus(bilan, user)}
    sans_source = set(sections_sans_source(bilan, user))
    a_rediger = []
    for titre_bloc, corps in sections_doc:
        cle, type_section = titre_bloc['section'], titre_bloc.get('section_type')
        titre = hb.texte_runs(titre_bloc['runs'])
        if type_section == 'ia':
            section = section_du_modele(bilan.modele, cle)
            if not section or section['type'] != 'ia' or cle in sans_source:
                continue
            vide = _est_vide_ou_placeholder(corps)
            entree = {'cle': cle, 'titre': titre, 'consigne': section['consigne'],
                      'poids': 3 if cle in POIDS_LOURDS else 1}
        elif type_section == 'test' and cle in items:
            _, interpretation = donnees.decouper_interpretation(corps)
            vide = not interpretation or _est_vide_ou_placeholder(interpretation[1:])
            entree = {'cle': cle, 'titre': titre, 'consigne': ia.consigne_test(items[cle]),
                      'poids': 3 if items[cle]['cle'] in POIDS_LOURDS else 2}
        else:
            continue
        if (cles_forcees and cle in cles_forcees) or (not cles_forcees and vide):
            a_rediger.append(entree)
    return a_rediger


def _prochain_lot(sections):
    """Les sections finales (conclusion, recommandations) passent en dernier, une à une, pour
    s'appuyer sur les interprétations déjà rédigées ; les autres par lots de POIDS_LOT."""
    normales = [s for s in sections if s['cle'] not in SECTIONS_FINALES]
    if not normales:
        return sections[:1], True
    lot, poids = [], 0
    for section in normales:
        if lot and poids + section['poids'] > POIDS_LOT:
            break
        lot.append(section)
        poids += section['poids']
    return lot, False


def _contexte_masque(bilan, user, pseudo, place_pour_bilan=False):
    """Contexte anonymisé, réduit (moins de notes de séance) s'il dépasse le budget de jetons."""
    if not _peut_voir_clinique(user):
        sources = dict(bilan.sources, anamnese=False, consultations=False)
        bilan = Bilan(organization=bilan.organization, patient=bilan.patient, sources=sources,
                      infos=bilan.infos, scores=bilan.scores, modele=bilan.modele, titre=bilan.titre, id=bilan.id)
    budget = (settings.IA_LIMITE_JETONS_MINUTE - 3000 - (2500 if place_pour_bilan else 0)) * 3.3
    for nb_seances in (donnees.NB_SEANCES_MAX, 6, 3, 0):
        texte = donnees.contexte_patient(bilan, user, nb_seances_max=nb_seances)
        if len(texte) <= budget:
            break
    return pseudo.masquer(texte)


def _messages_lot(bilan, user, pseudo, lot, finale):
    bilan_en_cours = ''
    if finale:
        bilan_en_cours = pseudo.masquer(hb.en_texte(hb.lire(bilan.contenu)))
    contexte = _contexte_masque(bilan, user, pseudo, place_pour_bilan=finale)
    titre_modele = MODELES[bilan.modele].get('nom', MODELES[bilan.modele]['titre'])
    messages_ia = ia.messages_premier_jet(titre_modele, contexte, lot, bilan_en_cours)
    while finale and ia.trop_long(messages_ia) and len(bilan_en_cours) > 2000:
        bilan_en_cours = bilan_en_cours[:int(len(bilan_en_cours) * 0.7)]
        messages_ia = ia.messages_premier_jet(titre_modele, contexte, lot, bilan_en_cours)
    return messages_ia


@login_required
@require_test_access('bilans')
@require_GET
def bilan_ia_apercu(request, bilan_id):
    """Texte exact qui serait envoyé à l'IA pour le prochain lot de rédaction (déjà anonymisé)."""
    bilan = _get_bilan(request, bilan_id)
    pseudo = Pseudonymiseur.pour_bilan(bilan)
    sections = _sections_a_rediger(bilan, request.user)
    lot, finale = _prochain_lot(sections) if sections else ([], False)
    message = _messages_lot(bilan, request.user, pseudo, lot, finale)[-1]
    return JsonResponse({'ok': True, 'texte': message['content'], 'nb_sections': len(sections)})


@login_required
@require_test_access('bilans')
@require_POST
def bilan_ia_premier_jet(request, bilan_id):
    """Rédige le prochain lot de sections (un appel IA). L'éditeur rappelle tant qu'il en reste."""
    bilan = _get_bilan(request, bilan_id)
    if bilan.est_finalise:
        return _erreur("Ce bilan est finalisé : rouvrez-le pour le modifier.", status=409)
    data = _json_body(request)
    if 'contenu' in data:
        _enregistrer(bilan, str(data['contenu']), request.user)
        bilan.save()

    cles_forcees = data.get('sections') if isinstance(data.get('sections'), list) else None
    sections = _sections_a_rediger(bilan, request.user, cles_forcees)
    if not sections:
        if cles_forcees and set(cles_forcees) & set(sections_sans_source(bilan, request.user)):
            return _erreur("Cette section s'appuie sur l'anamnèse ou les notes de séance, absentes de ce bilan : "
                           "ajoutez-les dans « Scores et informations », ou écrivez-la directement.")
        return _erreur("Toutes les sections à rédiger par l'IA sont déjà remplies : choisissez une section "
                       "à réécrire, ou utilisez le chat pour la retravailler.")
    lot, finale = _prochain_lot(sections)

    pseudo = Pseudonymiseur.pour_bilan(bilan)
    messages_ia = _messages_lot(bilan, request.user, pseudo, lot, finale)
    souhaite = 1500 + 1300 * sum(s['poids'] for s in lot)
    try:
        reponse = ia.appeler_journalise('premier_jet', bilan, request.user, messages_ia,
                                        max_tokens=ia.max_tokens_pour(messages_ia, souhaite))
    except ia.IAErreur as e:
        return _erreur(str(e), status=502, attendre=e.attendre)

    textes = reponse.get('sections') if isinstance(reponse.get('sections'), dict) else reponse
    a_remplir = {s['cle'] for s in lot}
    preambule, sections_doc = hb.decouper_sections(hb.lire(bilan.contenu))
    remplies = []
    for n, (titre_bloc, corps) in enumerate(sections_doc):
        cle = titre_bloc['section']
        texte = textes.get(cle) if isinstance(textes, dict) else None
        if cle not in a_remplir or not isinstance(texte, str) or not texte.strip():
            continue
        titre = hb.texte_runs(titre_bloc['runs'])
        nouveaux = hb.blocs_depuis_texte(pseudo.restaurer(texte), titre_a_ignorer=titre)
        if titre_bloc.get('section_type') == 'test':
            calcule, interpretation = donnees.decouper_interpretation(corps)
            if not cles_forcees and interpretation and not _est_vide_ou_placeholder(interpretation[1:]):
                continue
            titre_interp = interpretation[:1] or [hb.titre(3, donnees.TITRE_INTERPRETATION)]
            sections_doc[n] = (titre_bloc, calcule + titre_interp + nouveaux)
        else:
            if not cles_forcees and not _est_vide_ou_placeholder(corps):
                continue
            sections_doc[n] = (titre_bloc, nouveaux)
        remplies.append(titre)
    if not remplies:
        return _erreur("L'IA n'a renvoyé aucune section exploitable. Réessayez.", status=502)

    _enregistrer(bilan, hb.ecrire(hb.assembler_sections(preambule, sections_doc)), request.user,
                 motif_version="Avant réécriture IA" if cles_forcees else "Avant rédaction IA")
    bilan.save()
    restantes = 0 if cles_forcees else len(_sections_a_rediger(bilan, request.user))
    return JsonResponse({'ok': True, 'contenu': bilan.contenu, 'remplies': remplies, 'restantes': restantes,
                         'restants': ia.appels_restants(bilan.organization)})


@login_required
@require_test_access('bilans')
@require_POST
def bilan_ia_chat(request, bilan_id):
    bilan = _get_bilan(request, bilan_id)
    if bilan.est_finalise:
        return _erreur("Ce bilan est finalisé : rouvrez-le pour le retravailler.", status=409)
    data = _json_body(request)
    demande = str(data.get('message') or '').strip()[:LIMITE_MESSAGE]
    selection = str(data.get('selection') or '').strip()[:LIMITE_SELECTION]
    if not demande:
        return _erreur("Écrivez votre demande.")
    if 'contenu' in data:
        _enregistrer(bilan, str(data['contenu']), request.user)
        bilan.save()

    pseudo = Pseudonymiseur.pour_bilan(bilan)
    historique = [(m.role, pseudo.masquer(m.contenu)) for m in bilan.messages.all()]
    messages_ia = ia.messages_chat(
        pseudo.masquer(hb.en_texte(hb.lire(bilan.contenu))),
        _contexte_masque(bilan, request.user, pseudo, place_pour_bilan=True),
        historique,
        pseudo.masquer(demande),
        pseudo.masquer(selection),
    )
    MessageBilan.objects.create(bilan=bilan, role='psy', contenu=demande, selection=selection)
    try:
        reponse = ia.appeler_journalise('chat', bilan, request.user, messages_ia,
                                        max_tokens=ia.max_tokens_pour(messages_ia, 3500))
    except ia.IAErreur as e:
        return _erreur(str(e), status=502, attendre=e.attendre)

    texte = pseudo.restaurer(str(reponse.get('reponse') or '').strip()) or "Voici ma proposition."
    proposition = reponse.get('proposition')
    proposition = pseudo.restaurer(proposition.strip()) if isinstance(proposition, str) and proposition.strip() else ''
    MessageBilan.objects.create(bilan=bilan, role='ia', contenu=texte, proposition=proposition)
    return JsonResponse({'ok': True, 'reponse': texte, 'proposition': proposition,
                         'proposition_html': _proposition_html(proposition),
                         'restants': ia.appels_restants(bilan.organization)})


def _proposition_html(proposition):
    """Proposition du chat en HTML propre (listes, sous-titres) pour l'insérer telle quelle."""
    return hb.ecrire(hb.blocs_depuis_texte(proposition)) if proposition else ''


# --- bibliothèque de textes types ------------------------------------------------------------

@login_required
@require_test_access('bilans')
@require_GET
def textes_types_json(request):
    textes = [dict(t, html=_proposition_html(t['contenu'])) for t in bibliotheque(request.user.organization)]
    return JsonResponse({'ok': True, 'textes': textes, 'categories': TexteType.CATEGORIE_CHOICES})


@login_required
@require_test_access('bilans')
def textes_types(request):
    """Gestion de la bibliothèque du cabinet : modifier un texte fourni (copie personnalisée),
    le masquer ou le rétablir, ajouter ou supprimer ses propres textes."""
    org = request.user.organization
    if org is None:
        messages.error(request, "La bibliothèque de textes est propre à un cabinet.")
        return redirect('bilans:liste')
    if request.method == 'POST':
        action = request.POST.get('action')
        cle = (request.POST.get('cle') or '').strip()[:60]
        id_texte = request.POST.get('id', '')
        perso = TexteType.objects.filter(organization=org, id=int(id_texte)).first() if id_texte.isdigit() else None
        titre = (request.POST.get('titre') or '').strip()[:150]
        contenu = (request.POST.get('contenu') or '').strip()[:4000]
        categorie = request.POST.get('categorie')
        if categorie not in dict(TexteType.CATEGORIE_CHOICES):
            categorie = 'autre'
        if action == 'enregistrer' and titre:
            if perso:
                perso.titre, perso.contenu = titre, contenu
                perso.save()
            elif cle:
                TexteType.objects.update_or_create(organization=org, cle=cle, defaults={
                    'titre': titre, 'contenu': contenu, 'categorie': categorie, 'masque': False})
            else:
                TexteType.objects.create(organization=org, titre=titre, contenu=contenu, categorie=categorie)
            messages.success(request, "Texte enregistré.")
        elif action == 'masquer' and cle:
            TexteType.objects.update_or_create(organization=org, cle=cle, defaults={
                'titre': titre or cle, 'categorie': categorie, 'masque': True})
            messages.success(request, "Texte retiré de la bibliothèque.")
        elif action == 'retablir' and cle:
            TexteType.objects.filter(organization=org, cle=cle).delete()
            messages.success(request, "Texte d'origine rétabli.")
        elif action == 'supprimer' and perso and not perso.cle:
            perso.delete()
            messages.success(request, "Texte supprimé.")
        return redirect('bilans:textes_types')

    textes = bibliotheque(org)
    masques = TexteType.objects.filter(organization=org, masque=True).exclude(cle='')
    groupes = [(code, libelle, [t for t in textes if t['categorie'] == code]) for code, libelle in TexteType.CATEGORIE_CHOICES]
    return render(request, 'bilans/textes_types.html', {'groupes': groupes, 'masques': masques,
                                                        'categories': TexteType.CATEGORIE_CHOICES})


# --- en-tête des exports -----------------------------------------------------------------------

def _image_valide(fichier):
    if not fichier:
        return None
    if fichier.size > TAILLE_MAX_IMAGE:
        return "Image trop lourde (2 Mo maximum)."
    if graphiques.image_png(fichier) is None:
        return "Fichier image illisible (PNG ou JPEG attendu)."
    return None


@login_required
@require_test_access('bilans')
def en_tete(request):
    """Papier à en-tête du psychologue connecté pour l'export de ses bilans."""
    # Pas d'enregistrement à la simple consultation : l'en-tête n'existe qu'une fois validé
    objet = EnTeteBilan.objects.filter(utilisateur=request.user).first() or EnTeteBilan(
        utilisateur=request.user, nom_affiche=request.user.get_full_name(),
        titre_pro="Psychologue clinicienne" if request.user.role == 'psychologist' else '')
    champs = ['nom_affiche', 'titre_pro', 'specialites', 'texte_droite', 'pied_de_page', 'mention_confidentielle',
              'formule_signature']
    if request.method == 'POST':
        for champ in champs:
            limite = EnTeteBilan._meta.get_field(champ).max_length or 1500
            setattr(objet, champ, (request.POST.get(champ) or '').strip()[:limite])
        erreurs = []
        for champ_image in ('logo', 'signature'):
            fichier = request.FILES.get(champ_image)
            erreur = _image_valide(fichier)
            if erreur:
                erreurs.append(erreur)
            elif fichier:
                getattr(objet, champ_image).save(f'{champ_image}_{request.user.id}.png', fichier, save=False)
            if request.POST.get(f'supprimer_{champ_image}') == '1':
                getattr(objet, champ_image).delete(save=False)
        objet.save()
        for erreur in erreurs:
            messages.error(request, erreur)
        if not erreurs:
            messages.success(request, "En-tête enregistré : il s'applique à vos prochains exports Word et PDF.")
        retour = request.POST.get('retour') or ''
        if retour.isdigit():
            return redirect('bilans:editeur', bilan_id=int(retour))
        return redirect('bilans:en_tete')
    return render(request, 'bilans/en_tete.html', {'en_tete': objet, 'retour': request.GET.get('retour', '')})


@login_required
@require_test_access('bilans')
@require_GET
def en_tete_image(request, champ):
    if champ not in ('logo', 'signature'):
        raise Http404
    objet = EnTeteBilan.objects.filter(utilisateur=request.user).first()
    png = graphiques.image_png(getattr(objet, champ)) if objet and getattr(objet, champ) else None
    if png is None:
        raise Http404
    return HttpResponse(png, content_type='image/png')
