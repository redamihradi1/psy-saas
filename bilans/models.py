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
    # Informations de la page de garde et du contexte : date d'évaluation, latéralité,
    # établissement, classe/profession, adressé par, civilité, bilan antérieur, sous-titre...
    infos = models.JSONField(default=dict, blank=True)
    # Scores saisis des tests passés hors plateforme (WISC-V, TMT...) : {cle_test: saisie},
    # format décrit dans bilans/tests_externes.py
    scores = models.JSONField(default=dict, blank=True)
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
    TYPE_CHOICES = [('premier_jet', 'Première version'), ('chat', 'Chat'), ('relecture', 'Relecture')]

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


class EnTeteBilan(models.Model):
    """Papier à en-tête d'un psychologue pour l'export de ses bilans (Word et PDF) : bloc
    d'identité à gauche, logo au centre, texte libre à droite (ex. arabe, Word uniquement),
    pied de page, signature."""
    utilisateur = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='en_tete_bilan')
    nom_affiche = models.CharField("Nom affiché", max_length=120, blank=True)
    titre_pro = models.CharField("Titre", max_length=150, blank=True,
                                 help_text="Ex. Psychologue clinicienne - Psychothérapeute")
    specialites = models.CharField("Spécialités / public", max_length=150, blank=True,
                                   help_text="Ex. Enfants - Adolescents - Adultes")
    texte_droite = models.TextField("Texte à droite de l'en-tête", blank=True,
                                    help_text="Facultatif, une ligne par ligne (ex. votre nom en arabe). "
                                              "L'arabe s'affiche dans l'export Word uniquement.")
    pied_de_page = models.TextField("Pied de page", blank=True,
                                    help_text="Une ligne par ligne : diplômes, adresse, téléphone, email...")
    mention_confidentielle = models.CharField("Mention", max_length=120, blank=True,
                                              default="Document clinique confidentiel")
    formule_signature = models.CharField("Formule avant la signature", max_length=200, blank=True,
                                         default="Pour faire valoir ce que de droit.")
    logo = models.ImageField("Logo", upload_to='bilans/entetes/', blank=True)
    signature = models.ImageField("Signature ou cachet", upload_to='bilans/entetes/', blank=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "En-tête de bilan"
        verbose_name_plural = "En-têtes de bilan"

    def __str__(self):
        return f"En-tête de {self.utilisateur}"


class TexteType(TenantModel):
    """Texte réutilisable de la bibliothèque du cabinet (présentation d'un test, définition,
    recommandation...). `cle` renseignée = version personnalisée d'un texte fourni par la
    plateforme (bilans/textes_types.py), `masque` = texte fourni retiré de la bibliothèque."""
    CATEGORIE_CHOICES = [
        ('presentation', "Présentation des tests"),
        ('definition', "Définitions"),
        ('recommandation', "Recommandations"),
        ('mention', "Mentions et formules"),
        ('autre', "Mes textes"),
    ]

    cle = models.CharField(max_length=60, blank=True)
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, default='autre')
    titre = models.CharField(max_length=150)
    contenu = models.TextField(blank=True)
    masque = models.BooleanField(default=False)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Texte type"
        verbose_name_plural = "Textes types"
        ordering = ['categorie', 'titre']
