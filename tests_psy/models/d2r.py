from django.db import models
from django.urls import reverse
from .base import TestPsychometrique
from core.models import TenantModel

class TestD2R(TestPsychometrique):
    """Test d'attention D2R"""
    
    # Informations participant
    code = models.CharField(max_length=50, verbose_name="Code du test")
    date = models.DateField(verbose_name="Date")
    age = models.IntegerField(verbose_name="Âge")
    sexe = models.CharField(
        max_length=1, 
        choices=[('M', 'Masculin'), ('F', 'Féminin')],
        verbose_name="Sexe"
    )
    type_ecole = models.CharField(max_length=100, null=True, blank=True, verbose_name="Type d'école")
    etudes = models.CharField(max_length=100, null=True, blank=True, verbose_name="Études")
    profession = models.CharField(max_length=100, null=True, blank=True, verbose_name="Profession")
    correction_vue = models.CharField(
        max_length=2,
        choices=[
            ('OP', 'Oui portées'), 
            ('ON', 'Oui non portées'), 
            ('NO', 'Non')
        ],
        verbose_name="Correction de la vue"
    )
    lateralite = models.CharField(
        max_length=1, 
        choices=[('D', 'Droitier'), ('G', 'Gaucher')],
        verbose_name="Latéralité"
    )
    
    # Résultats
    reponses_correctes = models.IntegerField(default=0, verbose_name="Réponses correctes")
    reponses_incorrectes = models.IntegerField(default=0, verbose_name="Réponses incorrectes")
    reponses_omises = models.IntegerField(default=0, null=True, blank=True, verbose_name="Réponses omises")
    
    # Scores
    note_cct = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Note CCT"
    )
    note_exactitude = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Note exactitude"
    )
    capacite_concentration = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Capacité de concentration"
    )
    temps_total = models.IntegerField(default=0, verbose_name="Temps total (secondes)")
    
    class Meta:
        verbose_name = "Test D2R"
        verbose_name_plural = "Tests D2R"
        ordering = ['-date_passation']
    
    def __str__(self):
        return f"D2R - {self.patient.nom_complet} - {self.code}"
    
    def get_absolute_url(self):
        return reverse('tests_psy:d2r_resultats', kwargs={'test_id': self.id})
    
    @property
    def cct(self):
        """Caractère ciblé traité"""
        return self.reponses_correctes
    
    @property
    def ec(self):
        """Erreurs de commission"""
        return self.reponses_incorrectes
    
    @property
    def eo(self):
        """Erreurs d'omission"""
        return self.reponses_omises or 0
    
    @property
    def cc(self):
        """Capacité de concentration"""
        return self.cct - self.ec - self.eo
    
    @property
    def e_percentage(self):
        """Pourcentage d'erreur"""
        if self.cct > 0:
            return ((self.eo + self.ec) / self.cct) * 100
        return 0


class SymboleReference(models.Model):
    """Symboles de référence pour le test D2R - Configuration globale partagée"""
    LETTRE_CHOICES = [('d', 'd'), ('p', 'p')]
    BACKGROUND_CHOICES = [('W', 'White'), ('G', 'Grey'), ('N', 'None')]

    page = models.IntegerField(verbose_name="Page")
    ligne = models.IntegerField(verbose_name="Ligne")
    position = models.IntegerField(editable=False, verbose_name="Position")
    lettre = models.CharField(max_length=1, choices=LETTRE_CHOICES, verbose_name="Lettre")
    traits_haut = models.IntegerField(
        choices=[(0, '0'), (1, '1'), (2, '2')],
        verbose_name="Traits en haut"
    )
    traits_bas = models.IntegerField(
        choices=[(0, '0'), (1, '1'), (2, '2')],
        verbose_name="Traits en bas"
    )
    background = models.CharField(
        max_length=1, 
        choices=BACKGROUND_CHOICES,
        default='N',
        verbose_name="Background"
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            last_position = (
                SymboleReference.objects.filter(
                    page=self.page, 
                    ligne=self.ligne
                ).order_by('-position').first()
            )
            self.position = (last_position.position + 1) if last_position else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Symbole {self.lettre} (P{self.page}-L{self.ligne}-Pos{self.position})"

    class Meta:
        verbose_name = "Symbole de référence"
        verbose_name_plural = "Symboles de référence"
        unique_together = ['page', 'ligne', 'position']  # ← SANS 'organization'
        ordering = ['page', 'ligne', 'position']

class NormeExactitude(models.Model):
    """Normes d'exactitude pour le test D2R"""
    note_standard = models.IntegerField(verbose_name="Note standard")
    percentile = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Percentile")
    age_min = models.IntegerField(verbose_name="Âge minimum")
    age_max = models.IntegerField(verbose_name="Âge maximum")
    valeur_min = models.IntegerField(verbose_name="Valeur minimum")
    valeur_max = models.IntegerField(verbose_name="Valeur maximum")

    class Meta:
        verbose_name = "Norme d'exactitude"
        verbose_name_plural = "Normes d'exactitude"
        ordering = ['note_standard', 'percentile', 'age_min']
    
    def __str__(self):
        return f"NS:{self.note_standard} P:{self.percentile} Age:{self.age_min}-{self.age_max}"


class NormeRythmeTraitement(models.Model):
    """Normes de rythme de traitement pour le test D2R"""
    note_standard = models.IntegerField(verbose_name="Note standard")
    percentile = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Percentile")
    age_min = models.IntegerField(verbose_name="Âge minimum")
    age_max = models.IntegerField(verbose_name="Âge maximum")
    valeur_min = models.IntegerField(verbose_name="Valeur minimum")
    valeur_max = models.IntegerField(verbose_name="Valeur maximum")

    class Meta:
        verbose_name = "Norme de rythme de traitement"
        verbose_name_plural = "Normes de rythme de traitement"
        ordering = ['note_standard', 'percentile', 'age_min']

    def __str__(self):
        return f"NS:{self.note_standard} P:{self.percentile} Age:{self.age_min}-{self.age_max}"


class NormeCapaciteConcentration(models.Model):
    """Normes de capacité de concentration pour le test D2R"""
    note_standard = models.IntegerField(verbose_name="Note standard")
    percentile = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Percentile")
    age_min = models.IntegerField(verbose_name="Âge minimum")
    age_max = models.IntegerField(verbose_name="Âge maximum")
    valeur_min = models.IntegerField(verbose_name="Valeur minimum")
    valeur_max = models.IntegerField(verbose_name="Valeur maximum")

    class Meta:
        verbose_name = "Norme de capacité de concentration"
        verbose_name_plural = "Normes de capacité de concentration"
        ordering = ['note_standard', 'percentile', 'age_min']

    def __str__(self):
        return f"NS:{self.note_standard} P:{self.percentile} Age:{self.age_min}-{self.age_max}"