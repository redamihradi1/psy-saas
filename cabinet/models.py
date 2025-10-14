from django.db import models
from django.core.validators import EmailValidator, FileExtensionValidator
from datetime import date, timedelta
from django.utils import timezone
import os

from core.models import TenantModel  # ← MULTI-TENANT


class Patient(TenantModel):  # ← Hérite de TenantModel
    CATEGORIE_CHOICES = [
        ('adulte', 'Adulte'),
        ('enfant', 'Enfant'),
    ]
    
    nom = models.CharField(max_length=100, verbose_name="Nom", db_index=True)
    prenom = models.CharField(max_length=100, verbose_name="Prénom", db_index=True)
    date_naissance = models.DateField(verbose_name="Date de naissance")
    categorie_age = models.CharField(
        max_length=10, 
        choices=CATEGORIE_CHOICES, 
        default='adulte',
        verbose_name="Catégorie d'âge"
    )
    telephone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        verbose_name="Téléphone"
    )
    email = models.EmailField(
        blank=True, 
        null=True,
        validators=[EmailValidator()],
        verbose_name="Email"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"
        ordering = ['nom', 'prenom']
        indexes = [
            models.Index(fields=['organization', 'nom', 'prenom']),
        ]
    
    def __str__(self):
        return f"{self.prenom} {self.nom}"
    
    @property
    def age(self):
        """Calcule l'âge du patient"""
        today = date.today()
        age = today.year - self.date_naissance.year
        if today.month < self.date_naissance.month or \
           (today.month == self.date_naissance.month and today.day < self.date_naissance.day):
            age -= 1
        return age
    
    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"


class Anamnese(TenantModel):  # ← Hérite de TenantModel
    patient = models.OneToOneField(
        Patient, 
        on_delete=models.CASCADE,
        verbose_name="Patient"
    )
    motif_consultation = models.TextField(verbose_name="Motif de consultation")
    antecedents_medicaux = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Antécédents médicaux"
    )
    antecedents_familiaux = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Antécédents familiaux"
    )
    medicaments_actuels = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Médicaments actuels"
    )
    deja_consulte_psy = models.BooleanField(
        default=False,
        verbose_name="A déjà consulté un psy"
    )
    situation_professionnelle = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Situation professionnelle"
    )
    situation_familiale = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Situation familiale"
    )
    troubles_sommeil = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Troubles du sommeil"
    )
    troubles_alimentaires = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Troubles alimentaires"
    )
    activite_physique = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Activité physique régulière"
    )
    hobbies_bien_etre = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Hobbies et activités bien-être"
    )
    changements_souhaites = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Changements souhaités dans la vie"
    )
    consommation_substances = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Consommation de substances"
    )
    niveau_stress = models.IntegerField(
        default=5,
        choices=[(i, i) for i in range(1, 11)],
        verbose_name="Niveau de stress (1-10)"
    )
    objectifs_therapie = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Objectifs de la thérapie"
    )
    attentes_patient = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Attentes du patient"
    )
    contraintes_horaires = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Contraintes horaires"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Anamnèse"
        verbose_name_plural = "Anamnèses"
    
    def __str__(self):
        return f"Anamnèse de {self.patient}"


