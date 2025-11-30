from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from threading import local

# Contexte local pour stocker le tenant actuel
_thread_locals = local()


def get_current_tenant():
    """Récupère l'organisation du contexte actuel"""
    return getattr(_thread_locals, 'tenant', None)


def set_current_tenant(tenant):
    """Définit l'organisation dans le contexte actuel"""
    _thread_locals.tenant = tenant


class TenantMiddleware:
    """
    Middleware qui attache l'organisation de l'utilisateur à chaque requête.
    Cela permet de filtrer automatiquement les données par organisation.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ajouter l'organisation au contexte de la requête
        if request.user.is_authenticated:
            # Si superadmin, pas de filtrage (voit tout)
            if request.user.is_superadmin():
                request.tenant = None
                set_current_tenant(None)
            else:
                # Pour les psychologues, filtrer par leur organisation
                request.tenant = request.user.organization
                set_current_tenant(request.tenant)
                
                # Vérifier si l'utilisateur a une organisation
                if not request.tenant:
                    # Rediriger vers une page d'erreur si pas d'organisation
                    if not request.path.startswith('/admin/') and not request.path.startswith('/accounts/'):
                        return HttpResponseForbidden("Vous n'êtes pas associé à une organisation.")
                
                # Vérifier si la licence est active
                if request.tenant:
                    try:
                        license = request.tenant.license
                        if not license.is_active():
                            if not request.path.startswith('/admin/') and not request.path.startswith('/accounts/'):
                                return HttpResponseForbidden("Votre licence a expiré.")
                    except Exception as e:
                        # Log l'erreur mais ne bloque pas l'accès si la licence n'existe pas
                        # (l'organisation pourrait ne pas encore avoir de licence)
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Erreur lors de la vérification de licence pour {request.tenant}: {e}")
        else:
            request.tenant = None
            set_current_tenant(None)

        response = self.get_response(request)
        
        # Nettoyer le contexte après la requête
        set_current_tenant(None)
        
        return response