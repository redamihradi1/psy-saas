"""Cabinet virtuel (bêta, page à part, plein écran) : le cabinet en vue isométrique, chaque
pièce mène à une partie de l'app. Le Secrétariat (agenda, créneaux libres, création de
consultation), la Salle d'attente (consultations du jour) et la Bibliothèque (tests) s'ouvrent
dans un panneau latéral sans quitter la page. Pas d'IA ici : tout est calculé sur le serveur.
"""
import json
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import require_module_access
from ..models import Consultation, Indisponibilite, Patient

HEURE_OUVERTURE = 9
HEURE_FERMETURE = 19
DUREE_MIN_CRENEAU = 60
NB_JOURS_MAX = 14
LIMITE_DEMANDE = 500
JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre',
        'octobre', 'novembre', 'décembre']


def _date_longue(d):
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def _initiales(patient):
    return f"{(patient.prenom or ' ')[0]}{(patient.nom or ' ')[0]}".upper().strip()


def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


# --- la page ---------------------------------------------------------------------------------

def _resume_salle_attente(organization):
    """Patients attendus aujourd'hui (consultations planifiées) pour les chaises de la salle."""
    maintenant = timezone.now()
    attendus = list(Consultation.objects.filter(
        organization=organization, date_seance__date=timezone.localdate(), statut_consultation='planifie',
    ).select_related('patient').order_by('date_seance'))
    prochain = next((c for c in attendus if c.date_seance >= maintenant - timedelta(minutes=15)), None)
    return {
        'nb_attente': len(attendus),
        'initiales': [_initiales(c.patient) for c in attendus[:6]],
        # Personnages assis dans la salle d'attente : apparence tirée de l'id (stable, jamais
        # déduite du prénom), taille enfant d'après la catégorie d'âge de la fiche.
        'patients': [{
            'nom': c.patient.nom_complet,
            'heure': timezone.localtime(c.date_seance).strftime('%H:%M'),
            'enfant': c.patient.categorie_age == 'enfant',
            'graine': c.patient_id,
        } for c in attendus[:30]],  # 10 places assises, le reste en « +N »
        'prochain': timezone.localtime(prochain.date_seance).strftime('%H:%M') if prochain else None,
        'prochain_patient': prochain.patient.nom_complet if prochain else None,
    }


def _pieces(user, organization):
    """Infos vivantes de chaque pièce, ou None si l'utilisateur n'y a pas accès (porte fermée)."""
    license = getattr(organization, 'license', None)
    can = user.has_module_access
    pieces = {}

    if can('consultations'):
        resume = _resume_salle_attente(organization)
        pieces['attente'] = resume
        prochaine = Consultation.objects.filter(
            organization=organization, date_seance__gte=timezone.now(), statut_consultation='planifie',
        ).select_related('patient').order_by('date_seance').first()
        if prochaine:
            debut = timezone.localtime(prochaine.date_seance)
            jour = "aujourd'hui" if debut.date() == timezone.localdate() else _date_longue(debut.date())
            pieces['accueil'] = {'prochaine': f"{jour} à {debut:%H:%M}", 'patient': prochaine.patient.nom_complet}
        else:
            pieces['accueil'] = {'prochaine': None}
    else:
        pieces['attente'] = pieces['accueil'] = None

    pieces['bureau'] = {'nb_patients': Patient.objects.filter(organization=organization).count()} \
        if can('patients') else None

    # Bibliothèque : un livre par test autorisé (nom, nombre de passations, liens)
    from tests_psy.models import TestBeck, TestBRIEF, TestD2R, TestSTAI, TestVineland
    catalogue = [
        ('vineland', 'Vineland', "Vineland-II · comportement adaptatif", TestVineland),
        ('brief', 'BRIEF', "BRIEF · fonctions exécutives", TestBRIEF),
        ('d2r', 'D2R', "d2-R · attention et concentration", TestD2R),
        ('beck', 'Beck', "Inventaire de dépression de Beck", TestBeck),
        ('stai', 'STAI', "STAI · anxiété état-trait", TestSTAI),
    ]
    livres = [{
        'cle': cle, 'nom': nom, 'description': description,
        'nb': modele.all_objects.filter(organization=organization).count(),
        'url': reverse(f'tests_psy:{cle}_liste'), 'url_nouveau': reverse(f'tests_psy:{cle}_nouveau'),
    } for cle, nom, description, modele in catalogue
        if license and getattr(license, f'has_{cle}', False) and user.has_test_permission(cle)]
    pieces['bibliotheque'] = {'tests': [l['nom'] for l in livres], 'livres': livres} if livres else None

    if license and license.has_bilans and user.has_test_permission('bilans'):
        from bilans.models import Bilan
        pieces['redaction'] = {'brouillons': Bilan.objects.filter(organization=organization, statut='brouillon').count()}
    else:
        pieces['redaction'] = None

    pieces['comptabilite'] = {'impayes': Consultation.objects.filter(
        organization=organization, statut_consultation='termine', statut_paiement='attente').count()
    } if can('comptabilite') else None

    pieces['archives'] = {} if (user.is_superadmin() or user.can_export_backup) else None
    return pieces