class PackMindOffice(TenantModel):  # ← Hérite de TenantModel
    STATUT_CHOICES = [
        ('actif', 'Actif'),
        ('expire', 'Expiré'),
        ('suspendu', 'Suspendu'),
    ]
    
    nom_pack = models.CharField(
        max_length=100,
        verbose_name="Nom du pack",
        default="Pack Mind Office"
    )
    nombre_seances_total = models.IntegerField(verbose_name="Nombre de séances total")
    nombre_seances_utilisees = models.IntegerField(
        default=0,
        verbose_name="Nombre de séances utilisées"
    )
    date_achat = models.DateField(verbose_name="Date d'achat")
    date_expiration = models.DateField(
        blank=True, 
        null=True,
        verbose_name="Date d'expiration"
    )
    prix_pack = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Prix du pack (DHS)"
    )
    statut = models.CharField(
        max_length=10, 
        choices=STATUT_CHOICES,
        default='actif',
        verbose_name="Statut"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Pack Mind Office"
        verbose_name_plural = "Packs Mind Office"
        ordering = ['-date_achat']
    
    def __str__(self):
        return f"{self.nom_pack} - {self.seances_restantes} séances restantes"
    
    @property
    def seances_restantes(self):
        return self.nombre_seances_total - self.nombre_seances_utilisees
    
    @property
    def prix_par_seance(self):
        if self.nombre_seances_total > 0:
            return round(self.prix_pack / self.nombre_seances_total, 2)
        return 0
    
    @property
    def pourcentage_utilise(self):
        if self.nombre_seances_total > 0:
            return round((self.nombre_seances_utilisees / self.nombre_seances_total) * 100, 1)
        return 0


class Consultation(TenantModel):  # ← Hérite de TenantModel
    LIEU_CONSULTATION_CHOICES = [
        ('visio', 'Visioconférence'),
        ('bouskoura', 'Cabinet Bouskoura'),
        ('mind_office', 'Cabinet Mind Office'),
    ]
    TYPE_CONSULTATION_CHOICES = [
        ('individuelle', 'Consultation individuelle'),
        ('couple', 'Thérapie de couple'),
        ('famille', 'Thérapie familiale'),
        ('groupe', 'Thérapie de groupe'),
        ('suivi', 'Consultation de suivi'),
    ]
    
    STATUT_PAIEMENT_CHOICES = [
        ('paye', 'Payé'),
        ('attente', 'En attente'),
        ('annule', 'Annulé'),
    ]
    
    STATUT_CONSULTATION_CHOICES = [
        ('planifie', 'Planifiée'),
        ('reporte', 'Reportée'),
        ('annule', 'Annulée'),
        ('termine', 'Terminée'),
        ('absent', 'Patient absent'),
    ]
    
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.CASCADE,
        verbose_name="Patient"
    )
    date_seance = models.DateTimeField(verbose_name="Date et heure de séance", db_index=True)
    duree_minutes = models.IntegerField(
        default=60,
        verbose_name="Durée (minutes)"
    )
    type_consultation = models.CharField(
        max_length=20, 
        choices=TYPE_CONSULTATION_CHOICES,
        default='individuelle',
        verbose_name="Type de consultation"
    )
    notes_cliniques = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Notes cliniques"
    )
    objectifs_seance = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Objectifs de la séance"
    )
    exercices_prevus = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Exercices prévus"
    )
    suivi_progression = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Suivi de progression"
    )
    tarif = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Tarif (DHS)"
    )
    statut_paiement = models.CharField(
        max_length=10, 
        choices=STATUT_PAIEMENT_CHOICES,
        default='attente',
        verbose_name="Statut du paiement"
    )
    date_paiement = models.DateField(
        blank=True, 
        null=True,
        verbose_name="Date de paiement"
    )
    lieu_consultation = models.CharField(
        max_length=20,
        choices=LIEU_CONSULTATION_CHOICES,
        default='visio',
        verbose_name="Lieu de consultation"
    )
    pack_mind_office_utilise = models.ForeignKey(
        PackMindOffice,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Pack Mind Office utilisé"
    )
    
    statut_consultation = models.CharField(
        max_length=20,
        choices=STATUT_CONSULTATION_CHOICES,
        default='planifie',
        verbose_name="Statut de la consultation"
    )
    date_seance_originale = models.DateTimeField(
        blank=True, 
        null=True,
        verbose_name="Date de séance originale"
    )
    nombre_reports = models.IntegerField(
        default=0,
        verbose_name="Nombre de reports"
    )
    motif_report = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Motif du report/annulation"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Consultation"
        verbose_name_plural = "Consultations"
        ordering = ['-date_seance']
        indexes = [
            models.Index(fields=['organization', '-date_seance']),
            models.Index(fields=['organization', 'statut_paiement']),
        ]
    
    def __str__(self):
        return f"Consultation {self.patient} - {self.date_seance.strftime('%d/%m/%Y %H:%M')}"
    
    @property
    def est_reporte(self):
        return self.statut_consultation == 'reporte'
    
    @property
    def est_annule(self):
        return self.statut_consultation == 'annule'
    
    @property
    def peut_etre_reporte(self):
        return self.statut_consultation in ['planifie', 'reporte']
    
    @property
    def historique_reports(self):
        if self.nombre_reports == 0:
            return "Aucun report"
        elif self.nombre_reports == 1:
            return "Reportée 1 fois"
        else:
            return f"Reportée {self.nombre_reports} fois"
    
    def reporter(self, nouvelle_date, motif=None):
        if self.nombre_reports == 0:
            self.date_seance_originale = self.date_seance
        
        self.date_seance = nouvelle_date
        self.nombre_reports += 1
        self.statut_consultation = 'reporte'
        if motif:
            self.motif_report = motif
        
        self.save()
        return True
    
    def annuler(self, motif=None):
        self.statut_consultation = 'annule'
        if motif:
            self.motif_report = motif
        self.save()
        return True
    
    def marquer_termine(self):
        self.statut_consultation = 'termine'
        self.save()
        return True


