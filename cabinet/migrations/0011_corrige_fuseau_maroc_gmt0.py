"""
Recale d'une heure les dates saisies avec l'ancienne règle horaire du Maroc.

Depuis le 2026-09-20, le Maroc est en GMT+0 permanent (IANA 2026c). Tant que le serveur
utilisait une base de fuseaux plus ancienne (tzdata 2025.2), une séance saisie « 10:00 »
pour une date postérieure au 20/09 était interprétée en GMT+1 et stockée 09:00 UTC au lieu
de 10:00 UTC : agenda, flux .ics et rappels push décalés d'une heure.

On décale de +1h toutes les valeurs stockées après le basculement, sauf dans les périodes
de Ramadan où l'ancienne règle était déjà en GMT+0 (valeurs alors stockées correctement).
Ne s'exécute qu'une fois par base (migration) et refuse de tourner si le serveur n'a pas
encore la nouvelle règle (sinon on décalerait les données sans corriger leur lecture).
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db import migrations
from django.db.models import F, Q

UTC = dt_timezone.utc
DEBUT_GMT0 = datetime(2026, 9, 20, 1, 0, tzinfo=UTC)
# Au-delà, aucune séance n'est raisonnablement planifiée.
FIN_CORRECTION = datetime(2031, 12, 14, 2, 0, tzinfo=UTC)
# Périodes où l'ancienne règle (tzdata 2025.2) était déjà en GMT+0 : rien à corriger.
ANCIENNES_PERIODES_GMT0 = [
    (datetime(2027, 2, 7, 2, 0, tzinfo=UTC), datetime(2027, 3, 14, 2, 0, tzinfo=UTC)),
    (datetime(2028, 1, 23, 2, 0, tzinfo=UTC), datetime(2028, 3, 5, 2, 0, tzinfo=UTC)),
    (datetime(2029, 1, 14, 2, 0, tzinfo=UTC), datetime(2029, 2, 18, 2, 0, tzinfo=UTC)),
    (datetime(2029, 12, 30, 2, 0, tzinfo=UTC), datetime(2030, 2, 10, 2, 0, tzinfo=UTC)),
    (datetime(2030, 12, 22, 2, 0, tzinfo=UTC), datetime(2031, 1, 26, 2, 0, tzinfo=UTC)),
]

CHAMPS = [
    ('Consultation', 'date_seance'),
    ('Consultation', 'date_seance_originale'),
    ('Indisponibilite', 'date_debut'),
    ('Indisponibilite', 'date_fin'),
]


def a_corriger(champ, decalage=timedelta(0)):
    """Filtre des valeurs stockées avec l'ancienne règle GMT+1 (bornes décalées pour le retour arrière)."""
    q = Q(**{f'{champ}__gte': DEBUT_GMT0 + decalage, f'{champ}__lt': FIN_CORRECTION + decalage})
    for debut, fin in ANCIENNES_PERIODES_GMT0:
        q &= ~Q(**{f'{champ}__gte': debut + decalage, f'{champ}__lt': fin + decalage})
    return q


def verifier_nouvelle_regle():
    offset = datetime(2026, 10, 14, 12, 0, tzinfo=ZoneInfo('Africa/Casablanca')).utcoffset()
    if offset != timedelta(0):
        raise RuntimeError(
            "La base de fuseaux du serveur ignore encore le passage du Maroc en GMT+0 "
            f"(Africa/Casablanca = UTC{offset}). Faire `pip install -r requirements.txt` "
            "(tzdata >= 2026.3) avant `migrate`."
        )


def decaler(apps, sens):
    heure = timedelta(hours=sens)
    for modele, champ in CHAMPS:
        Model = apps.get_model('cabinet', modele)
        decalage = timedelta(0) if sens > 0 else timedelta(hours=1)
        Model._base_manager.filter(a_corriger(champ, decalage)).update(**{champ: F(champ) + heure})


def appliquer(apps, schema_editor):
    verifier_nouvelle_regle()
    decaler(apps, +1)


def annuler(apps, schema_editor):
    decaler(apps, -1)


class Migration(migrations.Migration):

    dependencies = [
        ('cabinet', '0010_pushsubscription_rappelenvoye'),
    ]

    operations = [
        migrations.RunPython(appliquer, annuler),
    ]
