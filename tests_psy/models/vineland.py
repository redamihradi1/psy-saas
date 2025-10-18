from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from core.models import TenantModel


# ========== MODÈLES AVEC ORGANISATION (MULTI-TENANT) ==========

class TestVineland(TenantModel):
    """Test Vineland pour un patient - MULTI-TENANT"""
    patient = models.ForeignKey(
        'cabinet.Patient',
        on_delete=models.CASCADE,
        related_name='tests_vineland',
        verbose_name="Patient"
    )
    psychologue = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='tests_vineland_administres',
        verbose_name="Psychologue"
    )
    date_passation = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date de passation"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes du psychologue"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Test Vineland"
        verbose_name_plural = "Tests Vineland"
        ordering = ['-date_passation']
    
    def __str__(self):
        return f"Vineland - {self.patient.nom_complet} - {self.date_passation.strftime('%d/%m/%Y')}"
    
    @property
    def is_complete(self):
        """Vérifie si toutes les questions ont une réponse"""
        total_questions = QuestionVineland.objects.count()
        total_reponses = self.reponses_vineland.count()
        return total_reponses >= total_questions


class ReponseVineland(TenantModel):
    """Réponses au test Vineland - MULTI-TENANT"""
    test_vineland = models.ForeignKey(
        TestVineland,
        on_delete=models.CASCADE,
        related_name='reponses_vineland',
        verbose_name="Test Vineland"
    )
    question = models.ForeignKey(
        'tests_psy.QuestionVineland',
        on_delete=models.CASCADE,
        related_name='reponses'
    )
    reponse = models.CharField(
        max_length=3,
        choices=[
            ('0', '0'),
            ('1', '1'),
            ('2', '2'),
            ('NSP', 'Ne sais pas'),
            ('NA', 'Non applicable'),
            ('?', '?'),
            ('', 'Non répondu')
        ],
        null=True,
        blank=True,
        verbose_name="Réponse"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réponse Vineland"
        verbose_name_plural = "Réponses Vineland"
        unique_together = ['test_vineland', 'question']

    def __str__(self):
        return f"Réponse pour {self.question} - Test {self.test_vineland.id}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.reponse == 'NA' and not self.question.permet_na:
            raise ValidationError("La réponse 'Non applicable' n'est pas autorisée pour cette question.")


# ========== MODÈLES DE CONFIGURATION (PARTAGÉS - SANS ORGANISATION) ==========

class PlageItemVineland(models.Model):
    """Plages d'items Vineland par âge - CONFIGURATION PARTAGÉE"""
    sous_domaine = models.ForeignKey(
        'tests_psy.SousDomain',
        on_delete=models.CASCADE,
        related_name='plages_items_vineland'
    )
    item_debut = models.PositiveIntegerField(
        verbose_name="Premier item de la plage"
    )
    item_fin = models.PositiveIntegerField(
        verbose_name="Dernier item de la plage"
    )
    age_debut = models.PositiveIntegerField(
        verbose_name="Âge minimum (en années)"
    )
    age_fin = models.PositiveIntegerField(
        verbose_name="Âge maximum (en années)",
        null=True,
        blank=True,
        help_text="Laisser vide si pas de maximum (7+ par exemple)"
    )

    class Meta:
        verbose_name = "Plage d'items Vineland"
        verbose_name_plural = "Plages d'items Vineland"
        ordering = ['sous_domaine', 'item_debut']

    def __str__(self):
        age_str = f"{self.age_debut}-{self.age_fin}" if self.age_fin else f"{self.age_debut}+"
        return f"{self.sous_domaine} - Items {self.item_debut}-{self.item_fin} ({age_str} ans)"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.item_fin < self.item_debut:
            raise ValidationError("Le dernier item doit être supérieur au premier item")


class QuestionVineland(models.Model):
    """Questions du test Vineland - CONFIGURATION PARTAGÉE"""
    CHOIX_REPONSES = (
        ('0', '0'),
        ('1', '1'),
        ('2', '2'),
        ('NSP', 'Ne sais pas'),
        ('NA', 'Non applicable'),
        ('?', '?'),
        ('', 'Non répondu')
    )

    texte = models.TextField(verbose_name="Question")
    sous_domaine = models.ForeignKey(
        'tests_psy.SousDomain',
        on_delete=models.CASCADE,
        related_name='questions_vineland'
    )
    numero_item = models.PositiveIntegerField(
        verbose_name="Numéro de l'item",
        help_text="Numéro de l'item dans le sous-domaine"
    )
    note = models.TextField(
        verbose_name="Note/Indication", 
        blank=True, 
        null=True,
        help_text="Pour plusieurs lignes, utilisez | comme séparateur"
    )
    permet_na = models.BooleanField(
        verbose_name="Permet la réponse N/A",
        default=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Question Vineland"
        verbose_name_plural = "Questions Vineland"
        ordering = ['sous_domaine', 'numero_item']
        unique_together = ['sous_domaine', 'numero_item']

    def __str__(self):
        return f"{self.sous_domaine} - Item {self.numero_item}: {self.texte[:50]}..."
    
    def save(self, *args, **kwargs):
        if self.note:
            self.note = self.note.replace('\n', '|').replace('\r', '')
        super().save(*args, **kwargs)

    def get_plage_age(self):
        """Retourne la plage d'âge correspondante à cet item"""
        return PlageItemVineland.objects.filter(
            sous_domaine=self.sous_domaine,
            item_debut__lte=self.numero_item,
            item_fin__gte=self.numero_item
        ).first()


class EchelleVMapping(models.Model):
    """Correspondances Échelle-V - CONFIGURATION PARTAGÉE"""
    sous_domaine = models.ForeignKey(
        'tests_psy.SousDomain',
        on_delete=models.CASCADE,
        related_name='echelle_v_mappings',
        verbose_name="Sous-domaine"
    )
    
    # Tranche d'âge
    age_debut_annee = models.PositiveIntegerField(verbose_name="Âge début - Années")
    age_debut_mois = models.PositiveIntegerField(
        verbose_name="Âge début - Mois",
        validators=[MaxValueValidator(11)]
    )
    age_debut_jour = models.PositiveIntegerField(
        verbose_name="Âge début - Jours",
        validators=[MaxValueValidator(30)],
        null=True,
        blank=True
    )
    
    age_fin_annee = models.PositiveIntegerField(verbose_name="Âge fin - Années")
    age_fin_mois = models.PositiveIntegerField(
        verbose_name="Âge fin - Mois",
        validators=[MaxValueValidator(11)]
    )
    age_fin_jour = models.PositiveIntegerField(
        verbose_name="Âge fin - Jours",
        validators=[MaxValueValidator(30)],
        null=True,
        blank=True
    )
    
    # Note brute et correspondance échelle-V
    note_brute_min = models.PositiveIntegerField(verbose_name="Note brute minimum")
    note_brute_max = models.PositiveIntegerField(verbose_name="Note brute maximum")
    note_echelle_v = models.PositiveIntegerField(
        verbose_name="Note échelle-V",
        validators=[MinValueValidator(1), MaxValueValidator(24)]
    )

    class Meta:
        verbose_name = "Correspondance Échelle-V"
        verbose_name_plural = "Correspondances Échelle-V"
        ordering = ['sous_domaine', 'age_debut_annee', 'age_debut_mois', 'note_brute_min']

    def __str__(self):
        return (
            f"{self.sous_domaine} - "
            f"{self.age_debut_annee};{self.age_debut_mois};{self.age_debut_jour or 0} à "
            f"{self.age_fin_annee};{self.age_fin_mois};{self.age_fin_jour or 0} - "
            f"Note brute {self.note_brute_min}-{self.note_brute_max} → V : {self.note_echelle_v}"
        )


class NoteDomaineVMapping(models.Model):
    """Correspondances Notes Domaines - CONFIGURATION PARTAGÉE"""
    TRANCHES_AGE = [
        ('1-2', '1 à 2 ans'),
        ('3-6', '3 à 6 ans'),
        ('7-18', '7 à 18 ans'),
        ('19-49', '19 à 49 ans'),
        ('50-90', '50 à 90 ans'),
    ]

    tranche_age = models.CharField(
        max_length=10,
        choices=TRANCHES_AGE,
        verbose_name="Tranche d'âge"
    )
    
    # Intervalles pour les notes des sous-domaines
    communication_min = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Communication minimum"
    )
    communication_max = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Communication maximum"
    )
    
    vie_quotidienne_min = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Vie quotidienne minimum"
    )
    vie_quotidienne_max = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Vie quotidienne maximum"
    )
    
    socialisation_min = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Socialisation minimum"
    )
    socialisation_max = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Socialisation maximum"
    )
    
    motricite_min = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Motricité minimum"
    )
    motricite_max = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MaxValueValidator(72)],
        verbose_name="Note Motricité maximum"
    )

    # Résultats
    note_standard = models.PositiveIntegerField(
        validators=[MinValueValidator(20), MaxValueValidator(160)],
        verbose_name="Note standard"
    )
    note_composite_min = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Note composite minimum"
    )
    note_composite_max = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Note composite maximum"
    )
    rang_percentile = models.CharField(
        max_length=10,
        verbose_name="Rang percentile"
    )

    class Meta:
        verbose_name = "Correspondance Note Domaine"
        verbose_name_plural = "Correspondances Notes Domaines"
        unique_together = ['tranche_age', 'note_standard']
        ordering = ['tranche_age', '-note_standard']

    def __str__(self):
        return f"{self.tranche_age} - Note Standard: {self.note_standard} - Rang: {self.rang_percentile}"


