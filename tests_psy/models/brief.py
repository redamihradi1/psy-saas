"""
BRIEF (Behavior Rating Inventory of Executive Function) - Forme Parent.

Le contenu protégé par le droit d'auteur (texte des 86 items, répartition item -> échelle,
items de Négativité, paires d'Incohérence, tables d'étalonnage) n'est JAMAIS versionné : il
est chargé en base depuis des fichiers JSON ignorés par git, via
`python manage.py import_brief` (voir tests_psy/data/brief/README.md). Le code ci-dessous
ne contient que la structure générique (noms des échelles, composition des indices).
"""
import secrets
from datetime import timedelta

from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TenantModel


FORME_CHOICES = [
    ('parent', 'Forme Parent'),
]

SEXE_CHOICES = [
    ('M', 'Garçon'),
    ('F', 'Fille'),
]

# Les 8 échelles cliniques, dans l'ordre de la feuille de profil du manuel.
ECHELLE_CHOICES = [
    ('inhibition', 'Inhibition'),
    ('flexibilite', 'Flexibilité'),
    ('controle_emotionnel', 'Contrôle émotionnel'),
    ('initiation', 'Initiation'),
    ('memoire_travail', 'Mémoire de travail'),
    ('planification', 'Planification/Organisation'),
    ('organisation_materiel', 'Organisation du matériel'),
    ('controle', 'Contrôle'),
]

# Indices composites (scores bruts = somme des scores bruts des échelles qui les composent).
INDICE_CHOICES = [
    ('irc', 'Indice de Régulation Comportementale (IRC)'),
    ('im', 'Indice de Métacognition (IM)'),
    ('ceg', 'Composite Exécutif Global (CEG)'),
]

REPONSE_CHOICES = [
    ('J', 'Jamais'),
    ('P', 'Parfois'),
    ('S', 'Souvent'),
]
VALEUR_REPONSE = {'J': 1, 'P': 2, 'S': 3}


class ItemBRIEF(models.Model):
    """Un des 86 items du questionnaire - données de référence partagées entre les cabinets.

    `echelle` est vide pour les items 73 à 86 de la Forme Parent : ils ne comptent dans
    aucun score brut d'échelle (analyse d'items / Négativité uniquement)."""
    forme = models.CharField(max_length=10, choices=FORME_CHOICES, default='parent')
    numero = models.PositiveIntegerField(verbose_name="Numéro de l'item")
    texte = models.TextField(verbose_name="Texte de l'item")
    echelle = models.CharField(
        max_length=30, choices=ECHELLE_CHOICES, blank=True,
        verbose_name="Échelle clinique",
        help_text="Vide = item non compté dans les scores bruts d'échelle.",
    )
    est_negativite = models.BooleanField(default=False, verbose_name="Item de l'échelle de Négativité")

    class Meta:
        verbose_name = "Item BRIEF"
        verbose_name_plural = "Items BRIEF"
        ordering = ['forme', 'numero']
        unique_together = ['forme', 'numero']

    def __str__(self):
        return f"BRIEF {self.forme} - Item {self.numero}"


class PaireIncoherenceBRIEF(models.Model):
    """Paire d'items de l'échelle d'Incohérence (différence absolue des deux réponses)."""
    forme = models.CharField(max_length=10, choices=FORME_CHOICES, default='parent')
    item_a = models.PositiveIntegerField(verbose_name="Numéro du 1er item")
    item_b = models.PositiveIntegerField(verbose_name="Numéro du 2e item")

    class Meta:
        verbose_name = "Paire d'Incohérence BRIEF"
        verbose_name_plural = "Paires d'Incohérence BRIEF"
        ordering = ['forme', 'id']
        unique_together = ['forme', 'item_a', 'item_b']

    def __str__(self):
        return f"BRIEF {self.forme} - Items {self.item_a}/{self.item_b}"


class NormeBRIEF(models.Model):
    """Une ligne des tables d'étalonnage (Annexes du manuel) : score brut -> score T,
    percentile et valeur de l'intervalle de confiance à 90 %, pour un sexe, une tranche
    d'âge et une échelle/un indice donnés."""
    forme = models.CharField(max_length=10, choices=FORME_CHOICES, default='parent')
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    age_min = models.PositiveIntegerField(verbose_name="Âge minimum (ans, inclus)")
    age_max = models.PositiveIntegerField(verbose_name="Âge maximum (ans, inclus)")
    echelle = models.CharField(max_length=30, choices=ECHELLE_CHOICES + INDICE_CHOICES)
    score_brut = models.PositiveIntegerField()
    score_t = models.PositiveIntegerField()
    percentile = models.PositiveIntegerField(null=True, blank=True)
    ic90 = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Valeur IC 90 %",
        help_text="À ajouter/soustraire au score T pour obtenir l'intervalle de confiance.",
    )

    class Meta:
        verbose_name = "Norme BRIEF"
        verbose_name_plural = "Normes BRIEF"
        ordering = ['forme', 'sexe', 'age_min', 'echelle', 'score_brut']
        unique_together = ['forme', 'sexe', 'age_min', 'age_max', 'echelle', 'score_brut']

    def __str__(self):
        return f"BRIEF {self.sexe} {self.age_min}-{self.age_max} {self.echelle} {self.score_brut} -> T{self.score_t}"


class TestBRIEF(TenantModel):
    """Passation BRIEF pour un patient - MULTI-TENANT. Mêmes 3 modes que Vineland."""

    MODE_CHOICES = [
        ('cabinet', 'Passation en cabinet'),
        ('importe', 'Notes importées'),
        ('lien_public', 'Lien envoyé aux parents'),
    ]

    patient = models.ForeignKey(
        'cabinet.Patient', on_delete=models.CASCADE,
        related_name='tests_brief', verbose_name="Patient",
    )
    psychologue = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tests_brief_administres', verbose_name="Psychologue",
    )
    forme = models.CharField(max_length=10, choices=FORME_CHOICES, default='parent')
    # Le modèle Patient n'a pas de sexe : il est demandé à la création du test, comme pour
    # D2R, car les tables d'étalonnage BRIEF sont distinctes pour les garçons et les filles.
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, verbose_name="Sexe de l'enfant")
    repondant = models.CharField(
        max_length=50, blank=True,
        verbose_name="Lien de parenté du répondant",
        help_text="Ex : Mère, Père, Tuteur.",
    )
    date_passation = models.DateTimeField(default=timezone.now, verbose_name="Date de passation")
    notes = models.TextField(blank=True, verbose_name="Notes du psychologue")
    mode = models.CharField(max_length=15, choices=MODE_CHOICES, default='cabinet', verbose_name="Mode de passation")
    termine_le = models.DateTimeField(
        null=True, blank=True, verbose_name="Terminé le",
        help_text="Les réponses manquantes étant tolérées par le manuel, la fin de passation est explicite.",
    )

    # Lien public (mode='lien_public') - même mécanique que TestVineland.
    lien_token = models.CharField(max_length=43, unique=True, null=True, blank=True, verbose_name="Jeton du lien public")
    lien_expire_le = models.DateTimeField(null=True, blank=True, verbose_name="Expiration du lien")
    lien_soumis_le = models.DateTimeField(
        null=True, blank=True, verbose_name="Soumis par le parent le",
        help_text="Non vide = lien verrouillé (le parent ne peut plus modifier).",
    )
    lien_duree_jours = models.PositiveIntegerField(null=True, blank=True, verbose_name="Durée choisie du lien (jours)")

    # Mode 'importe' : les échelles de validité ne peuvent pas être recalculées sans les
    # réponses item par item, le psy peut donc saisir les scores déjà cotés sur papier.
    negativite_importee = models.PositiveIntegerField(null=True, blank=True, verbose_name="Score de Négativité (saisi)")
    incoherence_importee = models.PositiveIntegerField(null=True, blank=True, verbose_name="Score d'Incohérence (saisi)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Test BRIEF"
        verbose_name_plural = "Tests BRIEF"
        ordering = ['-date_passation']

    def __str__(self):
        return f"BRIEF - {self.patient.nom_complet} - {self.date_passation.strftime('%d/%m/%Y')}"

    def get_absolute_url(self):
        return reverse('tests_psy:brief_resultats', kwargs={'test_id': self.id})

    @property
    def is_complete(self):
        if self.mode == 'importe':
            return self.notes_brutes_importees.count() >= len(ECHELLE_CHOICES)
        if self.mode == 'lien_public':
            return self.lien_soumis_le is not None
        return self.termine_le is not None

    def generate_lien_public(self, duree_jours):
        """Passe le test en mode lien public et (re)génère son jeton secret."""
        self.mode = 'lien_public'
        self.lien_token = secrets.token_urlsafe(24)
        self.lien_duree_jours = duree_jours
        self.lien_expire_le = timezone.now() + timedelta(days=duree_jours)
        self.lien_soumis_le = None
        self.save()

    def reouvrir_lien(self):
        """Déverrouille un lien déjà soumis (ou expiré) - le jeton reste le même."""
        self.lien_soumis_le = None
        self.termine_le = None
        self.lien_expire_le = timezone.now() + timedelta(days=self.lien_duree_jours or 7)
        self.save()


class ReponseBRIEF(TenantModel):
    """Réponse à un item : la réponse textuelle (J/P/S) ET sa valeur numérique (1/2/3)."""
    test = models.ForeignKey(TestBRIEF, on_delete=models.CASCADE, related_name='reponses', verbose_name="Test")
    item = models.ForeignKey(ItemBRIEF, on_delete=models.CASCADE, verbose_name="Item")
    reponse = models.CharField(max_length=1, choices=REPONSE_CHOICES)
    valeur = models.PositiveSmallIntegerField(verbose_name="Valeur numérique")

    class Meta:
        verbose_name = "Réponse BRIEF"
        verbose_name_plural = "Réponses BRIEF"
        unique_together = ['test', 'item']
        ordering = ['item__numero']

    def __str__(self):
        return f"Test {self.test_id} - Item {self.item.numero} - {self.reponse}"

    def save(self, *args, **kwargs):
        self.valeur = VALEUR_REPONSE[self.reponse]
        # update_or_create ne sauvegarde que les champs de `defaults` : sans ceci, changer
        # une réponse (J -> P) laisserait l'ancienne valeur numérique en base.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'reponse' in update_fields:
            kwargs['update_fields'] = {*update_fields, 'valeur'}
        super().save(*args, **kwargs)


class NoteBruteImporteeBRIEF(TenantModel):
    """Score brut d'échelle saisi directement (mode='importe'), déjà coté sur papier."""
    test = models.ForeignKey(
        TestBRIEF, on_delete=models.CASCADE,
        related_name='notes_brutes_importees', verbose_name="Test",
    )
    echelle = models.CharField(max_length=30, choices=ECHELLE_CHOICES)
    note_brute = models.PositiveIntegerField(verbose_name="Score brut")

    class Meta:
        verbose_name = "Score brut importé BRIEF"
        verbose_name_plural = "Scores bruts importés BRIEF"
        unique_together = ['test', 'echelle']

    def __str__(self):
        return f"Test {self.test_id} - {self.echelle} = {self.note_brute}"
