from django.db import models

from django.urls import reverse

from .base import TestPsychometrique

from core.models import TenantModel

 

 

class ItemSTAI(models.Model):

    """

    Un des 40 items du STAI (State-Trait Anxiety Inventory).

    Données de référence partagées entre toutes les organisations.

    """

    SECTION_CHOICES = [

        ('ETAT', 'État (Y1)'),

        ('TRAIT', 'Trait (Y2)')

    ]

 

    numero = models.IntegerField(unique=True, verbose_name="Numéro de l'item")

    texte = models.TextField(verbose_name="Texte de l'item")

    section = models.CharField(

        max_length=10,

        choices=SECTION_CHOICES,

        verbose_name="Section",

        help_text="ÉTAT (situationnel) ou TRAIT (habituel)"

    )

    est_inverse = models.BooleanField(

        default=False,

        verbose_name="Item inversé",

        help_text="Si True, le score est inversé (1→4, 2→3, 3→2, 4→1)"

    )

 

    class Meta:

        verbose_name = "Item STAI"

        verbose_name_plural = "Items STAI"

        ordering = ['numero']

 

    def __str__(self):

        return f"Item {self.numero} ({self.section}) - {self.texte[:50]}"

 

 

class TestSTAI(TestPsychometrique):

    """Test d'anxiété STAI de Spielberger pour un patient"""

 

    score_etat = models.IntegerField(

        default=0,

        verbose_name="Score ÉTAT (Y1)",

        help_text="Score anxiété situationnelle (20-80)"

    )

    score_trait = models.IntegerField(

        default=0,

        verbose_name="Score TRAIT (Y2)",

        help_text="Score anxiété générale (20-80)"

    )

    niveau_anxiete_etat = models.CharField(

        max_length=20,

        blank=True,

        verbose_name="Niveau anxiété ÉTAT"

    )

    niveau_anxiete_trait = models.CharField(

        max_length=20,

        blank=True,

        verbose_name="Niveau anxiété TRAIT"

    )

 

    class Meta:

        verbose_name = "Test STAI"

        verbose_name_plural = "Tests STAI"

        ordering = ['-date_passation']

 

    def __str__(self):

        return f"STAI - {self.patient.nom_complet} - {self.date_passation.strftime('%d/%m/%Y')}"

 

    def get_absolute_url(self):

        return reverse('tests_psy:stai_resultats', kwargs={'test_id': self.id})

 

    def calculer_scores(self):

        """Calcule les scores ÉTAT et TRAIT séparément"""

        # Score ÉTAT (items 1-20)

        reponses_etat = self.reponses.filter(item__section='ETAT')

        self.score_etat = sum(reponse.score_calcule for reponse in reponses_etat)

        self.niveau_anxiete_etat = self.get_niveau_anxiete(self.score_etat)

 

        # Score TRAIT (items 21-40)

        reponses_trait = self.reponses.filter(item__section='TRAIT')

        self.score_trait = sum(reponse.score_calcule for reponse in reponses_trait)

        self.niveau_anxiete_trait = self.get_niveau_anxiete(self.score_trait)

 

        self.save()

        return self.score_etat, self.score_trait

 

    def get_niveau_anxiete(self, score):

        """Retourne le niveau d'anxiété selon le score"""

        if score < 20:

            return 'invalide'

        elif score <= 35:

            return 'minimale'

        elif score <= 45:

            return 'faible'

        elif score <= 55:

            return 'moderee'

        elif score <= 65:

            return 'elevee'

        else:

            return 'tres_elevee'

 

    def get_niveau_display(self, niveau):

        """Retourne le niveau d'anxiété formaté pour l'affichage"""

        niveaux = {

            'minimale': 'Anxiété minimale',

            'faible': 'Anxiété faible',

            'moderee': 'Anxiété modérée',

            'elevee': 'Anxiété élevée',

            'tres_elevee': 'Anxiété très élevée',

            'invalide': 'Score invalide'

        }

        return niveaux.get(niveau, 'Non évalué')

 

    @property

    def niveau_etat_display(self):

        return self.get_niveau_display(self.niveau_anxiete_etat)

 

    @property

    def niveau_trait_display(self):

        return self.get_niveau_display(self.niveau_anxiete_trait)

 

    @property

    def interpretation_etat(self):

        """Retourne une interprétation du score ÉTAT"""

        interpretations = {

            'minimale': "Le score suggère une absence ou une présence minimale d'anxiété situationnelle.",

            'faible': "Le score indique une anxiété situationnelle faible, dans les limites normales.",

            'moderee': "Le score suggère une anxiété situationnelle modérée. Une évaluation approfondie peut être utile.",

            'elevee': "Le score indique une anxiété situationnelle élevée. Un suivi est recommandé.",

            'tres_elevee': "Le score suggère une anxiété situationnelle très élevée. Une prise en charge est fortement recommandée."

        }

        return interpretations.get(self.niveau_anxiete_etat, "")

 

    @property

    def interpretation_trait(self):

        """Retourne une interprétation du score TRAIT"""

        interpretations = {

            'minimale': "Le score suggère une absence ou une présence minimale d'anxiété générale.",

            'faible': "Le score indique une anxiété générale faible, dans les limites normales.",

            'moderee': "Le score suggère une anxiété générale modérée. Une évaluation approfondie peut être utile.",

            'elevee': "Le score indique une anxiété générale élevée. Un suivi psychologique est recommandé.",

            'tres_elevee': "Le score suggère une anxiété générale très élevée. Une prise en charge thérapeutique est fortement recommandée."

        }

        return interpretations.get(self.niveau_anxiete_trait, "")

 

 

class ReponseItemSTAI(TenantModel):

    """Réponse d'un patient à un item spécifique du STAI"""

 

    test = models.ForeignKey(

        TestSTAI,

        on_delete=models.CASCADE,

        related_name='reponses',

        verbose_name="Test"

    )

    item = models.ForeignKey(

        ItemSTAI,

        on_delete=models.CASCADE,

        verbose_name="Item"

    )

    valeur_choisie = models.IntegerField(

        verbose_name="Valeur choisie",

        help_text="Valeur brute choisie par le patient (1, 2, 3 ou 4)"

    )

    score_calcule = models.IntegerField(

        default=0,

        verbose_name="Score calculé",

        help_text="Score après inversion si nécessaire"

    )

 

    class Meta:

        verbose_name = "Réponse Item STAI"

        verbose_name_plural = "Réponses Items STAI"

        unique_together = ['test', 'item']

        ordering = ['item__numero']

 

    def __str__(self):

        return f"Test {self.test.id} - Item {self.item.numero} - Score {self.score_calcule}"

 

    def calculer_score(self):

        """

        Calcule le score en tenant compte de l'inversion.

        Items inversés : 1→4, 2→3, 3→2, 4→1

        Items normaux : score = valeur choisie

        """

        if self.item.est_inverse:

            # Inversion du score

            self.score_calcule = 5 - self.valeur_choisie

        else:

            self.score_calcule = self.valeur_choisie

 

        self.save()

        return self.score_calcule