class IntervaleConfianceSousDomaine(models.Model):
    """Intervalles de confiance sous-domaines - CONFIGURATION PARTAGÉE"""
    NIVEAUX_CONFIANCE = [
        (95, '95%'),
        (90, '90%'),
        (85, '85%'),
    ]

    TRANCHES_AGE = [
        ('1', '1 an'), ('2', '2 ans'), ('3', '3 ans'), ('4', '4 ans'),
        ('5', '5 ans'), ('6', '6 ans'), ('7-8', '7-8 ans'), ('9-11', '9-11 ans'),
        ('12-14', '12-14 ans'), ('15-18', '15-18 ans'), ('19-29', '19-29 ans'),
        ('30-49', '30-49 ans'), ('50-90', '50-90 ans'),
    ]

    age = models.CharField(max_length=10, choices=TRANCHES_AGE)
    niveau_confiance = models.IntegerField(choices=NIVEAUX_CONFIANCE)
    sous_domaine = models.ForeignKey(
        'tests_psy.SousDomain',
        on_delete=models.CASCADE,
        related_name='intervalles_confiance'
    )
    intervalle = models.IntegerField(
        help_text="Valeur de l'intervalle (ex: ±2 → entrer 2)"
    )

    class Meta:
        verbose_name = "Intervalle de confiance sous-domaine"
        verbose_name_plural = "Intervalles de confiance sous-domaines"
        unique_together = ['age', 'niveau_confiance', 'sous_domaine']
        ordering = ['age', '-niveau_confiance', 'sous_domaine']

    def __str__(self):
        return f"{self.age} - {self.niveau_confiance}% - {self.sous_domaine} (±{self.intervalle})"


