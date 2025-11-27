from django.db import models


class TenantManager(models.Manager):
    """
    Manager personnalisé qui filtre automatiquement par organisation.
    À utiliser dans tous les modèles qui doivent être filtrés par tenant.
    """

    def get_queryset(self):
        from core.middleware import get_current_tenant

        # Récupérer le tenant depuis le contexte local du thread
        queryset = super().get_queryset()

        # Si on a un tenant actif, filtrer par organisation
        tenant = get_current_tenant()

        if tenant:
            return queryset.filter(organization=tenant)

        return queryset


class TenantModel(models.Model):
    """
    Modèle abstrait de base pour tous les modèles multi-tenant.
    Ajoute automatiquement le champ organization et le filtrage.
    """
    
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        verbose_name="Organisation"
    )
    
    # Manager par défaut (filtre par tenant)
    objects = TenantManager()
    
    # Manager pour les superadmins (voit tout)
    all_objects = models.Manager()
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        # Auto-assigner l'organisation si elle n'est pas définie
        if not self.organization_id:
            from core.middleware import get_current_tenant
            tenant = get_current_tenant()
            if tenant:
                self.organization = tenant

        super().save(*args, **kwargs)