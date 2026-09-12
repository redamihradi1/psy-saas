"""Génération minimale de flux iCalendar (.ics) pour l'abonnement agenda.

Pas de dépendance externe : le format RFC 5545 est simple pour notre besoin
(événements ponctuels, pas de récurrence). On construit le texte à la main.
"""
from datetime import timezone as dt_timezone

from django.utils import timezone

from .models import Consultation, Indisponibilite

FENETRE_PASSEE = timezone.timedelta(days=30)
FENETRE_FUTURE = timezone.timedelta(days=180)


def _escape(texte):
    return (
        (texte or '')
        .replace('\\', '\\\\')
        .replace('\n', '\\n')
        .replace(',', '\\,')
        .replace(';', '\\;')
    )


def _plier_ligne(ligne):
    """Replie une ligne selon RFC 5545 (max 75 octets par ligne physique)."""
    encoded = ligne.encode('utf-8')
    if len(encoded) <= 75:
        return ligne
    morceaux = []
    reste = ligne
    while len(reste.encode('utf-8')) > 75:
        morceaux.append(reste[:74])
        reste = reste[74:]
    morceaux.append(reste)
    return '\r\n '.join(morceaux)


def _dt_utc(dt):
    return timezone.localtime(dt, dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _vevent(uid, dtstart, dtend, summary, description='', location=''):
    lignes = [
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{_dt_utc(timezone.now())}',
        f'DTSTART:{_dt_utc(dtstart)}',
        f'DTEND:{_dt_utc(dtend)}',
        f'SUMMARY:{_escape(summary)}',
    ]
    if description:
        lignes.append(f'DESCRIPTION:{_escape(description)}')
    if location:
        lignes.append(f'LOCATION:{_escape(location)}')
    lignes.append('END:VEVENT')
    return [_plier_ligne(l) for l in lignes]


def build_ics_feed(organization):
    """Construit le flux .ics des consultations + indisponibilités d'une organisation.

    Suppose que le tenant courant (thread-local) est déjà positionné sur `organization`.
    """
    maintenant = timezone.now()
    debut_fenetre = maintenant - FENETRE_PASSEE
    fin_fenetre = maintenant + FENETRE_FUTURE

    lignes = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//PsySaaS//Agenda//FR',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{_escape(organization.name)} — Agenda',
        'X-PUBLISHED-TTL:PT12H',
        'REFRESH-INTERVAL;VALUE=DURATION:PT12H',
    ]

    consultations = Consultation.objects.filter(
        date_seance__gte=debut_fenetre,
        date_seance__lte=fin_fenetre,
    ).exclude(statut_consultation='annule').select_related('patient')

    for c in consultations:
        debut = c.date_seance
        fin = debut + timezone.timedelta(minutes=c.duree_minutes or 60)
        description_parts = [
            f"Type : {c.get_type_consultation_display()}",
            f"Statut : {c.get_statut_consultation_display()}",
            f"Tarif : {c.tarif} DHS",
        ]
        lignes.extend(_vevent(
            uid=f'consultation-{c.id}@psysaas',
            dtstart=debut,
            dtend=fin,
            summary=f"{c.patient.nom_complet} — {c.get_type_consultation_display()}",
            description='\n'.join(description_parts),
            location=c.get_lieu_consultation_display(),
        ))

    indisponibilites = Indisponibilite.objects.filter(date_fin__gte=debut_fenetre)

    for i in indisponibilites:
        lignes.extend(_vevent(
            uid=f'indisponibilite-{i.id}@psysaas',
            dtstart=i.date_debut,
            dtend=i.date_fin,
            summary=f"🚫 {i.titre}",
            description=i.note,
        ))

    lignes.append('END:VCALENDAR')
    return '\r\n'.join(lignes) + '\r\n'