class IntervaleConfianceDomaine(models.Model):
    """Intervalles de confiance domaines - CONFIGURATION PARTAGÉE"""
    NIVEAUX_CONFIANCE = [(95, '95%'), (90, '90%'), (85, '85%')]
    TRANCHES_AGE = [
        ('1', '1 an'), ('2', '2 ans'), ('3', '3 ans'), ('4', '4 ans'),
        ('5', '5 ans'), ('6', '6 ans'), ('7-8', '7-8 ans'), ('9-11', '9-11 ans'),
        ('12-14', '12-14 ans'), ('15-18', '15-18 ans'), ('19-29', '19-29 ans'),
        ('30-49', '30-49 ans'), ('50-90', '50-90 ans'),
    ]

    age = models.CharField(max_length=10, choices=TRANCHES_AGE)
    niveau_confiance = models.IntegerField(choices=NIVEAUX_CONFIANCE)
    domain = models.ForeignKey(
        'tests_psy.Domain',
        on_delete=models.CASCADE,
        related_name='intervalles_confiance'
    )
    intervalle = models.IntegerField(
        help_text="Valeur de l'intervalle (ex: ±5 → entrer 5)"
    )
    note_composite = models.IntegerField(
        help_text="Note composite pour ce niveau de confiance",
        null=True, blank=True
    )

    class Meta:
        verbose_name = "Intervalle de confiance domaine"
        verbose_name_plural = "Intervalles de confiance domaines"
        unique_together = ['age', 'niveau_confiance', 'domain']
        ordering = ['age', '-niveau_confiance', 'domain']

    def __str__(self):
        base = f"{self.age} - {self.niveau_confiance}% - {self.domain} (±{self.intervalle})"
        if self.note_composite:
            base += f" [Note composite: {self.note_composite}]"
        return base


