from django.db import models
from core.models import TenantModel
from django.urls import reverse

class TestPsychometrique(TenantModel):
    """
    Modèle abstrait de base pour tous les tests psychométriques
    """
    patient = models.ForeignKey(
        'cabinet.Patient',
        on_delete=models.CASCADE,
        related_name='tests_%(class)s',
        verbose_name="Patient"
    )
    psychologue = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Psychologue"
    )
    date_passation = models.DateTimeField(auto_now_add=True, verbose_name="Date de passation")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    
    class Meta:
        abstract = True
        ordering = ['-date_passation']
    
    def __str__(self):
        return f"{self.__class__.__name__} - {self.patient.nom_complet} ({self.date_passation.strftime('%d/%m/%Y')})"
    
    def get_absolute_url(self):
        """À surcharger dans chaque modèle de test"""
        raise NotImplementedError("Chaque test doit définir get_absolute_url()")