class PatientFichier(TenantModel):  # ← Hérite de TenantModel
    CATEGORIE_CHOICES = [
        ('anamnese', 'Anamnèse / Bilan initial'),
        ('compte_rendu', 'Compte-rendu de séance'),
        ('test_psychologique', 'Test psychologique / Évaluation'),
        ('ordonnance_psy', 'Ordonnance psychiatrique'),
        ('certificat', 'Certificat médical / Arrêt'),
        ('courrier_medical', 'Courrier médical / Correspondance'),
        ('bilan_medical', 'Bilan médical externe'),
        ('imagerie', 'Imagerie médicale (IRM, Scanner...)'),
        ('resultats_analyses', 'Résultats d\'analyses'),
        ('document_juridique', 'Document juridique / Expertise'),
        ('autorisation', 'Autorisation parentale / Tutelle'),
        ('contrat_soin', 'Contrat de soin / Consentement'),
        ('suivi_externe', 'Suivi externe (autre praticien)'),
        ('document_scolaire', 'Document scolaire / Professionnel'),
        ('autre', 'Autre document'),
    ]
    
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.CASCADE,
        related_name='fichiers',
        verbose_name="Patient"
    )
    
    nom_fichier = models.CharField(
        max_length=255,
        verbose_name="Nom du fichier"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description"
    )
    
    categorie = models.CharField(
        max_length=20,
        choices=CATEGORIE_CHOICES,
        default='autre',
        verbose_name="Catégorie"
    )
    
    fichier = models.FileField(
        upload_to='patients_fichiers/%Y/%m/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 
                    'gif', 'bmp', 'tiff', 'txt', 'rtf', 'odt',
                    'xls', 'xlsx', 'ppt', 'pptx'
                ]
            )
        ],
        verbose_name="Fichier"
    )
    
    taille_fichier = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Taille (octets)"
    )
    
    date_upload = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'upload"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    
    class Meta:
        verbose_name = "Fichier Patient"
        verbose_name_plural = "Fichiers Patients"
        ordering = ['-date_upload']
    
    def __str__(self):
        return f"{self.nom_fichier} - {self.patient.nom_complet}"
    
    def save(self, *args, **kwargs):
        if self.fichier:
            self.taille_fichier = self.fichier.size
            if not self.nom_fichier:
                self.nom_fichier = os.path.basename(self.fichier.name)
        super().save(*args, **kwargs)
    
    @property
    def taille_lisible(self):
        if not self.taille_fichier:
            return "Inconnue"
        
        taille = self.taille_fichier
        for unit in ['octets', 'Ko', 'Mo', 'Go']:
            if taille < 1024.0:
                return f"{taille:.1f} {unit}"
            taille /= 1024.0
        return f"{taille:.1f} To"
    
    @property
    def extension(self):
        return os.path.splitext(self.fichier.name)[1].lower().replace('.', '')
    
    @property
    def est_image(self):
        return self.extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']