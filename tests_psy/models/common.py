"""
Modèles communs pour les tests psychologiques (Domaines et Sous-domaines)
Ces modèles sont partagés entre différents tests (Vineland, etc.)
"""
from django.db import models


class Domain(models.Model):
    """Domaine d'évaluation (ex: Communication, Socialisation, etc.)"""
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom du domaine"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Domaine"
        verbose_name_plural = "Domaines"
        ordering = ['ordre', 'name']
    
    def __str__(self):
        return self.name


class SousDomain(models.Model):
    """Sous-domaine d'un domaine (ex: Réceptif, Expressif pour Communication)"""
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        related_name='sous_domaines',
        verbose_name="Domaine parent"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nom du sous-domaine"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Sous-domaine"
        verbose_name_plural = "Sous-domaines"
        ordering = ['domain', 'ordre', 'name']
        unique_together = ['domain', 'name']
    
    def __str__(self):
        return f"{self.domain.name} - {self.name}"