class NiveauAdaptatif(models.Model):
    """Niveaux adaptatifs - CONFIGURATION PARTAGÉE"""
    NIVEAUX = [
        ('faible', 'Faible'),
        ('assez_faible', 'Assez faible'),
        ('adapte', 'Adapté'),
        ('assez_eleve', 'Assez élevé'),
        ('eleve', 'Élevé'),
    ]
    
    niveau = models.CharField(
        max_length=20, choices=NIVEAUX,
        verbose_name="Niveau adaptatif"
    )
    echelle_v_min = models.IntegerField(verbose_name="Échelle-v minimum")
    echelle_v_max = models.IntegerField(verbose_name="Échelle-v maximum")
    note_standard_min = models.IntegerField(verbose_name="Note standard minimum")
    note_standard_max = models.IntegerField(verbose_name="Note standard maximum")
    
    class Meta:
        verbose_name = "Niveau adaptatif"
        verbose_name_plural = "Niveaux adaptatifs"
        ordering = ['echelle_v_min']
        
    def __str__(self):
        return f"{self.get_niveau_display()} (Échelle-v: {self.echelle_v_min}-{self.echelle_v_max})"


class AgeEquivalentSousDomaine(models.Model):
    """Équivalences d'âge - CONFIGURATION PARTAGÉE"""
    SPECIAL_AGES = [
        ('>18', 'Plus de 18 ans'),
        ('<1', 'Moins de 1 an'),
    ]

    sous_domaine = models.ForeignKey(
        'tests_psy.SousDomain',
        on_delete=models.CASCADE,
        verbose_name="Sous-domaine",
        related_name='age_equivalents'
    )
    note_brute_min = models.IntegerField(verbose_name="Note brute minimum")
    note_brute_max = models.IntegerField(
        verbose_name="Note brute maximum",
        null=True, blank=True
    )
    age_special = models.CharField(
        max_length=4, choices=SPECIAL_AGES,
        null=True, blank=True,
        verbose_name="Âge spécial"
    )
    age_annees = models.IntegerField(
        null=True, blank=True,
        verbose_name="Années"
    )
    age_mois = models.IntegerField(
        null=True, blank=True,
        verbose_name="Mois",
        validators=[MinValueValidator(0), MaxValueValidator(11)]
    )

    def get_age_equivalent_display(self):
        if self.age_special:
            return "Plus de 18 ans" if self.age_special == '>18' else "Moins de 1 an"
        if self.age_annees is not None:
            if self.age_mois:
                return f"{self.age_annees} an(s) et {self.age_mois} mois"
            return str(self.age_annees)
        return "-"

    class Meta:
        verbose_name = "Équivalence d'âge pour sous-domaine"
        verbose_name_plural = "Équivalences d'âge pour sous-domaines"
        ordering = ['sous_domaine', '-age_annees', '-age_mois']
        unique_together = ['sous_domaine', 'note_brute_min', 'note_brute_max']

    def __str__(self):
        note_display = f"{self.note_brute_min}-{self.note_brute_max}" if self.note_brute_max else str(self.note_brute_min)
        return f"{self.sous_domaine.name}: {note_display} → {self.get_age_equivalent_display()}"


