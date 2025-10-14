from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta

class Organization(models.Model):
    """Cabinet/Organisation du psychologue"""
    name = models.CharField(max_length=200, verbose_name="Nom du cabinet")
    slug = models.SlugField(unique=True, verbose_name="Identifiant unique")
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Utilisateur personnalisé"""
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('psychologist', 'Psychologue'),
        ('assistant', 'Assistant'),
    ]
    
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='users'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='psychologist')
    phone = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=100, blank=True, verbose_name="Numéro de licence professionnelle")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def is_superadmin(self):
        return self.role == 'superadmin'

    def is_psychologist(self):
        return self.role == 'psychologist'


class License(models.Model):
    """Licence d'utilisation pour une organisation"""
    PLAN_CHOICES = [
        ('trial', 'Essai gratuit (30 jours)'),
        ('lifetime', 'Licence complète (achat unique)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expirée'),
        ('suspended', 'Suspendue'),
        ('cancelled', 'Annulée'),
    ]
    
    organization = models.OneToOneField(
        Organization, 
        on_delete=models.CASCADE,
        related_name='license'
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='trial')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Limites patients
    max_patients = models.IntegerField(default=10, verbose_name="Nombre max de patients")
    
    # Dates
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Date de fin (null = illimité)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Licence"
        verbose_name_plural = "Licences"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.organization.name} - {self.get_plan_display()}"

    def save(self, *args, **kwargs):
        # Définir les limites selon le plan
        if self.plan == 'trial':
            self.max_patients = 10
            if not self.end_date:
                self.end_date = timezone.now() + timedelta(days=30)
        elif self.plan == 'lifetime':
            self.max_patients = 100
            self.end_date = None
        super().save(*args, **kwargs)

    def is_active(self):
        """Vérifie si la licence est active et non expirée"""
        if self.status != 'active':
            return False
        # Lifetime = toujours actif
        if self.plan == 'lifetime':
            return True
        # Trial = vérifier la date
        return self.end_date and self.end_date > timezone.now()

    def days_remaining(self):
        """Nombre de jours restants (trial uniquement)"""
        if self.plan == 'lifetime':
            return 'Illimité'
        if self.end_date and self.end_date > timezone.now():
            return (self.end_date - timezone.now()).days
        return 0
    
    def has_patient_limit(self):
        """Vérifie si cette licence a une limite de patients"""
        return True  # Les deux plans ont une limite