@login_required
def cabinet_virtuel(request):
    organization = request.user.organization
    if organization is None:  # superadmin : pas de cabinet à lui
        return redirect('accounts:clients_list')

    peut_consulter = request.user.has_module_access('consultations')
    patients = Patient.objects.filter(organization=organization).order_by('nom', 'prenom') if peut_consulter else []
    return render(request, 'cabinet/cabinet_virtuel.html', {
        'pieces': _pieces(request.user, organization),
        'aujourdhui': _date_longue(timezone.localdate()),
        'peut_agenda': request.user.has_module_access('agenda'),
        'patients_json': [{'id': p.id, 'nom': f"{p.nom} {p.prenom}"} for p in patients],
        'derniers_patients': [p.id for p in Patient.objects.filter(organization=organization)
                              .order_by('-date_creation')[:5]] if peut_consulter else [],
        'types': Consultation.TYPE_CONSULTATION_CHOICES,
        'lieux': Consultation.LIEU_CONSULTATION_CHOICES,
    })


# --- salle d'attente -------------------------------------------------------------------------

def _consultation_json(c):
    debut = timezone.localtime(c.date_seance)
    return {
        'id': c.id,
        'heure': debut.strftime('%H:%M'),
        'fin': (debut + timedelta(minutes=c.duree_minutes)).strftime('%H:%M'),
        'patient': c.patient.nom_complet,
        'patient_url': reverse('cabinet:patient_detail', args=[c.patient_id]),
        'url': reverse('cabinet:consultation_detail', args=[c.id]),
        'statut': c.statut_consultation,
        'statut_display': c.get_statut_consultation_display(),
        'paye': c.statut_paiement == 'paye',
        'tarif': str(c.tarif),
        'type': c.get_type_consultation_display(),
        'lieu': c.get_lieu_consultation_display(),
        'visio': c.lien_visio,
        'en_retard': c.statut_consultation == 'planifie' and c.date_seance < timezone.now() - timedelta(minutes=10),
    }


@login_required
@require_module_access('consultations')
@require_GET
def cv_salle_attente(request):
    organization = request.user.organization
    du_jour = Consultation.objects.filter(
        organization=organization, date_seance__date=timezone.localdate(),
    ).exclude(statut_consultation='annule').select_related('patient').order_by('date_seance')
    return JsonResponse({
        'ok': True,
        'consultations': [_consultation_json(c) for c in du_jour],
        'resume': _resume_salle_attente(organization),
    })


# --- secrétariat : agenda --------------------------------------------------------------------

def _creneaux_libres(jour, occupes):
    """Débuts d'heure libres pour une séance d'1h entre l'ouverture et la fermeture."""
    tz = timezone.get_current_timezone()
    maintenant = timezone.now()
    libres = []
    for heure in range(HEURE_OUVERTURE, HEURE_FERMETURE):
        debut = timezone.make_aware(datetime.combine(jour, time(heure)), tz)
        fin = debut + timedelta(minutes=DUREE_MIN_CRENEAU)
        if debut < maintenant:
            continue
        if all(fin <= o_debut or debut >= o_fin for o_debut, o_fin in occupes):
            libres.append(f"{heure:02d}:00")
    return libres


def agenda(organization, debut, nb_jours):
    tz = timezone.get_current_timezone()
    jours = []
    for n in range(nb_jours):
        jour = debut + timedelta(days=n)
        debut_jour = timezone.make_aware(datetime.combine(jour, time.min), tz)
        fin_jour = debut_jour + timedelta(days=1)
        consultations = list(Consultation.objects.filter(
            organization=organization, date_seance__gte=debut_jour, date_seance__lt=fin_jour,
        ).exclude(statut_consultation='annule').select_related('patient').order_by('date_seance'))
        indispos = list(Indisponibilite.objects.filter(
            organization=organization, date_debut__lt=fin_jour, date_fin__gt=debut_jour,
        ).order_by('date_debut'))
        occupes = [(c.date_seance, c.date_seance + timedelta(minutes=c.duree_minutes)) for c in consultations]
        occupes += [(i.date_debut, i.date_fin) for i in indispos]
        jours.append({
            'date': jour.isoformat(),
            'titre': "Aujourd'hui" if jour == timezone.localdate() else _date_longue(jour).capitalize(),
            'consultations': [_consultation_json(c) for c in consultations],
            'indisponibilites': [{
                'titre': i.titre, 'type': i.get_type_absence_display(),
                'debut': timezone.localtime(max(i.date_debut, debut_jour)).strftime('%H:%M'),
                'fin': timezone.localtime(min(i.date_fin, fin_jour)).strftime('%H:%M'),
            } for i in indispos],
            'libres': _creneaux_libres(jour, occupes),
        })
    return jours


def _parse_date(valeur, defaut=None):
    try:
        return datetime.strptime(str(valeur), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return defaut


@login_required
@require_module_access('consultations')
@require_GET
def cv_agenda(request):
    debut = _parse_date(request.GET.get('debut'), timezone.localdate())
    try:
        nb_jours = max(1, min(NB_JOURS_MAX, int(request.GET.get('jours', 1))))
    except ValueError:
        nb_jours = 1
    return JsonResponse({'ok': True, 'jours': agenda(request.user.organization, debut, nb_jours)})


# --- secrétariat : création de consultation --------------------------------------------------

def _valeurs_par_defaut(patient):
    """Reprend durée/type/lieu/tarif de la dernière consultation du patient (sinon défauts du modèle)."""
    derniere = Consultation.objects.filter(patient=patient).order_by('-date_seance').first() if patient else None
    return {
        'duree_minutes': derniere.duree_minutes if derniere else 60,
        'type_consultation': derniere.type_consultation if derniere else 'individuelle',
        'lieu_consultation': derniere.lieu_consultation if derniere else Consultation._meta.get_field('lieu_consultation').default,
        'tarif': str(derniere.tarif) if derniere else '',
    }


def _conflits(organization, debut, fin):
    consultations = Consultation.objects.filter(
        organization=organization, date_seance__lt=fin, date_seance__gte=debut - timedelta(hours=6),
    ).exclude(statut_consultation='annule').select_related('patient')
    conflits = [
        f"{timezone.localtime(c.date_seance):%H:%M} : {c.patient.nom_complet}"
        for c in consultations if c.date_seance + timedelta(minutes=c.duree_minutes) > debut
    ]
    conflits += [
        f"{i.get_type_absence_display()} : {i.titre}"
        for i in Indisponibilite.objects.filter(organization=organization, date_debut__lt=fin, date_fin__gt=debut)
    ]
    return conflits


@login_required
@require_module_access('consultations')
@require_POST
def cv_creer_consultation(request):
    organization = request.user.organization
    data = _json_body(request)
    erreurs = {}

    patient = Patient.objects.filter(organization=organization, id=data.get('patient_id') or 0).first()
    if not patient:
        erreurs['patient_id'] = "Choisissez un patient."
    jour = _parse_date(data.get('date'))
    try:
        heure = datetime.strptime(str(data.get('heure')), '%H:%M').time()
    except ValueError:
        heure = None
    if not jour or not heure:
        erreurs['date'] = "Date ou heure invalide."
    try:
        duree = int(data.get('duree_minutes') or 60)
        if not 15 <= duree <= 240:
            raise ValueError
    except (TypeError, ValueError):
        erreurs['duree_minutes'] = "Durée entre 15 et 240 minutes."
    type_consultation = data.get('type_consultation') or 'individuelle'
    if type_consultation not in dict(Consultation.TYPE_CONSULTATION_CHOICES):
        erreurs['type_consultation'] = "Type invalide."
    lieu = data.get('lieu_consultation') or 'visio'
    if lieu not in dict(Consultation.LIEU_CONSULTATION_CHOICES):
        erreurs['lieu_consultation'] = "Lieu invalide."
    try:
        tarif = Decimal(str(data.get('tarif') or '0').replace(',', '.'))
        if tarif < 0:
            raise InvalidOperation
    except InvalidOperation:
        erreurs['tarif'] = "Tarif invalide."
    if erreurs:
        return JsonResponse({'ok': False, 'erreurs': erreurs, 'erreur': ' '.join(erreurs.values())}, status=400)

    debut = timezone.make_aware(datetime.combine(jour, heure), timezone.get_current_timezone())
    conflits = _conflits(organization, debut, debut + timedelta(minutes=duree))
    if conflits and not data.get('forcer'):
        return JsonResponse({'ok': False, 'conflits': conflits,
                             'erreur': "Ce créneau chevauche : " + ' ; '.join(conflits)}, status=409)

    consultation = Consultation.objects.create(
        organization=organization, patient=patient, date_seance=debut, duree_minutes=duree,
        type_consultation=type_consultation, lieu_consultation=lieu, tarif=tarif,
        statut_consultation='planifie', statut_paiement='attente',
    )
    return JsonResponse({
        'ok': True,
        'consultation': _consultation_json(consultation),
        'date_longue': _date_longue(jour),
        'resume': _resume_salle_attente(organization),
    })


@login_required
@require_module_access('consultations')
@require_GET
def cv_valeurs_patient(request):
    """Durée/type/lieu/tarif habituels d'un patient (pré-remplissage du formulaire)."""
    patient = Patient.objects.filter(organization=request.user.organization,
                                     id=request.GET.get('patient_id') or 0).first()
    return JsonResponse({'ok': True, **_valeurs_par_defaut(patient)})


@login_required
@require_module_access('consultations')
@require_POST
def cv_encaisser(request, consultation_id):
    """Encaissement depuis la salle d'attente (JSON, sans message flash)."""
    consultation = Consultation.objects.filter(organization=request.user.organization, id=consultation_id).first()
    if not consultation:
        return JsonResponse({'ok': False, 'erreur': "Consultation introuvable."}, status=404)
    consultation.statut_paiement = 'paye'
    consultation.date_paiement = timezone.localdate()
    consultation.save(update_fields=['statut_paiement', 'date_paiement'])
    return JsonResponse({'ok': True})
