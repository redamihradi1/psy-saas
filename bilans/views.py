import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import require_test_access
from cabinet.models import Patient

from . import donnees, exports, ia
from . import html_blocs as hb
from .anonymisation import Pseudonymiseur
from .modeles import MODELES, PLACEHOLDER_IA, sections_ia
from .models import Bilan, MessageBilan, VersionBilan

INTERVALLE_VERSION_AUTO = timedelta(minutes=10)
LIMITE_MESSAGE = 2000
LIMITE_SELECTION = 6000


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


def _erreur(message, status=400):
    return JsonResponse({'ok': False, 'erreur': message}, status=status)


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
    tests = donnees.tests_disponibles(request.user, patient)
    peut_clinique = _peut_voir_clinique(request.user)
    a_anamnese = peut_clinique and hasattr(patient, 'anamnese')
    nb_seances = patient.consultation_set.filter(statut_consultation='termine').count() if peut_clinique else 0

    if request.method == 'POST':
        cle_modele = request.POST.get('modele')
        if cle_modele not in MODELES:
            messages.error(request, "Choisissez un modèle de bilan.")
        else:
            refs_valides = {t['ref'] for t in tests}
            bilan = Bilan.objects.create(
                organization=patient.organization,
                patient=patient,
                psychologue=request.user,
                modele=cle_modele,
                titre=(request.POST.get('titre') or '').strip()[:200] or MODELES[cle_modele]['titre'],
                sources={
                    'anamnese': a_anamnese and request.POST.get('anamnese') == '1',
                    'consultations': peut_clinique and nb_seances > 0 and request.POST.get('consultations') == '1',
                    'tests': [ref for ref in request.POST.getlist('tests') if ref in refs_valides],
                },
            )
            bilan.contenu = donnees.construire_contenu(bilan, request.user)
            bilan.save(update_fields=['contenu'])
            VersionBilan.objects.create(bilan=bilan, contenu=bilan.contenu, motif="Création", auteur=request.user)
            return redirect('bilans:editeur', bilan_id=bilan.id)

    return render(request, 'bilans/nouveau.html', {
        'patient': patient,
        'modeles': MODELES,
        'tests': tests,
        'a_anamnese': a_anamnese,
        'nb_seances': nb_seances,
        'peut_clinique': peut_clinique,
    })


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
        'tests': donnees.charger_tests(bilan, request.user),
        'ia_configuree': ia.ia_configuree(),
        'appels_restants': ia.appels_restants(bilan.organization),
        'historique': historique,
        'placeholder_ia': PLACEHOLDER_IA,
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
    reponse['Content-Disposition'] = f'attachment; filename="{exports.nom_fichier(bilan, format_export)}"'
    return reponse


# --- IA --------------------------------------------------------------------------------------

def _est_vide_ou_placeholder(corps):
    texte = ' '.join(hb.en_texte([b]) for b in corps).strip()
    return not texte or texte == PLACEHOLDER_IA


def _sections_a_rediger(bilan, cles_forcees=None):
    """Sections IA du modèle encore vides (ou avec le texte d'attente) dans le document - ou,
    si `cles_forcees` est fourni (réécriture demandée par le psy), ces sections-là même remplies."""
    _, sections_doc = hb.decouper_sections(hb.lire(bilan.contenu))
    if cles_forcees:
        presentes = {t['section'] for t, _ in sections_doc if t.get('section_type') == 'ia'}
        return [s for s in sections_ia(bilan.modele) if s['cle'] in presentes and s['cle'] in cles_forcees]
    vides = {titre_bloc['section'] for titre_bloc, corps in sections_doc
             if titre_bloc.get('section_type') == 'ia' and _est_vide_ou_placeholder(corps)}
    return [s for s in sections_ia(bilan.modele) if s['cle'] in vides]


