from django.db import models

from core.models import TenantModel

from .modeles import MODELE_CHOICES


class Bilan(TenantModel):
    """Rapport de bilan rédigé par le psychologue pour un patient, à partir d'un modèle
    (bilans/modeles.py). Le contenu est du HTML nettoyé (bilans/html_blocs.py), découpé en
    sections <h2 data-section=...> ; les tableaux de résultats sont figés à la création
    (le psychologue peut ensuite tout modifier)."""

    STATUT_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('finalise', 'Finalisé'),
    ]

    patient = models.ForeignKey('cabinet.Patient', on_delete=models.CASCADE, related_name='bilans')
    psychologue = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='bilans_rediges',
    )
    modele = models.CharField(max_length=40, choices=MODELE_CHOICES)
    titre = models.CharField(max_length=200)
    contenu = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='brouillon')
    # Données choisies à la création pour remplir le bilan et alimenter l'IA :
    # {'anamnese': bool, 'consultations': bool, 'tests': ['brief:3', 'beck:7', ...]}
    sources = models.JSONField(default=dict, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bilan"
        verbose_name_plural = "Bilans"
        ordering = ['-date_modification']
        indexes = [models.Index(fields=['organization', 'patient'])]

    def __str__(self):
        return f"{self.titre} - {self.patient.nom_complet}"

    @property
    def est_finalise(self):
        return self.statut == 'finalise'


class VersionBilan(models.Model):
    """Instantané du contenu, pour revenir en arrière (avant chaque intervention de l'IA,
    à la finalisation, à la restauration, et au plus toutes les 10 min pendant l'édition)."""
    bilan = models.ForeignKey(Bilan, on_delete=models.CASCADE, related_name='versions')
    contenu = models.TextField()
    motif = models.CharField(max_length=100)
    auteur = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.bilan} - {self.motif} ({self.date:%d/%m/%Y %H:%M})"


class MessageBilan(models.Model):
    """Historique du chat IA d'un bilan (vrais noms restaurés : c'est ce que voit le psy)."""
    ROLE_CHOICES = [('psy', 'Psychologue'), ('ia', 'Assistant IA')]

    bilan = models.ForeignKey(Bilan, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    contenu = models.TextField()
    selection = models.TextField(blank=True)
    proposition = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'id']


class AppelIA(TenantModel):
    """Journal des appels au fournisseur d'IA : quota quotidien par cabinet (clé API gratuite
    partagée par toute la plateforme) et suivi d'usage."""
    TYPE_CHOICES = [('premier_jet', 'Première version'), ('chat', 'Chat')]

    utilisateur = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    bilan = models.ForeignKey(Bilan, on_delete=models.SET_NULL, null=True, blank=True)
    type_appel = models.CharField(max_length=20, choices=TYPE_CHOICES)
    succes = models.BooleanField(default=False)
    tokens = models.IntegerField(null=True, blank=True)
    erreur = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Appel IA"
        verbose_name_plural = "Appels IA"
        ordering = ['-date']