class ComparaisonDomaineVineland(models.Model):
    """Comparaisons de domaines - CONFIGURATION PARTAGÉE"""
    age = models.CharField(max_length=10)
    niveau_significativite = models.CharField(max_length=5)
    domaine1 = models.ForeignKey('tests_psy.Domain', on_delete=models.CASCADE, related_name='comparaison_domaine1')
    domaine2 = models.ForeignKey('tests_psy.Domain', on_delete=models.CASCADE, related_name='comparaison_domaine2')
    difference_requise = models.IntegerField()
    
    class Meta:
        unique_together = ('age', 'niveau_significativite', 'domaine1', 'domaine2')
        verbose_name = "Comparaison de domaines"
        verbose_name_plural = "Comparaisons de domaines"
    
    def __str__(self):
        return f"{self.domaine1} vs {self.domaine2} ({self.age} ans, {self.niveau_significativite})"


class ComparaisonSousDomaineVineland(models.Model):
    """Comparaisons de sous-domaines - CONFIGURATION PARTAGÉE"""
    age = models.CharField(max_length=10)
    niveau_significativite = models.CharField(max_length=5)
    sous_domaine1 = models.ForeignKey('tests_psy.SousDomain', on_delete=models.CASCADE, related_name='comparaison_sous_domaine1')
    sous_domaine2 = models.ForeignKey('tests_psy.SousDomain', on_delete=models.CASCADE, related_name='comparaison_sous_domaine2')
    difference_requise = models.IntegerField()
    
    class Meta:
        unique_together = ('age', 'niveau_significativite', 'sous_domaine1', 'sous_domaine2')
        verbose_name = "Comparaison de sous-domaines"
        verbose_name_plural = "Comparaisons de sous-domaines"
    
    def __str__(self):
        return f"{self.sous_domaine1} vs {self.sous_domaine2} ({self.age} ans, {self.niveau_significativite})"


class FrequenceDifferenceDomaineVineland(models.Model):
    """Fréquences de différence (domaines) - CONFIGURATION PARTAGÉE"""
    age = models.CharField(max_length=10)
    domaine1 = models.ForeignKey('tests_psy.Domain', on_delete=models.CASCADE, related_name='freq_domaine1')
    domaine2 = models.ForeignKey('tests_psy.Domain', on_delete=models.CASCADE, related_name='freq_domaine2')
    frequence_16 = models.CharField(max_length=10)
    frequence_10 = models.CharField(max_length=10)
    frequence_5 = models.CharField(max_length=10)
    
    class Meta:
        unique_together = ('age', 'domaine1', 'domaine2')
        verbose_name = "Fréquence de différence (domaines)"
        verbose_name_plural = "Fréquences de différence (domaines)"
        
    def __str__(self):
        return f"Fréquence {self.domaine1} vs {self.domaine2} ({self.age} ans)"


class FrequenceDifferenceSousDomaineVineland(models.Model):
    """Fréquences de différence (sous-domaines) - CONFIGURATION PARTAGÉE"""
    age = models.CharField(max_length=10)
    sous_domaine1 = models.ForeignKey('tests_psy.SousDomain', on_delete=models.CASCADE, related_name='freq_sous_domaine1')
    sous_domaine2 = models.ForeignKey('tests_psy.SousDomain', on_delete=models.CASCADE, related_name='freq_sous_domaine2')
    frequence_16 = models.CharField(max_length=10)
    frequence_10 = models.CharField(max_length=10)
    frequence_5 = models.CharField(max_length=10)
    
    class Meta:
        unique_together = ('age', 'sous_domaine1', 'sous_domaine2')
        verbose_name = "Fréquence de différence (sous-domaines)"
        verbose_name_plural = "Fréquences de différence (sous-domaines)"
        
    def __str__(self):
        return f"Fréquence {self.sous_domaine1} vs {self.sous_domaine2} ({self.age} ans)"