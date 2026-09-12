import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import PushSubscription
from ..push_utils import envoyer_rappels_consultations_proches


@login_required
@require_POST
def push_subscribe(request):
    """Enregistre (ou met à jour) un abonnement push pour l'utilisateur connecté."""
    try:
        payload = json.loads(request.body)
        endpoint = payload['endpoint']
        keys = payload['keys']
        p256dh = keys['p256dh']
        auth = keys['auth']
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Payload invalide'}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
        },
    )
    return JsonResponse({'success': True})


@login_required
@require_POST
def push_unsubscribe(request):
    """Supprime un abonnement push (l'utilisateur a désactivé les notifications sur cet appareil)."""
    try:
        payload = json.loads(request.body)
        endpoint = payload['endpoint']
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Payload invalide'}, status=400)

    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'success': True})


@csrf_exempt
def push_cron_trigger(request, token):
    """Déclencheur HTTP pour l'envoi des rappels — pensé pour un cron externe
    (PythonAnywhere gratuit ne permet qu'1 tâche planifiée par jour, trop peu
    fréquent pour un rappel '1h avant'). Protégé par un jeton secret en env
    (CRON_SECRET_TOKEN), pas par login puisqu'appelé par un service externe.
    """
    if not settings.CRON_SECRET_TOKEN or token != settings.CRON_SECRET_TOKEN:
        return HttpResponseForbidden("Jeton invalide.")

    nb = envoyer_rappels_consultations_proches()
    return JsonResponse({'success': True, 'rappels_envoyes': nb})
