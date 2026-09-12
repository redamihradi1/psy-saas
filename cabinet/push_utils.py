"""Envoi des rappels de consultation par notification push (Web Push API)."""
import json
import logging

from django.conf import settings
from django.utils import timezone
from pywebpush import webpush, WebPushException

from .models import Consultation, PushSubscription, RappelEnvoye

logger = logging.getLogger(__name__)

# Fenêtre de détection : on cherche les consultations qui commencent dans
# 55 à 65 minutes. Marge nécessaire car le déclencheur externe (cron) ne
# tourne pas forcément pile à la minute.
DELTA_MIN = timezone.timedelta(minutes=55)
DELTA_MAX = timezone.timedelta(minutes=65)


def _envoyer_a_abonnement(subscription, titre, corps, url='/cabinet/agenda/'):
    payload = json.dumps({'title': titre, 'body': corps, 'url': url})
    try:
        webpush(
            subscription_info=subscription.as_subscription_info(),
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': f'mailto:{settings.VAPID_ADMIN_EMAIL}'},
        )
        return True
    except WebPushException as exc:
        status_code = getattr(exc.response, 'status_code', None)
        if status_code in (404, 410):
            # Abonnement expiré ou révoqué côté navigateur : on le supprime.
            subscription.delete()
        else:
            logger.warning("Échec envoi push à %s : %s", subscription.user, exc)
        return False
    except Exception:
        # Ne jamais laisser un abonnement cassé (endpoint injoignable, etc.)
        # interrompre l'envoi des rappels aux autres abonnements/consultations.
        logger.exception("Erreur inattendue en envoyant un push à %s", subscription.user)
        return False


def envoyer_rappels_consultations_proches():
    """Envoie un rappel push pour chaque consultation démarrant dans ~1h.

    Idempotent : une consultation ne reçoit qu'un seul rappel '1h_avant'
    (verrouillé par RappelEnvoye). Sûr à appeler plusieurs fois de suite.
    """
    if not settings.VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY absente : notifications push désactivées.")
        return 0

    maintenant = timezone.now()
    consultations = Consultation.all_objects.filter(
        date_seance__gte=maintenant + DELTA_MIN,
        date_seance__lte=maintenant + DELTA_MAX,
    ).exclude(statut_consultation='annule').select_related('patient', 'organization')

    envoyes = 0
    for consultation in consultations:
        if RappelEnvoye.objects.filter(consultation=consultation, type_rappel='1h_avant').exists():
            continue

        abonnements = PushSubscription.objects.filter(user__organization=consultation.organization)
        if not abonnements.exists():
            continue

        titre = "Consultation dans 1h"
        corps = f"{consultation.patient.nom_complet} à {timezone.localtime(consultation.date_seance).strftime('%H:%M')}"

        au_moins_un_envoi_reussi = False
        for abonnement in abonnements:
            if _envoyer_a_abonnement(abonnement, titre, corps):
                au_moins_un_envoi_reussi = True

        if au_moins_un_envoi_reussi:
            RappelEnvoye.objects.get_or_create(consultation=consultation, type_rappel='1h_avant')
            envoyes += 1

    return envoyes
