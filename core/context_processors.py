from django.conf import settings


def vapid_public_key(request):
    """Expose la clé publique VAPID aux templates (nécessaire côté JS pour l'abonnement push)."""
    return {'VAPID_PUBLIC_KEY': settings.VAPID_PUBLIC_KEY}
