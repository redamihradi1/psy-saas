from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def require_test_access(test_name):
    """
    Décorateur pour vérifier l'accès à un test spécifique.
    
    Usage:
        @require_test_access('d2r')
        def ma_vue(request):
            ...
    
    Args:
        test_name (str): Nom du test ('d2r', 'vineland', 'pep3')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Vérifier que l'utilisateur est authentifié
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            # Vérifier que l'utilisateur a une organisation
            if not hasattr(request.user, 'organization') or not request.user.organization:
                messages.error(request, "Vous n'êtes pas associé à une organisation.")
                return redirect('cabinet:dashboard')
            
            # Vérifier que l'organisation a une licence
            if not hasattr(request.user.organization, 'license'):
                messages.error(request, "Votre organisation n'a pas de licence active.")
                return redirect('cabinet:dashboard')
            
            license = request.user.organization.license
            
            # Vérifier l'accès au test
            if not license.has_test_access(test_name):
                # Redirection silencieuse vers le dashboard sans message
                return redirect('cabinet:dashboard')
            
            # Accès autorisé, exécuter la vue
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def superadmin_required(view_func):
    """
    Décorateur pour restreindre l'accès aux super admins uniquement.
    
    Usage:
        @superadmin_required
        def admin_dashboard(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not request.user.is_superadmin():
            messages.error(request, "Accès réservé aux super administrateurs.")
            return redirect('cabinet:dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper