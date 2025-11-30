from django.db import models
from django.urls import reverse
from .base import TestPsychometrique
from core.models import TenantModel


class ItemBeck(models.Model):
    """
    Un des 21 items du Beck Depression Inventory.
    Données de référence partagées entre toutes les organisations.
    """
    numero = models.IntegerField(unique=True, verbose_name="Numéro de l'item")
    categorie = models.CharField(
        max_length=100,
        verbose_name="Catégorie",
        help_text="Ex: Tristesse, Pessimisme, Échec, etc."
    )

    class Meta:
        verbose_name = "Item Beck"
        verbose_name_plural = "Items Beck"
        ordering = ['numero']

    def __str__(self):
        return f"Item {self.numero} - {self.categorie}"


class PhraseBeck(models.Model):
    """
    Une phrase/option dans un item du BDI.
    Données de référence partagées entre toutes les organisations.
    """
    item = models.ForeignKey(
        ItemBeck,
        on_delete=models.CASCADE,
        related_name='phrases',
        verbose_name="Item"
    )
    score_valeur = models.IntegerField(
        verbose_name="Score",
        help_text="Valeur du score (0, 1, 2 ou 3)"
    )
    texte = models.TextField(verbose_name="Texte de la phrase")
    ordre = models.IntegerField(
        default=0,
        verbose_name="Ordre d'affichage"
    )

    class Meta:
        verbose_name = "Phrase Beck"
        verbose_name_plural = "Phrases Beck"
        ordering = ['item__numero', 'ordre']
        unique_together = ['item', 'ordre']

    def __str__(self):
        return f"Item {self.item.numero} - Score {self.score_valeur}"


class TestBeck(TestPsychometrique):
    """Test de dépression de Beck pour un patient"""

    score_total = models.IntegerField(
        default=0,
        verbose_name="Score total",
        help_text="Score total sur 63 points"
    )
    niveau_depression = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Niveau de dépression"
    )
    alerte_suicide = models.BooleanField(
        default=False,
        verbose_name="Alerte idées suicidaires",
        help_text="True si l'item 9 a un score >= 2"
    )

    class Meta:
        verbose_name = "Test Beck"
        verbose_name_plural = "Tests Beck"
        ordering = ['-date_passation']

    def __str__(self):
        return f"Beck - {self.patient.nom_complet} - {self.date_passation.strftime('%d/%m/%Y')}"

    def get_absolute_url(self):
        return reverse('tests_psy:beck_resultats', kwargs={'test_id': self.id})

    def calculer_score_total(self):
        """Calcule le score total du test (somme des 21 items)"""
        total = sum(reponse.score_item for reponse in self.reponses.all())
        self.score_total = total
        self.niveau_depression = self.get_niveau_depression()
        self.verifier_alerte_suicide()
        self.save()
        return total

    def get_niveau_depression(self):
        """Retourne le niveau de dépression selon le score total"""
        if self.score_total <= 13:
            return 'minimale'
        elif self.score_total <= 19:
            return 'legere'
        elif self.score_total <= 28:
            return 'moderee'
        else:
            return 'severe'

    def get_niveau_depression_display(self):
        """Retourne le niveau de dépression formaté pour l'affichage"""
        niveaux = {
            'minimale': 'Dépression minimale ou absente',
            'legere': 'Dépression légère',
            'moderee': 'Dépression modérée',
            'severe': 'Dépression sévère'
        }
        return niveaux.get(self.niveau_depression, 'Non évalué')

    def verifier_alerte_suicide(self):
        """Vérifie si l'item 9 (idées suicidaires) a un score >= 2"""
        try:
            reponse_item_9 = self.reponses.get(item__numero=9)
            self.alerte_suicide = reponse_item_9.score_item >= 2
        except ReponseItemBeck.DoesNotExist:
            self.alerte_suicide = False

    @property
    def interpretation_score(self):
        """Retourne une interprétation détaillée du score"""
        interpretations = {
            'minimale': "Le score suggère une absence ou une présence minimale de symptômes dépressifs.",
            'legere': "Le score indique la présence de symptômes dépressifs légers. Un suivi est recommandé.",
            'moderee': "Le score suggère une dépression modérée. Une intervention thérapeutique est recommandée.",
            'severe': "Le score indique une dépression sévère. Une prise en charge thérapeutique immédiate est fortement recommandée."
        }
        return interpretations.get(self.niveau_depression, "")

    @property
    def score_pourcentage(self):
        """Retourne le score en pourcentage (sur 63)"""
        return round((self.score_total / 63) * 100, 1)


class ReponseItemBeck(TenantModel):
    """Réponse d'un patient à un item spécifique du BDI"""

    test = models.ForeignKey(
        TestBeck,
        on_delete=models.CASCADE,
        related_name='reponses',
        verbose_name="Test"
    )
    item = models.ForeignKey(
        ItemBeck,
        on_delete=models.CASCADE,
        verbose_name="Item"
    )
    phrases_cochees = models.ManyToManyField(
        PhraseBeck,
        verbose_name="Phrases cochées",
        help_text="Le patient peut cocher plusieurs phrases"
    )
    score_item = models.IntegerField(
        default=0,
        verbose_name="Score de l'item",
        help_text="Score maximum des phrases cochées"
    )

    class Meta:
        verbose_name = "Réponse Item Beck"
        verbose_name_plural = "Réponses Items Beck"
        unique_together = ['test', 'item']
        ordering = ['item__numero']

    def __str__(self):
        return f"Test {self.test.id} - Item {self.item.numero} - Score {self.score_item}"

    def calculer_score(self):
        """Calcule le score de l'item = MAX des scores des phrases cochées"""
        phrases = self.phrases_cochees.all()
        if not phrases.exists():
            self.score_item = 0
        else:
            self.score_item = max(phrase.score_valeur for phrase in phrases)
        self.save()
        return self.score_item