def _contexte_masque(bilan, user, pseudo):
    if not _peut_voir_clinique(user):
        sources = dict(bilan.sources, anamnese=False, consultations=False)
        bilan = Bilan(organization=bilan.organization, patient=bilan.patient, sources=sources)
    return pseudo.masquer(donnees.contexte_patient(bilan, user))


@login_required
@require_test_access('bilans')
@require_GET
def bilan_ia_apercu(request, bilan_id):
    """Texte exact qui serait envoyé à l'IA pour la première version (déjà anonymisé)."""
    bilan = _get_bilan(request, bilan_id)
    pseudo = Pseudonymiseur.pour_bilan(bilan)
    sections = _sections_a_rediger(bilan)
    titre_modele = MODELES[bilan.modele]['titre']
    message = ia.messages_premier_jet(titre_modele, _contexte_masque(bilan, request.user, pseudo), sections)[-1]
    return JsonResponse({'ok': True, 'texte': message['content'], 'nb_sections': len(sections)})


@login_required
@require_test_access('bilans')
@require_POST
def bilan_ia_premier_jet(request, bilan_id):
    bilan = _get_bilan(request, bilan_id)
    if bilan.est_finalise:
        return _erreur("Ce bilan est finalisé : rouvrez-le pour le modifier.", status=409)
    data = _json_body(request)
    if 'contenu' in data:
        _enregistrer(bilan, str(data['contenu']), request.user)
        bilan.save()

    cles_forcees = data.get('sections') if isinstance(data.get('sections'), list) else None
    sections = _sections_a_rediger(bilan, cles_forcees)
    if not sections:
        return _erreur("Toutes les sections à rédiger par l'IA sont déjà remplies : choisissez une section "
                       "à réécrire, ou utilisez le chat pour la retravailler.")

    pseudo = Pseudonymiseur.pour_bilan(bilan)
    messages_ia = ia.messages_premier_jet(MODELES[bilan.modele]['titre'],
                                          _contexte_masque(bilan, request.user, pseudo), sections)
    try:
        reponse = ia.appeler_journalise('premier_jet', bilan, request.user, messages_ia, max_tokens=6000)
    except ia.IAErreur as e:
        return _erreur(str(e), status=502)

    textes = reponse.get('sections') if isinstance(reponse.get('sections'), dict) else reponse
    a_remplir = {s['cle'] for s in sections}
    preambule, sections_doc = hb.decouper_sections(hb.lire(bilan.contenu))
    remplies = []
    for n, (titre_bloc, corps) in enumerate(sections_doc):
        cle = titre_bloc['section']
        texte = textes.get(cle) if isinstance(textes, dict) else None
        if cle in a_remplir and isinstance(texte, str) and texte.strip() and (cles_forcees or _est_vide_ou_placeholder(corps)):
            sections_doc[n] = (titre_bloc, hb.blocs_depuis_texte(pseudo.restaurer(texte),
                                                                  titre_a_ignorer=hb.texte_runs(titre_bloc['runs'])))
            remplies.append(hb.texte_runs(titre_bloc['runs']))
    if not remplies:
        return _erreur("L'IA n'a renvoyé aucune section exploitable. Réessayez.", status=502)

    _enregistrer(bilan, hb.ecrire(hb.assembler_sections(preambule, sections_doc)), request.user,
                 motif_version="Avant réécriture IA" if cles_forcees else "Avant première version IA")
    bilan.save()
    return JsonResponse({'ok': True, 'contenu': bilan.contenu, 'remplies': remplies,
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
        _contexte_masque(bilan, request.user, pseudo),
        historique,
        pseudo.masquer(demande),
        pseudo.masquer(selection),
    )
    MessageBilan.objects.create(bilan=bilan, role='psy', contenu=demande, selection=selection)
    try:
        reponse = ia.appeler_journalise('chat', bilan, request.user, messages_ia, max_tokens=3500)
    except ia.IAErreur as e:
        return _erreur(str(e), status=502)

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
