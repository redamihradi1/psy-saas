from django import template

register = template.Library()


@register.filter
def attr(obj, field_name):
    """Récupère dynamiquement un attribut par son nom (utilisé pour afficher les booléens de permission)."""
    return getattr(obj, field_name, None)


@register.filter
def has_module(user, module_name):
    """Le psychologue (titulaire) a toujours accès ; un(e) assistant(e) dépend de can_access_<module>.

    La sidebar de base.html rend cette liste même pour un visiteur anonyme (page d'accueil
    publique) : on renvoie False plutôt que de planter sur AnonymousUser.
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    return user.has_module_access(module_name)


@register.filter
def has_test(user, test_name):
    """Idem has_module, pour les tests psychométriques (indépendant du flag de licence de l'org)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return user.has_test_permission(test_name)
